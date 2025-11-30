"""Pydantic models for product matching pipeline.

This module defines the data transfer objects and validation models
for the product matching workflow.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class MatchStatusEnum(str, Enum):
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


class MatchCandidate(BaseModel):
    """A potential product match for a supplier item.
    
    Attributes:
        product_id: UUID of the candidate product
        product_name: Name of the candidate product for display
        score: Fuzzy match confidence score (0-100)
        category_id: Optional category for blocking verification
    """
    
    product_id: UUID
    product_name: str = Field(..., max_length=500)
    score: float = Field(..., ge=0, le=100, description="Match confidence score 0-100")
    category_id: Optional[UUID] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_name": "Samsung Galaxy A54 5G 128GB",
                "score": 92.5,
                "category_id": "660e8400-e29b-41d4-a716-446655440000"
            }
        }
    }


class MatchResult(BaseModel):
    """Result of matching a supplier item against products.
    
    Attributes:
        supplier_item_id: UUID of the supplier item that was matched
        match_status: Resulting status after matching
        best_match: Top candidate (if any)
        candidates: All candidates above potential threshold
        match_score: Score of best match (if any)
    """
    
    supplier_item_id: UUID
    match_status: MatchStatusEnum
    best_match: Optional[MatchCandidate] = None
    candidates: List[MatchCandidate] = Field(default_factory=list)
    match_score: Optional[float] = Field(default=None, ge=0, le=100)
    
    @field_validator('best_match', mode='before')
    @classmethod
    def validate_best_match_required(cls, v, info):
        """Ensure best_match is set for matched statuses."""
        status = info.data.get('match_status')
        if status in (MatchStatusEnum.AUTO_MATCHED, MatchStatusEnum.VERIFIED_MATCH):
            if v is None:
                raise ValueError('best_match is required for auto_matched or verified_match status')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "match_status": "auto_matched",
                "best_match": {
                    "product_id": "550e8400-e29b-41d4-a716-446655440000",
                    "product_name": "Samsung Galaxy A54 5G 128GB",
                    "score": 96.5
                },
                "candidates": [],
                "match_score": 96.5
            }
        }
    }


class MatchItemsTaskMessage(BaseModel):
    """Queue message for batch matching of supplier items.
    
    Attributes:
        task_id: Unique task identifier for tracking
        category_id: Optional category filter for blocking strategy
        batch_size: Number of items to process (1-1000)
        retry_count: Current retry attempt (0-indexed)
        max_retries: Maximum retry attempts before DLQ
        enqueued_at: Timestamp when task was enqueued
    """
    
    task_id: str = Field(..., description="Unique task identifier")
    category_id: Optional[UUID] = Field(
        default=None,
        description="Category filter for blocking strategy"
    )
    batch_size: int = Field(default=100, ge=1, le=1000)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "match-2025-11-30-001",
                "category_id": "660e8400-e29b-41d4-a716-446655440000",
                "batch_size": 100,
                "retry_count": 0,
                "max_retries": 3
            }
        }
    }


class EnrichItemTaskMessage(BaseModel):
    """Queue message for enriching supplier item characteristics.
    
    Attributes:
        task_id: Unique task identifier
        supplier_item_id: Item to enrich
        extractors: List of extractor names to apply
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        enqueued_at: Timestamp when task was enqueued
    """
    
    task_id: str = Field(..., description="Unique task identifier")
    supplier_item_id: UUID = Field(..., description="Supplier item to enrich")
    extractors: List[str] = Field(
        default=["electronics", "dimensions"],
        description="Extractor names to apply"
    )
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "enrich-2025-11-30-001",
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "extractors": ["electronics", "dimensions"]
            }
        }
    }


class RecalcAggregatesTaskMessage(BaseModel):
    """Queue message for recalculating product aggregates.
    
    Attributes:
        task_id: Unique task identifier
        product_ids: List of products to recalculate
        trigger: Event that triggered recalculation
        triggered_by: User who triggered (for manual actions)
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        enqueued_at: Timestamp when task was enqueued
    """
    
    task_id: str = Field(..., description="Unique task identifier")
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    trigger: str = Field(
        ...,
        description="Event trigger: auto_match, manual_link, manual_unlink, price_change"
    )
    triggered_by: Optional[UUID] = Field(
        default=None,
        description="User UUID for manual actions"
    )
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    @field_validator('trigger')
    @classmethod
    def validate_trigger(cls, v: str) -> str:
        """Validate trigger is a known event type."""
        valid_triggers = {'auto_match', 'manual_link', 'manual_unlink', 'price_change', 'availability_change'}
        if v not in valid_triggers:
            raise ValueError(f'trigger must be one of: {valid_triggers}')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "recalc-2025-11-30-001",
                "product_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "trigger": "auto_match"
            }
        }
    }


class ManualMatchEventMessage(BaseModel):
    """Queue message for manual link/unlink events from API.
    
    Attributes:
        event_id: Unique event identifier
        action: Type of manual action
        supplier_item_id: Affected supplier item
        product_id: Target product (for link action)
        previous_product_id: Previous product (for unlink tracking)
        user_id: User who performed the action
        timestamp: When the action occurred
    """
    
    event_id: str = Field(..., description="Unique event identifier")
    action: str = Field(
        ...,
        description="Action type: link, unlink, reset_match, approve_match, reject_match"
    )
    supplier_item_id: UUID
    product_id: Optional[UUID] = Field(
        default=None,
        description="Target product for link action"
    )
    previous_product_id: Optional[UUID] = Field(
        default=None,
        description="Previous product for unlink tracking"
    )
    user_id: UUID = Field(..., description="User who performed the action")
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is a known type."""
        valid_actions = {'link', 'unlink', 'reset_match', 'approve_match', 'reject_match'}
        if v not in valid_actions:
            raise ValueError(f'action must be one of: {valid_actions}')
        return v
    
    @field_validator('product_id', mode='before')
    @classmethod
    def validate_product_id_required_for_link(cls, v, info):
        """Ensure product_id is provided for link action."""
        action = info.data.get('action')
        if action == 'link' and v is None:
            raise ValueError('product_id is required for link action')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "evt-2025-11-30-001",
                "action": "link",
                "supplier_item_id": "770e8400-e29b-41d4-a716-446655440000",
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "880e8400-e29b-41d4-a716-446655440000"
            }
        }
    }

