"""Supplier ORM model with semantic ETL feature flag."""
from sqlalchemy import String, CheckConstraint, Text, Boolean
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.models.supplier_item import SupplierItem
    from src.db.models.parsing_log import ParsingLog
    from src.db.models.category import Category


class Supplier(Base, UUIDMixin, TimestampMixin):
    """Supplier model representing external data sources.
    
    Phase 9 additions:
        - use_semantic_etl: Feature flag to enable LLM-based extraction for this supplier
    """
    
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('google_sheets', 'csv', 'excel')",
            name="check_source_type"
        ),
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Use 'meta' as Python attribute name, but map to 'metadata' column in database
    meta: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB(astext_type=Text),
        nullable=False,
        server_default="{}"
    )
    
    # Phase 9: Semantic ETL feature flag
    use_semantic_etl: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default='false',
        index=True,
        doc="Enable semantic ETL for this supplier"
    )
    
    # Relationships
    supplier_items: Mapped[List["SupplierItem"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan"
    )
    parsing_logs: Mapped[List["ParsingLog"]] = relationship(
        back_populates="supplier"
    )
    categories: Mapped[List["Category"]] = relationship(
        back_populates="supplier"
    )
    
    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name='{self.name}', use_semantic_etl={self.use_semantic_etl})>"

