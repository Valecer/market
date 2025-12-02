"""Pydantic models for the match review queue.

This module defines the data transfer objects for managing
potential matches that require human review.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime
from enum import Enum


class ReviewStatusEnum(str, Enum):
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


class CandidateProduct(BaseModel):
    """A candidate product in the review queue.
    
    Attributes:
        product_id: UUID of the candidate product
        product_name: Display name
        score: Match confidence score
    """
    
    product_id: UUID
    product_name: str = Field(..., max_length=500)
    score: float = Field(..., ge=0, le=100)


class ReviewQueueItem(BaseModel):
    """A supplier item in the review queue requiring human review.
    
    Attributes:
        id: Review queue entry UUID
        supplier_item_id: Reference to the supplier item
        supplier_item_name: Display name of supplier item
        supplier_name: Name of the supplier
        candidate_products: List of potential matches
        status: Current review status
        created_at: When item was added to queue
        expires_at: When item will auto-expire
        reviewed_by: User who reviewed (if actioned)
        reviewed_at: When review was completed
    """
    
    id: UUID
    supplier_item_id: UUID
    supplier_item_name: str = Field(..., max_length=500)
    supplier_name: str = Field(..., max_length=255)
    candidate_products: List[CandidateProduct]
    status: ReviewStatusEnum
    created_at: datetime
    expires_at: datetime
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "supplier_item_name": "Samsung A54 Phone Black 128",
                "supplier_name": "TechSupplier Inc",
                "candidate_products": [
                    {
                        "product_id": "550e8400-e29b-41d4-a716-446655440000",
                        "product_name": "Samsung Galaxy A54 5G 128GB",
                        "score": 78.5
                    }
                ],
                "status": "pending",
                "created_at": "2025-11-30T10:00:00Z",
                "expires_at": "2025-12-30T10:00:00Z"
            }
        }
    }


class ReviewAction(BaseModel):
    """Action to take on a review queue item.
    
    Attributes:
        action: Type of action (approve, reject, create_new)
        product_id: Product to link (required for 'approve')
        new_product_name: Name for new product (required for 'create_new')
    """
    
    action: Literal["approve", "reject", "create_new"]
    product_id: Optional[UUID] = Field(
        default=None,
        description="Product UUID to link (required for 'approve')"
    )
    new_product_name: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Name for new product (required for 'create_new')"
    )
    
    @field_validator('product_id', mode='before')
    @classmethod
    def validate_product_id_for_approve(cls, v, info):
        """Ensure product_id is provided for approve action."""
        action = info.data.get('action')
        if action == 'approve' and v is None:
            raise ValueError('product_id is required for approve action')
        return v
    
    @field_validator('new_product_name', mode='before')
    @classmethod
    def validate_name_for_create_new(cls, v, info):
        """Ensure new_product_name is provided for create_new action."""
        action = info.data.get('action')
        if action == 'create_new' and not v:
            raise ValueError('new_product_name is required for create_new action')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "action": "approve",
                "product_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    }


class ReviewQueueStats(BaseModel):
    """Statistics for the review queue.
    
    Attributes:
        total_pending: Total items awaiting review
        by_supplier: Counts grouped by supplier
        by_category: Counts grouped by category
        avg_score: Average match score in queue
        oldest_item_date: Date of oldest pending item
    """
    
    total_pending: int = Field(default=0, ge=0)
    by_supplier: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    avg_score: Optional[float] = Field(default=None, ge=0, le=100)
    oldest_item_date: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "total_pending": 42,
                "by_supplier": {
                    "Supplier A": 15,
                    "Supplier B": 27
                },
                "by_category": {
                    "Electronics": 20,
                    "Power Tools": 22
                },
                "avg_score": 82.5,
                "oldest_item_date": "2025-11-01T10:00:00Z"
            }
        }
    }


class ReviewQueueFilter(BaseModel):
    """Filter parameters for querying the review queue.
    
    Attributes:
        status: Filter by status
        supplier_id: Filter by supplier
        category_id: Filter by category
        min_score: Minimum match score
        max_score: Maximum match score
        created_after: Items created after this date
        created_before: Items created before this date
        limit: Maximum results to return
        offset: Pagination offset
    """
    
    status: Optional[ReviewStatusEnum] = None
    supplier_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    min_score: Optional[float] = Field(default=None, ge=0, le=100)
    max_score: Optional[float] = Field(default=None, ge=0, le=100)
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    
    @field_validator('max_score', mode='before')
    @classmethod
    def validate_score_range(cls, v, info):
        """Ensure max_score >= min_score if both are set."""
        min_score = info.data.get('min_score')
        if v is not None and min_score is not None and v < min_score:
            raise ValueError('max_score must be >= min_score')
        return v

