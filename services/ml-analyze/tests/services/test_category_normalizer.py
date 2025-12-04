"""
Unit Tests for CategoryNormalizer
=================================

Tests fuzzy matching, category hierarchy creation,
and caching behavior.

Phase 9: Semantic ETL Pipeline Refactoring
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.category import CategoryMatchResult, CategoryNormalizationStats
from src.services.category_normalizer import CategoryNormalizer


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


class TestCategoryNormalizer:
    """Tests for CategoryNormalizer class."""
    
    def test_init_default_values(self, mock_session: AsyncMock) -> None:
        """Test default initialization values."""
        normalizer = CategoryNormalizer(mock_session)
        
        assert normalizer.session == mock_session
        assert normalizer.similarity_threshold == 85.0
        assert normalizer.cache_enabled is True
        assert normalizer._cache == {}
        assert normalizer._cache_loaded is False
    
    def test_init_custom_threshold(self, mock_session: AsyncMock) -> None:
        """Test custom threshold initialization."""
        normalizer = CategoryNormalizer(
            mock_session,
            similarity_threshold=90.0,
            cache_enabled=False,
        )
        
        assert normalizer.similarity_threshold == 90.0
        assert normalizer.cache_enabled is False
    
    @pytest.mark.asyncio
    async def test_load_category_cache(self, mock_session: AsyncMock) -> None:
        """Test loading categories into cache."""
        # Create proper mock objects with string name attribute
        from unittest.mock import PropertyMock
        
        cat1 = MagicMock()
        cat1.id = 1
        cat1.name = "Electronics"
        cat1.parent_id = None
        
        cat2 = MagicMock()
        cat2.id = 2
        cat2.name = "Laptops"
        cat2.parent_id = 1
        
        cat3 = MagicMock()
        cat3.id = 3
        cat3.name = "Furniture"
        cat3.parent_id = None
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.all.return_value = [cat1, cat2, cat3]
        mock_session.execute.return_value = mock_result
        
        normalizer = CategoryNormalizer(mock_session)
        await normalizer.load_category_cache()
        
        assert normalizer._cache_loaded is True
        assert len(normalizer._cache) == 3
        assert "electronics" in normalizer._cache
        assert "laptops" in normalizer._cache
        assert "furniture" in normalizer._cache
    
    @pytest.mark.asyncio
    async def test_load_cache_disabled(self, mock_session: AsyncMock) -> None:
        """Test that cache loading is skipped when disabled."""
        normalizer = CategoryNormalizer(mock_session, cache_enabled=False)
        await normalizer.load_category_cache()
        
        mock_session.execute.assert_not_called()
        assert normalizer._cache == {}
    
    def test_fuzzy_match_exact(self, mock_session: AsyncMock) -> None:
        """Test exact fuzzy match returns 100% similarity."""
        normalizer = CategoryNormalizer(mock_session)
        
        candidates = [
            ((1, "Electronics"), "electronics"),
            ((2, "Laptops"), "laptops"),
        ]
        
        result = normalizer._fuzzy_match("electronics", candidates)
        
        assert result is not None
        assert result[0] == (1, "Electronics")
        assert result[1] == 100.0  # Exact match
    
    def test_fuzzy_match_similar(self, mock_session: AsyncMock) -> None:
        """Test fuzzy match finds similar strings."""
        normalizer = CategoryNormalizer(mock_session)
        
        candidates = [
            ((1, "Electronics"), "electronics"),
            ((2, "Laptops"), "laptops"),
        ]
        
        # "Elektronics" should match "Electronics"
        result = normalizer._fuzzy_match("elektronics", candidates)
        
        assert result is not None
        assert result[0] == (1, "Electronics")
        assert result[1] > 80.0  # High similarity
    
    def test_fuzzy_match_no_candidates(self, mock_session: AsyncMock) -> None:
        """Test fuzzy match with empty candidates."""
        normalizer = CategoryNormalizer(mock_session)
        
        result = normalizer._fuzzy_match("query", [])
        
        assert result is None
    
    def test_fuzzy_match_token_order_independent(
        self, mock_session: AsyncMock
    ) -> None:
        """Test fuzzy match ignores word order (token_set_ratio)."""
        normalizer = CategoryNormalizer(mock_session)
        
        candidates = [
            ((1, "Gaming Laptops"), "gaming laptops"),
        ]
        
        # "Laptops Gaming" should match "Gaming Laptops"
        result = normalizer._fuzzy_match("laptops gaming", candidates)
        
        assert result is not None
        assert result[1] == 100.0  # token_set_ratio handles word order
    
    @pytest.mark.asyncio
    async def test_process_empty_category_path(
        self, mock_session: AsyncMock
    ) -> None:
        """Test processing empty category path."""
        normalizer = CategoryNormalizer(mock_session)
        
        result = await normalizer.process_category_path([], supplier_id=1)
        
        assert result.original_path == []
        assert result.match_results == []
        assert result.leaf_category_id is None
    
    def test_get_stats(self, mock_session: AsyncMock) -> None:
        """Test getting normalization statistics."""
        normalizer = CategoryNormalizer(mock_session)
        normalizer.stats.matched_count = 10
        normalizer.stats.created_count = 5
        
        stats = normalizer.get_stats()
        
        assert isinstance(stats, CategoryNormalizationStats)
        assert stats.matched_count == 10
        assert stats.created_count == 5
    
    def test_reset_stats(self, mock_session: AsyncMock) -> None:
        """Test resetting statistics."""
        normalizer = CategoryNormalizer(mock_session)
        normalizer.stats.matched_count = 100
        normalizer.stats.created_count = 50
        
        normalizer.reset_stats()
        
        assert normalizer.stats.matched_count == 0
        assert normalizer.stats.created_count == 0


class TestCategoryMatchResult:
    """Tests for CategoryMatchResult properties."""
    
    def test_is_new_category_created(self) -> None:
        """Test is_new_category for created action."""
        result = CategoryMatchResult(
            extracted_name="New Category",
            similarity_score=50.0,
            action="created",
            needs_review=True,
            created_category_id=42,
        )
        
        assert result.is_new_category is True
    
    def test_is_new_category_matched(self) -> None:
        """Test is_new_category for matched action."""
        result = CategoryMatchResult(
            extracted_name="Electronics",
            matched_id=1,
            matched_name="Electronics",
            similarity_score=100.0,
            action="matched",
        )
        
        assert result.is_new_category is False
    
    def test_is_confident_match(self) -> None:
        """Test is_confident_match property."""
        high_confidence = CategoryMatchResult(
            extracted_name="Electronics",
            matched_id=1,
            matched_name="Electronics",
            similarity_score=95.0,
            action="matched",
        )
        
        low_confidence = CategoryMatchResult(
            extracted_name="Elektronics",
            matched_id=1,
            matched_name="Electronics",
            similarity_score=85.0,
            action="matched",
        )
        
        assert high_confidence.is_confident_match is True
        assert low_confidence.is_confident_match is False
    
    def test_final_category_id_matched(self) -> None:
        """Test final_category_id for matched category."""
        result = CategoryMatchResult(
            extracted_name="Electronics",
            matched_id=1,
            matched_name="Electronics",
            similarity_score=100.0,
            action="matched",
        )
        
        assert result.final_category_id == 1
    
    def test_final_category_id_created(self) -> None:
        """Test final_category_id for created category."""
        result = CategoryMatchResult(
            extracted_name="New Category",
            similarity_score=50.0,
            action="created",
            needs_review=True,
            created_category_id=42,
        )
        
        assert result.final_category_id == 42
    
    def test_final_category_id_skipped(self) -> None:
        """Test final_category_id for skipped category."""
        result = CategoryMatchResult(
            extracted_name="",
            similarity_score=0.0,
            action="skipped",
        )
        
        assert result.final_category_id is None


class TestCategoryNormalizationStats:
    """Tests for CategoryNormalizationStats properties."""
    
    def test_match_rate_calculation(self) -> None:
        """Test match rate percentage calculation."""
        stats = CategoryNormalizationStats(
            matched_count=80,
            created_count=20,
        )
        
        assert stats.match_rate == 80.0
    
    def test_match_rate_zero_total(self) -> None:
        """Test match rate with zero total."""
        stats = CategoryNormalizationStats(
            matched_count=0,
            created_count=0,
        )
        
        assert stats.match_rate == 0.0
    
    def test_match_rate_all_matched(self) -> None:
        """Test match rate when all categories matched."""
        stats = CategoryNormalizationStats(
            matched_count=100,
            created_count=0,
        )
        
        assert stats.match_rate == 100.0

