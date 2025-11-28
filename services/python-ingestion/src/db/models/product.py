"""Product ORM model with status enum."""
from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from enum import Enum as PyEnum
from typing import List, Optional
import uuid


class ProductStatus(PyEnum):
    """Product lifecycle status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Product(Base, UUIDMixin, TimestampMixin):
    """Product model representing internal unified catalog."""
    
    __tablename__ = "products"
    
    internal_sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus, name="product_status", create_constraint=True),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
        index=True
    )
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.internal_sku}', status='{self.status.value}')>"

