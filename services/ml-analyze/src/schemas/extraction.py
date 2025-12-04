"""
Extraction Schemas for Semantic ETL Pipeline
=============================================

Pydantic models for LLM-based product extraction.
Defines contracts for product data extracted from supplier files.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "name": self.name,
            "description": self.description,
            "price_opt": float(self.price_opt) if self.price_opt else None,
            "price_rrc": float(self.price_rrc),
            "category_path": self.category_path,
            "raw_data": self.raw_data,
        }
    
    def get_dedup_key(self) -> str:
        """
        Generate deduplication key for within-file dedup.
        
        Key is based on normalized name (lowercase, stripped).
        Used with price tolerance (1%) for duplicate detection.
        """
        return self.name.lower().strip()


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
        Calculate success rate as percentage.
        
        Returns:
            Percentage of successful extractions (0.0 - 100.0)
        """
        if self.total_rows == 0:
            return 0.0
        return (self.successful_extractions / self.total_rows) * 100

    @property
    def status(self) -> str:
        """
        Determine job status based on success rate.
        
        Returns:
            - 'success': 100% extraction rate
            - 'completed_with_errors': 80-99% extraction rate
            - 'failed': <80% extraction rate
        """
        rate = self.success_rate
        if rate == 100:
            return "success"
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

