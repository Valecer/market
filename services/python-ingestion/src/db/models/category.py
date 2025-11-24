"""Category ORM model with self-referential hierarchy."""
from sqlalchemy import String, ForeignKey, UniqueConstraint, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import List, Optional
import uuid


class Category(Base, UUIDMixin):
    """Category model with self-referential parent-child relationships."""
    
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint('name', 'parent_id', name='uq_category_name_parent'),
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
    
    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        remote_side="Category.id",
        back_populates="children"
    )
    children: Mapped[List["Category"]] = relationship(
        back_populates="parent"
    )
    products: Mapped[List["Product"]] = relationship(
        back_populates="category"
    )
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"

