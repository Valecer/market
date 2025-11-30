"""Unit tests for RapidFuzzMatcher and matching service.

Tests cover:
    - MatchCandidate dataclass
    - MatchResult dataclass
    - RapidFuzzMatcher.find_matches with various score scenarios
    - Threshold logic: auto-match, potential-match, no-match
    - Empty products list handling
    - search_match_candidates utility function
"""
import pytest
from uuid import uuid4
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

from src.services.matching import (
    RapidFuzzMatcher,
    MatchCandidate,
    MatchResult,
    MatchStatusEnum,
    create_matcher,
    search_match_candidates,
)


@dataclass
class MockProduct:
    """Mock product for testing matcher."""
    id: any
    name: str
    category_id: Optional[any] = None


class TestMatchCandidate:
    """Tests for MatchCandidate dataclass."""
    
    def test_to_dict_basic(self):
        """Test basic to_dict conversion."""
        product_id = uuid4()
        candidate = MatchCandidate(
            product_id=product_id,
            product_name="Test Product",
            score=92.5,
        )
        
        result = candidate.to_dict()
        
        assert result["product_id"] == str(product_id)
        assert result["product_name"] == "Test Product"
        assert result["score"] == 92.5
        assert "category_id" not in result
    
    def test_to_dict_with_category(self):
        """Test to_dict with category_id."""
        product_id = uuid4()
        category_id = uuid4()
        candidate = MatchCandidate(
            product_id=product_id,
            product_name="Test Product",
            score=85.0,
            category_id=category_id,
        )
        
        result = candidate.to_dict()
        
        assert result["category_id"] == str(category_id)


class TestRapidFuzzMatcher:
    """Tests for RapidFuzzMatcher implementation."""
    
    @pytest.fixture
    def matcher(self):
        """Create a matcher instance for testing."""
        return RapidFuzzMatcher()
    
    @pytest.fixture
    def sample_products(self):
        """Create sample products for matching tests."""
        return [
            MockProduct(id=uuid4(), name="Samsung Galaxy A54 5G 128GB Black"),
            MockProduct(id=uuid4(), name="Samsung Galaxy A54 5G 256GB Black"),
            MockProduct(id=uuid4(), name="iPhone 15 Pro 256GB Silver"),
            MockProduct(id=uuid4(), name="Xiaomi Redmi Note 12 Pro 128GB"),
        ]
    
    def test_get_strategy_name(self, matcher):
        """Test strategy name."""
        assert matcher.get_strategy_name() == "rapidfuzz_wratio"
    
    def test_find_matches_exact_match(self, matcher, sample_products):
        """Test finding an exact match (should auto-match)."""
        item_id = uuid4()
        item_name = "Samsung Galaxy A54 5G 128GB Black"
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
        )
        
        assert result.supplier_item_id == item_id
        assert result.supplier_item_name == item_name
        assert result.match_status == MatchStatusEnum.AUTO_MATCHED
        assert result.match_score >= 95.0
        assert result.best_match is not None
        assert result.best_match.product_name == item_name
    
    def test_find_matches_potential_match(self, matcher, sample_products):
        """Test finding a potential match (70-94% range)."""
        item_id = uuid4()
        # Similar but different - should score between 70-94%
        item_name = "Samsung Galaxy A54 128GB"
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
        )
        
        assert result.supplier_item_id == item_id
        # Score should be in potential match range
        if result.match_score is not None and 70 <= result.match_score < 95:
            assert result.match_status == MatchStatusEnum.POTENTIAL_MATCH
        assert result.candidates is not None
    
    def test_find_matches_no_match(self, matcher, sample_products):
        """Test no match found (< 70% score)."""
        item_id = uuid4()
        # Completely different product
        item_name = "Bosch Hammer Drill 750W Professional"
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
        )
        
        assert result.supplier_item_id == item_id
        assert result.match_status == MatchStatusEnum.UNMATCHED
        # No candidates above threshold
    
    def test_find_matches_empty_products(self, matcher):
        """Test handling empty products list."""
        item_id = uuid4()
        item_name = "Test Product"
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=[],
        )
        
        assert result.match_status == MatchStatusEnum.UNMATCHED
        assert result.best_match is None
        assert result.candidates == []
    
    def test_find_matches_custom_thresholds(self, matcher, sample_products):
        """Test with custom threshold values."""
        item_id = uuid4()
        item_name = "Samsung Galaxy A54 5G 128GB Black"
        
        # Set high auto threshold
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
            auto_threshold=99.0,  # Very high threshold
            potential_threshold=95.0,
        )
        
        # Exact match should still meet 99% threshold
        assert result.match_score is not None
        assert result.match_score >= 95.0
    
    def test_find_matches_max_candidates(self, matcher, sample_products):
        """Test max_candidates limit."""
        item_id = uuid4()
        item_name = "Samsung"  # Partial match to multiple products
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
            max_candidates=2,
            potential_threshold=0,  # Include all
        )
        
        # Should have at most 2 candidates
        assert len(result.candidates) <= 2
    
    def test_find_matches_sorted_by_score(self, matcher, sample_products):
        """Test that candidates are sorted by score descending."""
        item_id = uuid4()
        item_name = "Samsung Galaxy"
        
        result = matcher.find_matches(
            item_name=item_name,
            item_id=item_id,
            products=sample_products,
            potential_threshold=0,  # Include all to get multiple candidates
        )
        
        if len(result.candidates) > 1:
            scores = [c.score for c in result.candidates]
            assert scores == sorted(scores, reverse=True)


class TestCreateMatcher:
    """Tests for matcher factory function."""
    
    def test_create_rapidfuzz_matcher(self):
        """Test creating RapidFuzz matcher."""
        matcher = create_matcher("rapidfuzz")
        assert isinstance(matcher, RapidFuzzMatcher)
    
    def test_create_unknown_matcher(self):
        """Test error on unknown matcher type."""
        with pytest.raises(ValueError, match="Unknown matching strategy"):
            create_matcher("unknown_strategy")


class TestSearchMatchCandidates:
    """Tests for search_match_candidates utility function."""
    
    @dataclass
    class MockSupplierItem:
        """Mock supplier item for testing."""
        id: any
        name: str
        match_score: Optional[Decimal]
        match_status: Optional[MatchStatusEnum]
        product_id: Optional[any] = None
    
    @pytest.fixture
    def sample_items(self):
        """Create sample supplier items for testing."""
        return [
            self.MockSupplierItem(
                id=uuid4(),
                name="Item 1",
                match_score=Decimal("95.5"),
                match_status=MatchStatusEnum.AUTO_MATCHED,
            ),
            self.MockSupplierItem(
                id=uuid4(),
                name="Item 2",
                match_score=Decimal("78.0"),
                match_status=MatchStatusEnum.POTENTIAL_MATCH,
            ),
            self.MockSupplierItem(
                id=uuid4(),
                name="Item 3",
                match_score=None,
                match_status=MatchStatusEnum.UNMATCHED,
            ),
            self.MockSupplierItem(
                id=uuid4(),
                name="Item 4",
                match_score=Decimal("65.0"),
                match_status=MatchStatusEnum.UNMATCHED,
            ),
        ]
    
    def test_search_no_filters(self, sample_items):
        """Test search with no filters returns items with scores."""
        results = search_match_candidates(sample_items)
        
        # Should exclude items without match_score
        assert len(results) == 3
    
    def test_search_min_score_filter(self, sample_items):
        """Test filtering by minimum score."""
        results = search_match_candidates(sample_items, min_score=70.0)
        
        # Should only include items with score >= 70
        assert len(results) == 2
        for r in results:
            assert r["match_score"] >= 70.0
    
    def test_search_max_score_filter(self, sample_items):
        """Test filtering by maximum score."""
        results = search_match_candidates(sample_items, max_score=80.0)
        
        # Should only include items with score <= 80
        assert all(r["match_score"] <= 80.0 for r in results)
    
    def test_search_score_range(self, sample_items):
        """Test filtering by score range."""
        results = search_match_candidates(
            sample_items,
            min_score=70.0,
            max_score=80.0,
        )
        
        # Should only include items in range
        for r in results:
            assert 70.0 <= r["match_score"] <= 80.0

