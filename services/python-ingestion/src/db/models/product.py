"""Product ORM model with status enum and aggregate fields."""
from sqlalchemy import String, ForeignKey, Enum as SQLEnum, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from enum import Enum as PyEnum
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.db.models.category import Category
    from src.db.models.supplier_item import SupplierItem


class ProductStatus(PyEnum):
    """Product lifecycle status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Product(Base, UUIDMixin, TimestampMixin):
    """Product model representing internal unified catalog.
    
    Attributes:
        internal_sku: Unique internal SKU for the product
        name: Product display name
        category_id: Reference to category (optional)
        status: Product lifecycle status (draft, active, archived)
        min_price: Lowest price among linked active supplier items (Phase 4)
        availability: TRUE if any linked supplier has stock (Phase 4)
        mrp: Manufacturer's recommended price placeholder (Phase 4)
    
    Relationships:
        category: Reference to Category
        supplier_items: All linked supplier items
    """
    
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
    # Note: values_callable ensures SQLAlchemy uses enum VALUES (lowercase strings)
    # instead of enum NAMES (uppercase) to match PostgreSQL enum values
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(
            ProductStatus,
            name="product_status",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        server_default=ProductStatus.DRAFT.value,
        index=True
    )
    
    # Phase 4: Aggregate fields calculated from linked supplier items
    min_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        index=True,
        doc="Lowest price among linked active supplier items"
    )
    availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default='false',
        doc="TRUE if any linked supplier has stock"
    )
    mrp: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Manufacturer's recommended price (placeholder)"
    )
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.internal_sku}', status='{self.status.value}')>"
