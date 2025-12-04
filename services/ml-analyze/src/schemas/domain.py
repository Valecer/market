"""
Domain Models
=============

Internal domain models representing business entities.
Used for data transfer between services and components.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Phase 10: Two-Stage Parsing Models
# =============================================================================


class ColumnMapping(BaseModel):
    """
    Column index to field purpose mapping.

    Used by Stage A (structure analysis) to communicate column positions
    to Stage B (data extraction).

    Attributes:
        name_column: Column index for product name
        sku_column: Column index for SKU/article number
        retail_price_column: Column index for retail price
        wholesale_price_column: Column index for wholesale price
        category_column: Column index for category
        unit_column: Column index for unit of measure
        description_column: Column index for description
        brand_column: Column index for brand
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name_column": 1,
                "sku_column": 0,
                "retail_price_column": 2,
                "wholesale_price_column": 3,
                "category_column": None,
            }
        }
    )

    name_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for product name"),
    ] = None
    sku_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for SKU/article"),
    ] = None
    retail_price_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for retail price"),
    ] = None
    wholesale_price_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for wholesale price"),
    ] = None
    category_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for category"),
    ] = None
    unit_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for unit of measure"),
    ] = None
    description_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for description"),
    ] = None
    brand_column: Annotated[
        int | None,
        Field(default=None, ge=0, description="Column index for brand"),
    ] = None


class StructureAnalysis(BaseModel):
    """
    Stage A output: Document structure analysis result.

    Captures LLM's understanding of document layout including
    header positions, data row boundaries, and column purposes.

    Attributes:
        header_rows: Row indices containing headers (0-indexed)
        data_start_row: First row index with product data
        data_end_row: Last row index with product data (-1 for end of document)
        column_mapping: Mapping of columns to field purposes
        confidence: LLM's confidence in the analysis (0.0-1.0)
        detected_currency: Currency detected in headers or data sample
        has_merged_cells: Whether document appears to have merged cells
        notes: Optional LLM notes about document structure

    Example:
        {
            "header_rows": [0, 1],
            "data_start_row": 2,
            "data_end_row": -1,
            "column_mapping": {
                "name_column": 1,
                "sku_column": 0,
                "retail_price_column": 3
            },
            "confidence": 0.92
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "header_rows": [0],
                "data_start_row": 1,
                "data_end_row": -1,
                "column_mapping": {
                    "name_column": 1,
                    "sku_column": 0,
                    "retail_price_column": 2,
                    "wholesale_price_column": 3,
                },
                "confidence": 0.95,
                "detected_currency": "RUB",
                "has_merged_cells": False,
            }
        }
    )

    header_rows: Annotated[
        list[int],
        Field(min_length=0, description="Row indices containing headers (0-indexed)"),
    ]
    data_start_row: Annotated[
        int,
        Field(ge=0, description="First row with product data"),
    ]
    data_end_row: Annotated[
        int,
        Field(description="Last row with product data (-1 = end of document)"),
    ]
    column_mapping: Annotated[
        ColumnMapping,
        Field(description="Column index to field purpose mapping"),
    ]
    confidence: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Analysis confidence score"),
    ]
    detected_currency: Annotated[
        str | None,
        Field(default=None, max_length=3, description="ISO 4217 currency code if detected"),
    ] = None
    has_merged_cells: Annotated[
        bool,
        Field(default=False, description="Document has merged cells"),
    ] = False
    notes: Annotated[
        str | None,
        Field(default=None, max_length=500, description="LLM notes about structure"),
    ] = None


class ParsingMetrics(BaseModel):
    """
    Quality metrics for a parsing job.

    Tracks row counts, token usage, timing, and per-field extraction rates.

    Attributes:
        total_rows: Total rows in source document
        parsed_rows: Successfully parsed rows
        skipped_rows: Intentionally skipped rows (headers, totals, empty)
        error_rows: Rows with parsing errors
        stage_a_tokens: LLM tokens used for structure analysis
        stage_b_tokens: LLM tokens used for data extraction
        duration_ms: Total processing time in milliseconds
        file_read_ms: Time to read file
        stage_a_ms: Time for structure analysis
        stage_b_ms: Time for data extraction
        db_write_ms: Time for database writes
        field_extraction_rates: Per-field extraction success rates

    Example:
        {
            "total_rows": 500,
            "parsed_rows": 480,
            "skipped_rows": 15,
            "error_rows": 5,
            "stage_a_tokens": 1200,
            "stage_b_tokens": 8500,
            "duration_ms": 45000
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_rows": 500,
                "parsed_rows": 480,
                "skipped_rows": 15,
                "error_rows": 5,
                "stage_a_tokens": 1200,
                "stage_b_tokens": 8500,
                "duration_ms": 45000,
                "field_extraction_rates": {
                    "name": 1.0,
                    "sku": 0.95,
                    "retail_price": 0.98,
                },
            }
        }
    )

    # Row counts
    total_rows: Annotated[
        int,
        Field(ge=0, description="Total rows in source document"),
    ]
    parsed_rows: Annotated[
        int,
        Field(ge=0, description="Successfully parsed rows"),
    ]
    skipped_rows: Annotated[
        int,
        Field(ge=0, default=0, description="Intentionally skipped rows"),
    ] = 0
    error_rows: Annotated[
        int,
        Field(ge=0, default=0, description="Rows with parsing errors"),
    ] = 0

    # Token usage
    stage_a_tokens: Annotated[
        int,
        Field(ge=0, default=0, description="Tokens used in Stage A"),
    ] = 0
    stage_b_tokens: Annotated[
        int,
        Field(ge=0, default=0, description="Tokens used in Stage B"),
    ] = 0

    # Timing breakdown
    duration_ms: Annotated[
        int,
        Field(ge=0, description="Total processing time (ms)"),
    ]
    file_read_ms: Annotated[
        int,
        Field(ge=0, default=0, description="File read time (ms)"),
    ] = 0
    stage_a_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Stage A duration (ms)"),
    ] = 0
    stage_b_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Stage B duration (ms)"),
    ] = 0
    db_write_ms: Annotated[
        int,
        Field(ge=0, default=0, description="Database write time (ms)"),
    ] = 0

    # Per-field extraction rates
    field_extraction_rates: Annotated[
        dict[str, float],
        Field(
            default_factory=dict,
            description="Per-field extraction success rate (0.0-1.0)",
        ),
    ]

    @property
    def total_tokens(self) -> int:
        """Total LLM tokens used."""
        return self.stage_a_tokens + self.stage_b_tokens

    @property
    def success_rate(self) -> float:
        """Parsing success rate (0.0-1.0)."""
        if self.total_rows == 0:
            return 0.0
        return self.parsed_rows / self.total_rows


# =============================================================================
# Core Domain Models
# =============================================================================


class NormalizedRow(BaseModel):
    """
    Normalized product data from file parser.

    Standard format for parsed supplier items before database insertion.
    All parsers (Excel, PDF, CSV) output this format.

    Extended in Phase 10 with:
    - Dual pricing (retail_price, wholesale_price)
    - Currency code (ISO 4217)
    - Category path hierarchy
    - Raw composite string preservation

    Attributes:
        name: Product name (required)
        description: Optional product description
        price: Product price (deprecated, use retail_price)
        retail_price: End-customer retail price
        wholesale_price: Dealer/bulk wholesale price
        currency_code: ISO 4217 currency code
        sku: Supplier's SKU for this item
        category: Product category (deprecated, use category_path)
        category_path: Hierarchical category path
        unit: Unit of measure (e.g., 'шт', 'кг', 'м')
        brand: Brand name if detected
        characteristics: Additional key-value attributes
        raw_composite: Original composite string before parsing
        raw_data: Original row data for debugging
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Shtenli Model Gt11",
                "description": "Li-ion 48V 15Ah electric bicycle",
                "price": 85000.00,  # Deprecated: use retail_price
                "retail_price": 95000.00,
                "wholesale_price": 85000.00,
                "currency_code": "RUB",
                "sku": "SHTGT11-48V",
                "category": "Electric Bicycle",  # Deprecated: use category_path
                "category_path": ["Electric Bicycle", "Adult"],
                "unit": "шт",
                "brand": "Shtenli",
                "characteristics": {"voltage": "48V", "battery": "15Ah"},
                "raw_composite": "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah",
                "raw_data": {"col_a": "SHTGT11-48V", "col_b": "..."},
            }
        }
    )

    # Core fields
    name: Annotated[
        str,
        Field(min_length=1, max_length=500, description="Product name"),
    ]
    description: Annotated[
        str | None,
        Field(default=None, max_length=2000, description="Product description"),
    ] = None

    # Pricing fields (Phase 10)
    price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="Product price (deprecated, use retail_price)"),
    ] = None
    retail_price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="End-customer retail price"),
    ] = None
    wholesale_price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="Dealer/bulk wholesale price"),
    ] = None
    currency_code: Annotated[
        str | None,
        Field(default=None, min_length=3, max_length=3, description="ISO 4217 currency code"),
    ] = None

    # Identification
    sku: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Supplier SKU"),
    ] = None

    # Category fields (Phase 10)
    category: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Product category (deprecated, use category_path)"),
    ] = None
    category_path: Annotated[
        list[str],
        Field(default_factory=list, description="Hierarchical category path"),
    ]

    # Additional fields
    unit: Annotated[
        str | None,
        Field(default=None, max_length=50, description="Unit of measure"),
    ] = None
    brand: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Brand name"),
    ] = None
    characteristics: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Additional attributes"),
    ]

    # Raw data preservation (Phase 10)
    raw_composite: Annotated[
        str | None,
        Field(default=None, max_length=1000, description="Original composite string before parsing"),
    ] = None
    raw_data: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="Original row data for debugging"),
    ] = None

    @model_validator(mode="after")
    def sync_deprecated_fields(self) -> Self:
        """
        Sync deprecated fields with new fields for backward compatibility.

        This ensures that:
        - `price` and `retail_price` stay in sync
        - `category` and `category_path` stay in sync

        The sync is bidirectional: if one is set but not the other,
        the value is copied to maintain compatibility with older code.
        """
        # Sync retail_price <-> price (deprecated)
        if self.retail_price is not None and self.price is None:
            object.__setattr__(self, "price", self.retail_price)
        elif self.price is not None and self.retail_price is None:
            object.__setattr__(self, "retail_price", self.price)

        # Sync category_path <-> category (deprecated)
        if self.category_path and not self.category:
            object.__setattr__(self, "category", self.category_path[0])
        elif self.category and not self.category_path:
            object.__setattr__(self, "category_path", [self.category])

        return self


class MatchResult(BaseModel):
    """
    Result of LLM-based product matching.

    Represents a potential match between a supplier item and catalog product.

    Attributes:
        product_id: ID of the matched product
        product_name: Name of the matched product
        confidence: Match confidence score (0.0-1.0)
        reasoning: LLM's reasoning for the match
        similarity_score: Vector similarity score (cosine)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_name": "Батарейка AA Duracell",
                "confidence": 0.92,
                "reasoning": "Same product: AA alkaline battery from same brand",
                "similarity_score": 0.89,
            }
        }
    )

    product_id: Annotated[
        UUID,
        Field(description="ID of the matched catalog product"),
    ]
    product_name: Annotated[
        str,
        Field(description="Name of the matched product"),
    ]
    confidence: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Match confidence (0-1)"),
    ]
    reasoning: Annotated[
        str,
        Field(description="LLM's reasoning for the match"),
    ]
    similarity_score: Annotated[
        float,
        Field(ge=0.0, le=1.0, description="Vector cosine similarity"),
    ]


class ProductEmbeddingData(BaseModel):
    """
    Data transfer object for product embeddings.

    Used for passing embedding data between services.

    Attributes:
        id: Embedding record ID
        supplier_item_id: Reference to supplier item
        embedding: 768-dimensional vector
        model_name: Name of embedding model used
        created_at: Creation timestamp
    """

    model_config = ConfigDict(
        from_attributes=True,  # Allow SQLAlchemy model conversion
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "supplier_item_id": "660e8400-e29b-41d4-a716-446655440001",
                "embedding": [0.1, -0.2, 0.3],
                "model_name": "nomic-embed-text",
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )

    id: Annotated[UUID, Field(description="Embedding record ID")]
    supplier_item_id: Annotated[UUID, Field(description="Supplier item reference")]
    embedding: Annotated[list[float], Field(description="768-dim vector")]
    model_name: Annotated[str, Field(description="Embedding model name")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]


class SimilarityResult(BaseModel):
    """
    Result from vector similarity search.

    Contains a matched item and its similarity score.

    Attributes:
        supplier_item_id: ID of similar item
        product_id: Product ID if item is matched
        name: Item name
        similarity: Cosine similarity score (0-1)
        characteristics: Item characteristics
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_item_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "Батарейка AA Alkaline",
                "similarity": 0.92,
                "characteristics": {"voltage": "1.5V"},
            }
        }
    )

    supplier_item_id: Annotated[UUID, Field(description="Similar item ID")]
    product_id: Annotated[UUID | None, Field(description="Matched product ID")]
    name: Annotated[str, Field(description="Item name")]
    similarity: Annotated[float, Field(ge=0.0, le=1.0, description="Cosine similarity")]
    characteristics: Annotated[dict[str, Any], Field(default_factory=dict)]


class ChunkData(BaseModel):
    """
    Semantic chunk for embedding.

    Represents a processed text chunk ready for embedding generation.

    Attributes:
        text: Concatenated text content
        supplier_item_id: Source item ID (if from existing item)
        metadata: Additional context for the chunk
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Батарейка AA Alkaline 1.5V Duracell",
                "supplier_item_id": "550e8400-e29b-41d4-a716-446655440000",
                "metadata": {"category": "Батарейки", "brand": "Duracell"},
            }
        }
    )

    text: Annotated[
        str,
        Field(min_length=1, max_length=8192, description="Chunk text content"),
    ]
    supplier_item_id: Annotated[
        UUID | None,
        Field(default=None, description="Source supplier item ID"),
    ] = None
    metadata: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Chunk metadata"),
    ]


class FileAnalysisJob(BaseModel):
    """
    Job message for file analysis queue.

    Sent to arq queue for background processing.

    Attributes:
        job_id: Unique job identifier
        file_url: URL or path to file
        supplier_id: Supplier ID
        file_type: File type (pdf, excel, csv)
        created_at: Job creation timestamp
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_url": "/shared/uploads/price-list.xlsx",
                "supplier_id": "660e8400-e29b-41d4-a716-446655440001",
                "file_type": "excel",
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )

    job_id: Annotated[UUID, Field(description="Job identifier")]
    file_url: Annotated[str, Field(description="File URL or path")]
    supplier_id: Annotated[UUID, Field(description="Supplier ID")]
    file_type: Annotated[str, Field(description="File type")]
    created_at: Annotated[datetime, Field(description="Job creation time")]


class MatchJob(BaseModel):
    """
    Job message for batch matching queue.

    Sent to arq queue for background matching.

    Attributes:
        job_id: Unique job identifier
        supplier_item_ids: Items to match
        created_at: Job creation timestamp
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "supplier_item_ids": [
                    "660e8400-e29b-41d4-a716-446655440001",
                    "770e8400-e29b-41d4-a716-446655440002",
                ],
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )

    job_id: Annotated[UUID, Field(description="Job identifier")]
    supplier_item_ids: Annotated[list[UUID], Field(description="Items to match")]
    created_at: Annotated[datetime, Field(description="Job creation time")]

