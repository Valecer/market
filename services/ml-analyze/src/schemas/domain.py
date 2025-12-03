"""
Domain Models
=============

Internal domain models representing business entities.
Used for data transfer between services and components.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NormalizedRow(BaseModel):
    """
    Normalized product data from file parser.

    Standard format for parsed supplier items before database insertion.
    All parsers (Excel, PDF, CSV) output this format.

    Attributes:
        name: Product name (required)
        description: Optional product description
        price: Product price (optional, may be None if not parseable)
        sku: Supplier's SKU for this item
        category: Product category if detected
        unit: Unit of measure (e.g., 'шт', 'кг', 'м')
        brand: Brand name if detected
        characteristics: Additional key-value attributes
        raw_data: Original row data for debugging
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Батарейка AA Alkaline 1.5V",
                "description": "Щелочная батарейка типа АА",
                "price": 25.50,
                "sku": "BAT-AA-001",
                "category": "Батарейки",
                "unit": "шт",
                "brand": "Duracell",
                "characteristics": {"voltage": "1.5V", "type": "alkaline"},
                "raw_data": {"col_a": "BAT-AA-001", "col_b": "Батарейка..."},
            }
        }
    )

    name: Annotated[
        str,
        Field(min_length=1, max_length=500, description="Product name"),
    ]
    description: Annotated[
        str | None,
        Field(default=None, max_length=2000, description="Product description"),
    ] = None
    price: Annotated[
        Decimal | None,
        Field(default=None, ge=0, description="Product price"),
    ] = None
    sku: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Supplier SKU"),
    ] = None
    category: Annotated[
        str | None,
        Field(default=None, max_length=255, description="Product category"),
    ] = None
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
    ] = {}
    raw_data: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="Original row data for debugging"),
    ] = None


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
    ] = {}


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

