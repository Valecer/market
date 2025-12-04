"""
Pydantic Request Models
=======================

API request schemas for ml-analyze service endpoints.
All incoming data validated via these models.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FileAnalysisRequest(BaseModel):
    """
    Request body for POST /analyze/file endpoint.

    Triggers file parsing and analysis pipeline (semantic ETL).
    
    Phase 9: Enhanced for LLM-based extraction with category normalization.

    Attributes:
        file_url: URL or path to the file to analyze
        supplier_id: ID of the supplier owning the file
        file_type: Type of file (pdf, excel, csv)
        use_semantic_etl: Whether to use LLM-based extraction (default: true)
        priority_sheet: Optional sheet name to prioritize
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_url": "/shared/uploads/supplier_123_pricelist.xlsx",
                "supplier_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_type": "excel",
                "use_semantic_etl": True,
                "priority_sheet": "Upload to site",
            }
        }
    )

    file_url: Annotated[
        HttpUrl | str,
        Field(
            description="HTTP URL, file:// path, or absolute path to the file",
            examples=[
                "https://example.com/price-list.pdf",
                "file:///shared/uploads/supplier-data.xlsx",
                "/shared/uploads/supplier-data.xlsx",
            ],
        ),
    ]
    supplier_id: Annotated[
        UUID,
        Field(
            description="UUID of the supplier this file belongs to",
        ),
    ]
    file_type: Annotated[
        Literal["pdf", "excel", "csv"],
        Field(
            description="Type of file being analyzed",
        ),
    ]
    use_semantic_etl: Annotated[
        bool,
        Field(
            default=True,
            description="Use LLM-based semantic extraction (Phase 9). "
            "Set to false to use legacy parsing.",
        ),
    ] = True
    priority_sheet: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional sheet name to prioritize for processing. "
            "If not specified, uses smart sheet selection.",
            examples=["Upload to site", "Products", "Товары"],
        ),
    ] = None


class BatchMatchRequest(BaseModel):
    """
    Request body for POST /analyze/merge endpoint.

    Triggers batch matching for unlinked supplier items.

    Attributes:
        supplier_item_ids: List of item IDs to match (optional, matches all if empty)
        supplier_id: Filter by supplier (optional)
        limit: Maximum number of items to process
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "supplier_item_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "223e4567-e89b-12d3-a456-426614174001",
                ],
                "supplier_id": None,
                "limit": 100,
            }
        }
    )

    supplier_item_ids: Annotated[
        list[UUID] | None,
        Field(
            default=None,
            description="Specific item IDs to match. If empty, matches all unmatched items.",
        ),
    ] = None
    supplier_id: Annotated[
        UUID | None,
        Field(
            default=None,
            description="Filter items by supplier ID",
        ),
    ] = None
    limit: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of items to process in this batch",
        ),
    ] = 100


class VisionAnalysisRequest(BaseModel):
    """
    Request body for POST /analyze/vision endpoint (stub).

    Placeholder for future image/photo processing.

    Attributes:
        image_url: URL or path to the image
        supplier_id: ID of the supplier owning the image
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image_url": "https://storage.example.com/images/price-tag.jpg",
                "supplier_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
    )

    image_url: Annotated[
        HttpUrl | str,
        Field(
            description="URL or path to the image file",
        ),
    ]
    supplier_id: Annotated[
        UUID,
        Field(
            description="UUID of the supplier this image belongs to",
        ),
    ]


class EmbeddingRequest(BaseModel):
    """
    Request for generating text embeddings.

    Internal use for vector service.

    Attributes:
        text: Text to embed
        model: Embedding model name
    """

    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=8192,
            description="Text to generate embedding for",
        ),
    ]
    model: Annotated[
        str,
        Field(
            default="nomic-embed-text",
            description="Embedding model to use",
        ),
    ] = "nomic-embed-text"


class SimilaritySearchRequest(BaseModel):
    """
    Request for similarity search.

    Internal use for vector service.

    Attributes:
        embedding: Query embedding vector
        top_k: Number of results to return
        threshold: Minimum similarity threshold
    """

    embedding: Annotated[
        list[float],
        Field(
            description="768-dimensional embedding vector",
            min_length=768,
            max_length=768,
        ),
    ]
    top_k: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=100,
            description="Number of similar items to return",
        ),
    ] = 5
    threshold: Annotated[
        float,
        Field(
            default=0.0,
            ge=0.0,
            le=1.0,
            description="Minimum cosine similarity threshold",
        ),
    ] = 0.0

