"""
Category Schemas for Semantic ETL Pipeline
==========================================

Pydantic models for category matching and normalization.
Defines contracts for fuzzy matching results and category governance.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CategoryMatchResult(BaseModel):
    """
    Result of category fuzzy matching.
    
    Captures the outcome of matching an extracted category name
    against existing categories in the database using RapidFuzz.
    
    Attributes:
        extracted_name: Original category name from LLM extraction
        matched_id: ID of matched existing category (None if new)
        matched_name: Name of matched existing category (None if new)
        similarity_score: Fuzzy match similarity score (0-100)
        action: Action taken: 'matched', 'created', or 'skipped'
        needs_review: Flag indicating admin review required
        parent_id: Parent category ID in hierarchy
    """
    
    extracted_name: str = Field(
        ...,
        description="Original category name from LLM extraction"
    )
    matched_id: Optional[int] = Field(
        None,
        description="ID of matched existing category (if found)"
    )
    matched_name: Optional[str] = Field(
        None,
        description="Name of matched existing category (if found)"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Fuzzy match similarity score (0-100)"
    )
    action: str = Field(
        ...,
        description="Action taken: 'matched' | 'created' | 'skipped'"
    )
    needs_review: bool = Field(
        default=False,
        description="Flag indicating if category needs admin review"
    )
    parent_id: Optional[int] = Field(
        None,
        description="Parent category ID in hierarchy"
    )
    created_category_id: Optional[int] = Field(
        None,
        description="ID of newly created category (if action='created')"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of allowed values."""
        allowed = {"matched", "created", "skipped"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v

    @property
    def is_new_category(self) -> bool:
        """Check if a new category was created."""
        return self.action == "created"

    @property
    def is_confident_match(self) -> bool:
        """Check if match confidence is high (>90%)."""
        return self.similarity_score > 90.0

    @property
    def final_category_id(self) -> Optional[int]:
        """Get the final category ID (matched or created)."""
        if self.action == "matched":
            return self.matched_id
        elif self.action == "created":
            return self.created_category_id
        return None


class CategoryHierarchyResult(BaseModel):
    """
    Result of processing a full category hierarchy.
    
    When LLM returns ['Electronics', 'Laptops', 'Gaming'],
    this captures the match/creation result for each level.
    """
    
    original_path: list[str] = Field(
        ...,
        description="Original category path from LLM"
    )
    match_results: list[CategoryMatchResult] = Field(
        default_factory=list,
        description="Match result for each level of hierarchy"
    )
    leaf_category_id: Optional[int] = Field(
        None,
        description="ID of the leaf (most specific) category"
    )
    
    @property
    def all_matched(self) -> bool:
        """Check if all categories in hierarchy were matched (not created)."""
        return all(r.action == "matched" for r in self.match_results)
    
    @property
    def any_needs_review(self) -> bool:
        """Check if any category in hierarchy needs admin review."""
        return any(r.needs_review for r in self.match_results)
    
    @property
    def categories_created(self) -> int:
        """Count of new categories created in this hierarchy."""
        return sum(1 for r in self.match_results if r.action == "created")


class CategoryDTO(BaseModel):
    """
    Category Data Transfer Object.
    
    Represents a category entity for API responses
    and internal transfers.
    """
    
    id: int = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    parent_id: Optional[int] = Field(None, description="Parent category ID")
    needs_review: bool = Field(default=False, description="Admin review flag")
    is_active: bool = Field(default=True, description="Active status")
    supplier_id: Optional[int] = Field(
        None,
        description="Supplier that introduced this category"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class CategoryReviewItem(BaseModel):
    """
    Category item for admin review workflow.
    
    Includes additional context like parent name,
    supplier name, and product count for review UI.
    """
    
    id: int = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    parent_id: Optional[int] = Field(None, description="Parent category ID")
    parent_name: Optional[str] = Field(
        None,
        description="Parent category name (joined)"
    )
    needs_review: bool = Field(..., description="Admin review flag")
    is_active: bool = Field(..., description="Active status")
    supplier_id: Optional[int] = Field(None, description="Original supplier ID")
    supplier_name: Optional[str] = Field(
        None,
        description="Supplier name (joined)"
    )
    product_count: int = Field(
        default=0,
        ge=0,
        description="Number of products in this category"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CategoryApprovalRequest(BaseModel):
    """
    Request to approve or merge a category.
    
    Used by admin to resolve categories with needs_review=true.
    """
    
    category_id: int = Field(..., description="Category ID to approve/merge")
    action: str = Field(
        ...,
        description="Action: 'approve' (keep as-is) or 'merge' (combine with existing)"
    )
    merge_with_id: Optional[int] = Field(
        None,
        description="Target category ID for merge (required if action='merge')"
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of allowed values."""
        allowed = {"approve", "merge"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


class CategoryApprovalResponse(BaseModel):
    """
    Response after approving or merging a category.
    """
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Human-readable result message")
    category_id: int = Field(..., description="Affected category ID")
    action: str = Field(..., description="Action performed")
    affected_products: int = Field(
        default=0,
        ge=0,
        description="Number of products updated (for merge)"
    )


class CategoryNormalizationStats(BaseModel):
    """
    Statistics from category normalization process.
    
    Aggregates metrics for logging and monitoring.
    """
    
    total_categories_processed: int = Field(
        default=0,
        ge=0,
        description="Total category paths processed"
    )
    matched_count: int = Field(
        default=0,
        ge=0,
        description="Categories matched to existing"
    )
    created_count: int = Field(
        default=0,
        ge=0,
        description="New categories created"
    )
    skipped_count: int = Field(
        default=0,
        ge=0,
        description="Categories skipped (empty/invalid)"
    )
    review_queue_count: int = Field(
        default=0,
        ge=0,
        description="Categories added to review queue"
    )
    average_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Average similarity score for matches"
    )

    @property
    def match_rate(self) -> float:
        """Calculate match rate as percentage."""
        total = self.matched_count + self.created_count
        if total == 0:
            return 0.0
        return (self.matched_count / total) * 100

