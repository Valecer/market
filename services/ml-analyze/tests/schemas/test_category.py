"""
Unit Tests for Category Schemas
================================

Tests for CategoryMatchResult, CategoryHierarchyResult, and related models.
Validates field validation, computed properties, and action constraints.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.category import (
    CategoryApprovalRequest,
    CategoryApprovalResponse,
    CategoryDTO,
    CategoryHierarchyResult,
    CategoryMatchResult,
    CategoryNormalizationStats,
    CategoryReviewItem,
)


class TestCategoryMatchResult:
    """Tests for CategoryMatchResult model."""

    def test_valid_matched_result(self) -> None:
        """Test creating a valid matched result."""
        result = CategoryMatchResult(
            extracted_name="Electronics",
            matched_id=5,
            matched_name="Electronics & Gadgets",
            similarity_score=92.5,
            action="matched",
            needs_review=False,
        )
        assert result.extracted_name == "Electronics"
        assert result.matched_id == 5
        assert result.matched_name == "Electronics & Gadgets"
        assert result.similarity_score == 92.5
        assert result.action == "matched"
        assert result.needs_review is False

    def test_valid_created_result(self) -> None:
        """Test creating a valid created result."""
        result = CategoryMatchResult(
            extracted_name="Gaming Laptops",
            similarity_score=70.0,
            action="created",
            needs_review=True,
            parent_id=5,
            created_category_id=42,
        )
        assert result.extracted_name == "Gaming Laptops"
        assert result.matched_id is None
        assert result.action == "created"
        assert result.needs_review is True
        assert result.created_category_id == 42

    def test_similarity_score_bounds(self) -> None:
        """Test that similarity_score must be between 0 and 100."""
        with pytest.raises(ValidationError) as exc_info:
            CategoryMatchResult(
                extracted_name="Test",
                similarity_score=-1.0,
                action="matched",
            )
        assert "greater than or equal to 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            CategoryMatchResult(
                extracted_name="Test",
                similarity_score=101.0,
                action="matched",
            )
        assert "less than or equal to 100" in str(exc_info.value)

    def test_action_validation(self) -> None:
        """Test that action must be one of allowed values."""
        with pytest.raises(ValidationError) as exc_info:
            CategoryMatchResult(
                extracted_name="Test",
                similarity_score=50.0,
                action="invalid_action",
            )
        assert "action must be one of" in str(exc_info.value)

    def test_is_new_category_property(self) -> None:
        """Test is_new_category property."""
        created = CategoryMatchResult(
            extracted_name="Test",
            similarity_score=50.0,
            action="created",
        )
        assert created.is_new_category is True

        matched = CategoryMatchResult(
            extracted_name="Test",
            similarity_score=90.0,
            action="matched",
        )
        assert matched.is_new_category is False

    def test_is_confident_match_property(self) -> None:
        """Test is_confident_match property (>90%)."""
        confident = CategoryMatchResult(
            extracted_name="Test",
            similarity_score=91.0,
            action="matched",
        )
        assert confident.is_confident_match is True

        not_confident = CategoryMatchResult(
            extracted_name="Test",
            similarity_score=90.0,
            action="matched",
        )
        assert not_confident.is_confident_match is False

    def test_final_category_id_property(self) -> None:
        """Test final_category_id property."""
        matched = CategoryMatchResult(
            extracted_name="Test",
            matched_id=5,
            similarity_score=90.0,
            action="matched",
        )
        assert matched.final_category_id == 5

        created = CategoryMatchResult(
            extracted_name="Test",
            similarity_score=50.0,
            action="created",
            created_category_id=42,
        )
        assert created.final_category_id == 42

        skipped = CategoryMatchResult(
            extracted_name="",
            similarity_score=0.0,
            action="skipped",
        )
        assert skipped.final_category_id is None


class TestCategoryHierarchyResult:
    """Tests for CategoryHierarchyResult model."""

    def test_valid_hierarchy_result(self) -> None:
        """Test creating a valid hierarchy result."""
        result = CategoryHierarchyResult(
            original_path=["Electronics", "Laptops", "Gaming"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="Electronics",
                    matched_id=1,
                    similarity_score=100.0,
                    action="matched",
                ),
                CategoryMatchResult(
                    extracted_name="Laptops",
                    matched_id=5,
                    similarity_score=95.0,
                    action="matched",
                ),
                CategoryMatchResult(
                    extracted_name="Gaming",
                    similarity_score=60.0,
                    action="created",
                    needs_review=True,
                    created_category_id=42,
                ),
            ],
            leaf_category_id=42,
        )
        assert result.original_path == ["Electronics", "Laptops", "Gaming"]
        assert len(result.match_results) == 3
        assert result.leaf_category_id == 42

    def test_all_matched_property(self) -> None:
        """Test all_matched property."""
        all_matched = CategoryHierarchyResult(
            original_path=["A", "B"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="A",
                    similarity_score=100.0,
                    action="matched",
                ),
                CategoryMatchResult(
                    extracted_name="B",
                    similarity_score=90.0,
                    action="matched",
                ),
            ],
        )
        assert all_matched.all_matched is True

        some_created = CategoryHierarchyResult(
            original_path=["A", "B"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="A",
                    similarity_score=100.0,
                    action="matched",
                ),
                CategoryMatchResult(
                    extracted_name="B",
                    similarity_score=50.0,
                    action="created",
                ),
            ],
        )
        assert some_created.all_matched is False

    def test_any_needs_review_property(self) -> None:
        """Test any_needs_review property."""
        needs_review = CategoryHierarchyResult(
            original_path=["A", "B"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="A",
                    similarity_score=100.0,
                    action="matched",
                    needs_review=False,
                ),
                CategoryMatchResult(
                    extracted_name="B",
                    similarity_score=50.0,
                    action="created",
                    needs_review=True,
                ),
            ],
        )
        assert needs_review.any_needs_review is True

        no_review = CategoryHierarchyResult(
            original_path=["A"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="A",
                    similarity_score=100.0,
                    action="matched",
                    needs_review=False,
                ),
            ],
        )
        assert no_review.any_needs_review is False

    def test_categories_created_property(self) -> None:
        """Test categories_created count property."""
        result = CategoryHierarchyResult(
            original_path=["A", "B", "C"],
            match_results=[
                CategoryMatchResult(
                    extracted_name="A",
                    similarity_score=100.0,
                    action="matched",
                ),
                CategoryMatchResult(
                    extracted_name="B",
                    similarity_score=50.0,
                    action="created",
                ),
                CategoryMatchResult(
                    extracted_name="C",
                    similarity_score=40.0,
                    action="created",
                ),
            ],
        )
        assert result.categories_created == 2


class TestCategoryDTO:
    """Tests for CategoryDTO model."""

    def test_valid_dto(self) -> None:
        """Test creating a valid CategoryDTO."""
        now = datetime.now(timezone.utc)
        dto = CategoryDTO(
            id=1,
            name="Electronics",
            parent_id=None,
            needs_review=False,
            is_active=True,
            supplier_id=5,
            created_at=now,
            updated_at=now,
        )
        assert dto.id == 1
        assert dto.name == "Electronics"
        assert dto.parent_id is None
        assert dto.needs_review is False


class TestCategoryReviewItem:
    """Tests for CategoryReviewItem model."""

    def test_valid_review_item(self) -> None:
        """Test creating a valid review item."""
        now = datetime.now(timezone.utc)
        item = CategoryReviewItem(
            id=42,
            name="Gaming Laptops",
            parent_id=5,
            parent_name="Laptops",
            needs_review=True,
            is_active=True,
            supplier_id=10,
            supplier_name="Tech Supplier",
            product_count=15,
            created_at=now,
            updated_at=now,
        )
        assert item.id == 42
        assert item.name == "Gaming Laptops"
        assert item.parent_name == "Laptops"
        assert item.supplier_name == "Tech Supplier"
        assert item.product_count == 15


class TestCategoryApprovalRequest:
    """Tests for CategoryApprovalRequest model."""

    def test_valid_approve_request(self) -> None:
        """Test creating a valid approve request."""
        request = CategoryApprovalRequest(
            category_id=42,
            action="approve",
        )
        assert request.category_id == 42
        assert request.action == "approve"
        assert request.merge_with_id is None

    def test_valid_merge_request(self) -> None:
        """Test creating a valid merge request."""
        request = CategoryApprovalRequest(
            category_id=42,
            action="merge",
            merge_with_id=5,
        )
        assert request.category_id == 42
        assert request.action == "merge"
        assert request.merge_with_id == 5

    def test_action_validation(self) -> None:
        """Test that action must be 'approve' or 'merge'."""
        with pytest.raises(ValidationError) as exc_info:
            CategoryApprovalRequest(
                category_id=42,
                action="delete",
            )
        assert "action must be one of" in str(exc_info.value)


class TestCategoryApprovalResponse:
    """Tests for CategoryApprovalResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid approval response."""
        response = CategoryApprovalResponse(
            success=True,
            message="Category approved successfully",
            category_id=42,
            action="approve",
            affected_products=0,
        )
        assert response.success is True
        assert response.message == "Category approved successfully"
        assert response.affected_products == 0


class TestCategoryNormalizationStats:
    """Tests for CategoryNormalizationStats model."""

    def test_valid_stats(self) -> None:
        """Test creating valid normalization stats."""
        stats = CategoryNormalizationStats(
            total_categories_processed=100,
            matched_count=80,
            created_count=15,
            skipped_count=5,
            review_queue_count=15,
            average_similarity=88.5,
        )
        assert stats.total_categories_processed == 100
        assert stats.matched_count == 80
        assert stats.created_count == 15

    def test_match_rate_property(self) -> None:
        """Test match_rate property calculation."""
        stats = CategoryNormalizationStats(
            matched_count=80,
            created_count=20,
        )
        assert stats.match_rate == 80.0

    def test_match_rate_zero_total(self) -> None:
        """Test match_rate with zero matches and creates."""
        stats = CategoryNormalizationStats(
            matched_count=0,
            created_count=0,
        )
        assert stats.match_rate == 0.0

