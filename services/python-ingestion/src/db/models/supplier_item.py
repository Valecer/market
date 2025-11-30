"""SupplierItem ORM model with JSONB characteristics and matching fields."""
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, UniqueConstraint, func, DateTime, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin, TimestampMixin
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from enum import Enum as PyEnum
import uuid

if TYPE_CHECKING:
    from src.db.models.supplier import Supplier
    from src.db.models.product import Product
    from src.db.models.price_history import PriceHistory
    from src.db.models.match_review_queue import MatchReviewQueue


class MatchStatus(PyEnum):
    """Match status for supplier items.
    
    State Transitions:
        - unmatched → auto_matched (system: score ≥95%)
        - unmatched → potential_match (system: score 70-94%)
        - unmatched → verified_match (admin: manual link)
        - potential_match → verified_match (admin: approve review)
        - potential_match → unmatched (admin: reject, creates new product)
        - auto_matched → verified_match (admin: confirm match)
        - auto_matched → unmatched (admin: reject match)
        - verified_match → unmatched (admin only: reset for re-matching)
    """
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    POTENTIAL_MATCH = "potential_match"
    VERIFIED_MATCH = "verified_match"


class SupplierItem(Base, UUIDMixin, TimestampMixin):
    """SupplierItem model representing raw product data from suppliers.
    
    Attributes:
        supplier_id: Reference to the supplier
        product_id: Reference to matched product (nullable)
        supplier_sku: Supplier's SKU for this item
        name: Product name from supplier
        current_price: Current price from supplier
        characteristics: JSONB field for flexible attributes
        last_ingested_at: Timestamp of last data ingestion
        match_status: Current matching state (Phase 4)
        match_score: Confidence score of last match 0-100 (Phase 4)
        match_candidates: Array of potential matches for review (Phase 4)
    
    Relationships:
        supplier: Reference to Supplier
        product: Reference to matched Product (if linked)
        price_history: Historical price records
        review_queue_item: Reference to review queue entry (if pending)
    """
    
    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint('supplier_id', 'supplier_sku', name='unique_supplier_sku'),
        CheckConstraint('current_price >= 0', name='check_positive_price'),
        CheckConstraint(
            'match_score IS NULL OR (match_score >= 0 AND match_score <= 100)',
            name='check_match_score'
        ),
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
    
    # Phase 4: Matching fields
    match_status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus, name="match_status", create_constraint=False),
        nullable=False,
        server_default=MatchStatus.UNMATCHED.value,
        index=True,
        doc="Current matching state"
    )
    match_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Confidence score of last match (0-100)"
    )
    match_candidates: Mapped[Dict[str, Any] | None] = mapped_column(
        postgresql.JSONB(astext_type=Text),
        nullable=True,
        doc="Array of potential matches [{product_id, product_name, score}]"
    )
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="supplier_items")
    price_history: Mapped[List["PriceHistory"]] = relationship(
        back_populates="supplier_item",
        cascade="all, delete-orphan"
    )
    review_queue_item: Mapped[Optional["MatchReviewQueue"]] = relationship(
        back_populates="supplier_item",
        uselist=False
    )
    
    def __repr__(self) -> str:
        return f"<SupplierItem(id={self.id}, sku='{self.supplier_sku}', status='{self.match_status.value}')>"
