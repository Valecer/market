"""PriceHistory ORM model for time-series price tracking."""
from sqlalchemy import ForeignKey, Numeric, CheckConstraint, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from decimal import Decimal
from datetime import datetime
import uuid


class PriceHistory(Base, UUIDMixin):
    """PriceHistory model tracking price changes over time."""
    
    __tablename__ = "price_history"
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_positive_price'),
    )
    
    supplier_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    supplier_item: Mapped["SupplierItem"] = relationship(back_populates="price_history")
    
    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, price={self.price}, recorded_at={self.recorded_at})>"

