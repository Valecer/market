"""
Pydantic Request Models
=======================

API request schemas for ml-analyze service endpoints.
All incoming data validated via these models.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class FileAnalysisRequest(BaseModel):
    """
    Request body for POST /analyze/file endpoint.

    Triggers file parsing and analysis pipeline.

    Extended in Phase 10 with:
    - file_path: Direct path to file in shared volume (preferred)
    - file_url: HTTP URL or file:// path (deprecated, for backward compatibility)
    - default_currency: Fallback ISO 4217 currency code
    - composite_delimiter: Delimiter for composite name parsing

    Attributes:
        file_path: Path to file in shared volume (e.g., /shared/uploads/file.xlsx)
        file_url: HTTP URL or file:// path (deprecated, use file_path)
        supplier_id: ID of the supplier owning the file
        file_type: Type of file (pdf, excel, csv)
        default_currency: Default ISO 4217 currency if not detected
        composite_delimiter: Delimiter for composite product names
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "/shared/uploads/supplier_123_20251203_price-list.xlsx",
                "supplier_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_type": "excel",
                "default_currency": "RUB",
                "composite_delimiter": "|",
            }
        }
    )

    # NEW: Direct file path (preferred for Phase 8 courier integration)
    file_path: Annotated[
        str | None,
        Field(
            default=None,
            description="Path to file in shared volume (e.g., /shared/uploads/file.xlsx)",
            examples=["/shared/uploads/supplier-data.xlsx"],
        ),
    ] = None

    # Existing: URL-based (deprecated but supported for backward compatibility)
    file_url: Annotated[
        HttpUrl | str | None,
        Field(
            default=None,
            description="HTTP URL or file:// path (deprecated, use file_path)",
            examples=[
                "https://example.com/price-list.pdf",
                "file:///shared/uploads/supplier-data.xlsx",
            ],
            deprecated=True,
        ),
    ] = None

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

    # NEW: Parsing options (Phase 10)
    default_currency: Annotated[
        str | None,
        Field(
            default=None,
            min_length=3,
            max_length=3,
            pattern=r"^[A-Z]{3}$",
            description="Default ISO 4217 currency code if not detected in document",
            examples=["RUB", "USD", "EUR"],
        ),
    ] = None

    composite_delimiter: Annotated[
        str,
        Field(
            default="|",
            min_length=1,
            max_length=5,
            description="Delimiter for parsing composite product name strings",
            examples=["|", " | ", "->"],
        ),
    ] = "|"

    @model_validator(mode="after")
    def require_file_source(self) -> Self:
        """
        Ensure at least one file source is provided.

        Either file_path or file_url must be specified.
        file_path takes precedence if both are provided.
        """
        if not self.file_path and not self.file_url:
            raise ValueError("Either file_path or file_url must be provided")
        return self

    @property
    def effective_file_source(self) -> str:
        """
        Get the effective file source, preferring file_path over file_url.

        Returns:
            str: The file path or URL to use for analysis
        """
        if self.file_path:
            return self.file_path
        return str(self.file_url)


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

