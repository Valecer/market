"""MatchReviewQueue ORM model for pending match reviews."""
from sqlalchemy import String, ForeignKey, func, DateTime, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base, UUIDMixin
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from enum import Enum as PyEnum
import uuid

if TYPE_CHECKING:
    from src.db.models.supplier_item import SupplierItem


class ReviewStatus(PyEnum):
    """Status of a review queue item.
    
    States:
        - pending: Awaiting review
        - approved: Match approved by user
        - rejected: Match rejected, creates new product
        - expired: Auto-expired after MATCH_REVIEW_EXPIRATION_DAYS
        - needs_category: Item has no category, can't be matched
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NEEDS_CATEGORY = "needs_category"


class MatchReviewQueue(Base, UUIDMixin):
    """MatchReviewQueue model for supplier items requiring human review.
    
    Potential matches (score 70-94%) are added to this queue for human review.
    Users can approve a suggested match, reject to create a new product, or
    items can auto-expire after a configurable period.
    
    Attributes:
        supplier_item_id: Reference to the supplier item (unique - one review per item)
        candidate_products: JSONB array of potential matches [{product_id, score, name}]
        status: Current review status
        reviewed_by: User who actioned the review (if completed)
        reviewed_at: Timestamp when review was completed
        created_at: When item was added to queue
        expires_at: When item will auto-expire
    
    Relationships:
        supplier_item: Reference to the SupplierItem being reviewed
        reviewer: Reference to the User who reviewed (if any)
    """
    
    __tablename__ = "match_review_queue"
    
    supplier_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        doc="Reference to supplier item (unique - one review per item)"
    )
    candidate_products: Mapped[Dict[str, Any]] = mapped_column(
        postgresql.JSONB(astext_type=Text),
        nullable=False,
        server_default='[]',
        doc="Array of potential matches [{product_id, score, name}]"
    )
    # Note: values_callable ensures SQLAlchemy uses enum VALUES (lowercase strings)
    # instead of enum NAMES (uppercase) to match PostgreSQL enum values
    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(
            ReviewStatus,
            name="review_status",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
        index=True,
        doc="Current review status"
    )
    # Note: FK constraint exists in DB but not modeled here since User model 
    # is managed by Bun API. Just store the UUID reference.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
        doc="User who actioned the review (FK to users.id in DB)"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when review was completed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="When item was added to queue"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="When item will auto-expire"
    )
    
    # Relationships
    supplier_item: Mapped["SupplierItem"] = relationship(
        back_populates="review_queue_item"
    )
    # Note: reviewer relationship would require User model import
    # For now we just store the UUID reference
    
    def __repr__(self) -> str:
        return f"<MatchReviewQueue(id={self.id}, status='{self.status.value}')>"

