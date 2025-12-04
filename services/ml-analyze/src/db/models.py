"""
SQLAlchemy ORM Models for ML-Analyze Service
=============================================

Defines database models for vector embeddings storage and category management.
Uses pgvector extension for efficient similarity search.

Phase 7: Product embeddings for RAG pipeline
Phase 9: Category model with hierarchy and review workflow
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass  # Future: Add SupplierItem relationship if needed


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped["UUID"] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )


class IntPKMixin:
    """Mixin for integer primary key."""

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
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


class Category(Base, IntPKMixin, TimestampMixin):
    """
    Category model with hierarchical structure and review workflow.
    
    Phase 9: Semantic ETL Pipeline - Category Governance
    
    Supports:
    - Self-referencing hierarchy (parent_id → categories.id)
    - Admin review workflow (needs_review flag)
    - Supplier tracking (which supplier introduced category)
    - Soft delete (is_active flag)
    
    Attributes:
        id: Category ID (integer primary key)
        name: Category name (required)
        parent_id: FK to parent category (NULL for root)
        needs_review: Flag for admin review queue
        is_active: Soft delete flag
        supplier_id: Supplier that introduced this category
        created_at: Creation timestamp
        updated_at: Last update timestamp
    
    Indexes:
        - idx_categories_parent_id: Parent category lookups
        - idx_categories_needs_review: Review queue filtering
        - idx_categories_supplier_id: Supplier filtering
    
    Constraints:
        - chk_no_self_reference: Prevent id = parent_id
    """

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Category name",
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Parent category ID (NULL for root categories)",
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        index=True,
        doc="Flag indicating category needs admin review",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Soft delete flag",
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Supplier that introduced this category",
    )

    # Self-referencing relationship for hierarchy
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        backref="children",
        foreign_keys=[parent_id],
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<Category("
            f"id={self.id}, "
            f"name={self.name!r}, "
            f"parent_id={self.parent_id}, "
            f"needs_review={self.needs_review})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "needs_review": self.needs_review,
            "is_active": self.is_active,
            "supplier_id": self.supplier_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_full_path(self) -> list[str]:
        """
        Get full category path from root to this category.
        
        Returns:
            List of category names from root to leaf, e.g.,
            ['Electronics', 'Laptops', 'Gaming Laptops']
        """
        path = [self.name]
        current = self.parent
        while current is not None:
            path.insert(0, current.name)
            current = current.parent
        return path

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """
        Normalize category name for comparison.
        
        Args:
            name: Raw category name
            
        Returns:
            Normalized name (lowercase, stripped, collapsed spaces)
        """
        return " ".join(name.strip().lower().split())

