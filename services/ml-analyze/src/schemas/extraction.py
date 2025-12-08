"""
Extraction Schemas for Semantic ETL Pipeline
=============================================

Pydantic models for LLM-based product extraction.
Defines contracts for product data extracted from supplier files.

Phase 9: Semantic ETL Pipeline Refactoring
Phase 10: Product Variants - Added variant_attributes field
"""

from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


# Common variant attribute keys for different product categories
VARIANT_ATTRIBUTE_KEYS = {
    # Electric transport
    "voltage": ["voltage", "вольт", "в", "v"],
    "capacity": ["capacity", "ёмкость", "емкость", "ач", "ah", "а"],
    "power": ["power", "мощность", "вт", "w"],
    # Electronics
    "storage": ["storage", "память", "гб", "gb", "тб", "tb"],
    "ram": ["ram", "озу", "оперативная память"],
    "color": ["color", "цвет", "colour"],
    # Apparel
    "size": ["size", "размер"],
    # General
    "model": ["model", "модель", "версия", "version"],
    "year": ["year", "год"],
}


class ExtractedProduct(BaseModel):
    """
    Product extracted from supplier file via LLM.
    
    Represents a single product with validated fields extracted
    from Excel/CSV files using LangChain + Ollama.
    
    Attributes:
        name: Product name (required, 1-500 chars, normalized)
        description: Product specifications or description
        price_opt: Wholesale/optimal price in BYN (optional)
        price_rrc: Retail/recommended price in BYN (required)
        category_path: Category hierarchy as array of strings
        variant_attributes: Structured specs for variant grouping (Phase 10)
        raw_data: Original row data for debugging
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Product name (required)"
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Product specifications or description"
    )
    price_opt: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Wholesale/optimal price in BYN"
    )
    price_rrc: Decimal = Field(
        ...,
        ge=Decimal("0"),
        description="Retail/recommended price in BYN (required)"
    )
    category_path: list[str] = Field(
        default_factory=list,
        description="Category hierarchy, e.g., ['Electronics', 'Laptops']"
    )
    # Phase 10: Product Variants
    variant_attributes: dict[str, Union[str, int, float]] = Field(
        default_factory=dict,
        description=(
            "Structured variant attributes extracted from product name/specs. "
            "Keys: voltage, capacity, storage, color, size, etc. "
            "Example: {'voltage': '48V', 'capacity': '20Ah'}"
        )
    )
    raw_data: dict = Field(
        default_factory=dict,
        description="Original row data for debugging"
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize product name: strip whitespace, collapse multiple spaces."""
        return " ".join(v.strip().split())

    @field_validator("category_path")
    @classmethod
    def normalize_categories(cls, v: list[str]) -> list[str]:
        """Normalize category names: strip whitespace, filter empty strings."""
        return [c.strip() for c in v if c.strip()]

    @field_validator("description")
    @classmethod
    def normalize_description(cls, v: Optional[str]) -> Optional[str]:
        """Normalize description: strip whitespace, return None if empty."""
        if v:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("variant_attributes")
    @classmethod
    def normalize_variant_attributes(
        cls, v: dict[str, Union[str, int, float]]
    ) -> dict[str, Union[str, int, float]]:
        """
        Normalize variant attribute keys and values.
        
        - Lowercase keys
        - Strip string values
        - Filter empty values
        """
        normalized = {}
        for key, value in v.items():
            key = key.lower().strip()
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
            normalized[key] = value
        return normalized

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "name": self.name,
            "description": self.description,
            "price_opt": float(self.price_opt) if self.price_opt else None,
            "price_rrc": float(self.price_rrc),
            "category_path": self.category_path,
            "variant_attributes": self.variant_attributes,
            "raw_data": self.raw_data,
        }
    
    def get_dedup_key(self) -> str:
        """
        Generate deduplication key for within-file dedup.
        
        Key is based on normalized name (lowercase, stripped).
        Used with price tolerance (1%) for duplicate detection.
        """
        return self.name.lower().strip()
    
    def get_variant_key(self) -> str:
        """
        Generate variant key from variant_attributes.
        
        Combines attribute values in a consistent order for grouping.
        Example: "48V/20Ah" or "256GB/Black"
        
        Returns:
            Slash-separated variant key, or empty string if no attributes
        """
        if not self.variant_attributes:
            return ""
        # Sort by key for consistent ordering
        values = [
            str(self.variant_attributes[k])
            for k in sorted(self.variant_attributes.keys())
        ]
        return "/".join(values)
    
    def get_base_product_name(self) -> str:
        """
        Extract base product name without variant specifications.
        
        Attempts to remove variant-specific text like "(48V/20A)" from the name.
        Used for grouping products with different variants.
        
        Returns:
            Normalized base product name
        """
        import re
        name = self.name
        # Remove common variant patterns from name
        # Pattern: (48V/20A), (256GB), [Black], etc.
        name = re.sub(r'\s*[\(\[]\s*[\d\w/]+[VvAaHhGgBb]*\s*[\)\]]', '', name)
        # Pattern: 48V20A at end of name
        name = re.sub(r'\s+\d+[VvАа]\s*/?\s*\d+[AaАа][Hh]?\s*$', '', name)
        return " ".join(name.strip().split())


class ExtractionError(BaseModel):
    """
    Error encountered during extraction.
    
    Captures details about extraction failures for debugging
    and error reporting.
    """
    
    row_number: Optional[int] = Field(
        None,
        ge=1,
        description="Row number in source file (1-indexed)"
    )
    chunk_id: Optional[int] = Field(
        None,
        ge=0,
        description="Chunk identifier for sliding window"
    )
    error_type: str = Field(
        ...,
        description="Error classification: 'validation', 'timeout', 'parsing', 'llm_error'"
    )
    error_message: str = Field(
        ...,
        description="Human-readable error description"
    )
    raw_data: Optional[dict] = Field(
        None,
        description="Original row data that caused the error"
    )


class ExtractionResult(BaseModel):
    """
    Result of file/sheet extraction process.
    
    Aggregates extraction results including successful products,
    error counts, and deduplication metrics.
    
    Attributes:
        products: Successfully extracted products
        sheet_name: Name of the processed sheet
        total_rows: Total rows processed (excluding header)
        successful_extractions: Number of products extracted successfully
        failed_extractions: Number of rows that failed extraction
        duplicates_removed: Number of duplicate products removed
        extraction_errors: List of errors with row numbers and messages
    """
    
    products: list[ExtractedProduct] = Field(
        default_factory=list,
        description="Successfully extracted products"
    )
    sheet_name: str = Field(
        ...,
        description="Name of the processed sheet"
    )
    total_rows: int = Field(
        ...,
        ge=0,
        description="Total rows processed (excluding header)"
    )
    successful_extractions: int = Field(
        ...,
        ge=0,
        description="Number of products extracted successfully"
    )
    failed_extractions: int = Field(
        ...,
        ge=0,
        description="Number of rows that failed extraction"
    )
    duplicates_removed: int = Field(
        default=0,
        ge=0,
        description="Number of duplicate products removed"
    )
    extraction_errors: list[ExtractionError] = Field(
        default_factory=list,
        description="List of errors with row numbers and messages"
    )

    @property
    def success_rate(self) -> float:
        """
        Calculate success rate as percentage of processed rows.
        
        Uses (successful / (successful + failed)) to ignore skipped rows
        (empty/metadata rows) that were not extraction failures.
        
        Returns:
            Percentage of successful extractions (0.0 - 100.0)
        """
        total_processed = self.successful_extractions + self.failed_extractions
        if total_processed == 0:
            return 0.0
        return (self.successful_extractions / total_processed) * 100

    @property
    def status(self) -> str:
        """
        Determine job status based on success rate.
        
        Returns:
            - 'complete': 100% extraction rate
            - 'completed_with_errors': 80-99% extraction rate
            - 'failed': <80% extraction rate
        
        Note: Returns 'complete' (not 'success') to match JobPhase enum.
        """
        rate = self.success_rate
        if rate == 100:
            return "complete"
        elif rate >= 80:
            return "completed_with_errors"
        else:
            return "failed"

    def to_summary_dict(self) -> dict:
        """Convert to summary dictionary for API responses."""
        return {
            "sheet_name": self.sheet_name,
            "total_rows": self.total_rows,
            "successful_extractions": self.successful_extractions,
            "failed_extractions": self.failed_extractions,
            "duplicates_removed": self.duplicates_removed,
            "success_rate": round(self.success_rate, 2),
            "status": self.status,
            "error_count": len(self.extraction_errors),
        }


class ChunkExtractionResult(BaseModel):
    """
    Result of extracting products from a single markdown chunk.
    
    Used during sliding window LLM extraction to track
    per-chunk progress and errors.
    """
    
    chunk_id: int = Field(
        ...,
        ge=0,
        description="Chunk identifier (0-indexed)"
    )
    start_row: int = Field(
        ...,
        ge=1,
        description="First row number in this chunk"
    )
    end_row: int = Field(
        ...,
        ge=1,
        description="Last row number in this chunk"
    )
    products: list[ExtractedProduct] = Field(
        default_factory=list,
        description="Products extracted from this chunk"
    )
    errors: list[ExtractionError] = Field(
        default_factory=list,
        description="Errors encountered in this chunk"
    )
    processing_time_ms: int = Field(
        default=0,
        ge=0,
        description="Time taken to process this chunk in milliseconds"
    )


class LLMExtractionResponse(BaseModel):
    """
    Response schema for LLM structured output.
    
    This schema is used with LangChain's with_structured_output()
    to enforce JSON structure from the LLM.
    """
    
    products: list[ExtractedProduct] = Field(
        default_factory=list,
        description="List of extracted products from the markdown table"
    )
    parsing_notes: Optional[str] = Field(
        None,
        description="Notes about parsing challenges or ambiguities"
    )

