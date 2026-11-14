"""
Duplicate detection schemas
---------------------------

Pydantic models for potential duplicate creation and reporting.

Phase 2: Foundational duplicate types
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PotentialDuplicateCreate(BaseModel):
    """Payload for flagging a potential duplicate pair."""

    product_id_1: UUID
    product_id_2: UUID
    similarity_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Name similarity score (0-100)",
    )
    detection_reason: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Why the pair was flagged (e.g., auto_creation_similarity)",
    )


class PotentialDuplicateResponse(BaseModel):
    """Response representation of a potential duplicate."""

    id: UUID
    product_id_1: UUID
    product_id_2: UUID
    similarity_score: float
    detection_reason: str
    status: Literal["pending", "merged", "dismissed"]
    created_at: datetime


class DuplicateDetectionStats(BaseModel):
    """Aggregate statistics for duplicate detection runs."""

    duplicates_flagged: int = Field(
        ...,
        ge=0,
        description="Total duplicates flagged in the run",
    )
    false_positives_estimated: int = Field(
        ...,
        ge=0,
        description="Estimated false positives based on sampling",
    )


__all__ = [
    "PotentialDuplicateCreate",
    "PotentialDuplicateResponse",
    "DuplicateDetectionStats",
]
