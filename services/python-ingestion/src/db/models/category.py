"""Category ORM model with self-referential hierarchy and semantic ETL support."""
from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint, func, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.db.models.product import Product
    from src.db.models.supplier import Supplier
    from src.db.models.supplier_item import SupplierItem


class Category(Base, UUIDMixin):
    """Category model with self-referential parent-child relationships.
    
    Phase 9 additions:
        - needs_review: Flag for admin review queue (semantic ETL)
        - is_active: Soft delete flag
        - supplier_id: Original supplier that created this category
        - updated_at: Last update timestamp
    """
    
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint('name', 'parent_id', name='uq_category_name_parent'),
        CheckConstraint('id != parent_id', name='chk_no_self_reference'),
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Phase 9: Semantic ETL governance fields
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default='false',
        index=True,
        doc="Flag for admin review queue (semantic ETL)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default='true',
        index=True,
        doc="Soft delete flag"
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Original supplier that created this category"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        remote_side="Category.id",
        back_populates="children",
        foreign_keys=[parent_id]
    )
    children: Mapped[List["Category"]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_id]
    )
    products: Mapped[List["Product"]] = relationship(
        back_populates="category"
    )
    supplier: Mapped[Optional["Supplier"]] = relationship(
        back_populates="categories"
    )
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="category"
    )
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', needs_review={self.needs_review})>"

