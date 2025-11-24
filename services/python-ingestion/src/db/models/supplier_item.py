"""SupplierItem ORM model with JSONB characteristics."""
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, UniqueConstraint, func, DateTime, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid


class SupplierItem(Base, UUIDMixin, TimestampMixin):
    """SupplierItem model representing raw product data from suppliers."""
    
    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint('supplier_id', 'supplier_sku', name='unique_supplier_sku'),
        CheckConstraint('current_price >= 0', name='check_positive_price'),
    )
    
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    supplier_sku: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        index=True
    )
    characteristics: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB(astext_type=Text),
        nullable=False,
        server_default="{}"
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="supplier_items")
    price_history: Mapped[List["PriceHistory"]] = relationship(
        back_populates="supplier_item",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<SupplierItem(id={self.id}, sku='{self.supplier_sku}', price={self.current_price})>"

