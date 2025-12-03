"""
SQLAlchemy ORM Models for ML-Analyze Service
=============================================

Defines database models for vector embeddings storage.
Uses pgvector extension for efficient similarity search.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass  # Future: Add SupplierItem relationship if needed


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ProductEmbedding(Base, UUIDMixin, TimestampMixin):
    """
    Product embedding model for vector similarity search.

    Stores semantic embeddings generated from product descriptions.
    Uses pgvector's vector type for efficient cosine similarity queries.

    Attributes:
        id: Unique identifier (UUID)
        supplier_item_id: Reference to the supplier_items table
        embedding: 768-dimensional vector embedding
        model_name: Name of the embedding model used (e.g., nomic-embed-text)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update

    Indexes:
        - IVFFLAT index on embedding for fast cosine similarity search
        - B-tree index on supplier_item_id for lookups
        - B-tree index on model_name for filtering

    Constraints:
        - Unique constraint on (supplier_item_id, model_name)
    """

    __tablename__ = "product_embeddings"

    supplier_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("supplier_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=True,
        doc="768-dimensional vector embedding from nomic-embed-text",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default="nomic-embed-text",
        index=True,
        doc="Name of the embedding model used",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<ProductEmbedding("
            f"id={self.id}, "
            f"supplier_item_id={self.supplier_item_id}, "
            f"model={self.model_name})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "supplier_item_id": str(self.supplier_item_id),
            "embedding": self.embedding,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

