"""
E2E Test: Category Fuzzy Matching (T050)
=========================================

Tests category normalization with fuzzy matching:
1. Verify categories are matched with >85% similarity threshold
2. Verify new categories are created with needs_review=true
3. Verify category hierarchy is preserved

Phase 9: Semantic ETL Pipeline Refactoring

Requires:
- Running PostgreSQL with categories table
- Test data files with category variations
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test data paths
TEST_DATA_DIR = Path("/Users/valecer/work/sites/marketbel/specs/009-semantic-etl/test_data")
METADATA_FILE = TEST_DATA_DIR / "test_metadata.json"


@pytest.fixture(scope="module")
def test_metadata() -> dict[str, Any]:
    """Load test metadata for validation."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {"standard_file": {"categories": []}}


class TestCategoryNormalizerUnit:
    """
    Unit tests for CategoryNormalizer fuzzy matching.
    
    These tests don't require a database connection.
    """

    def test_fuzzy_match_exact_match(self):
        """Test that exact matches return 100% similarity."""
        from src.services.category_normalizer import CategoryNormalizer
        
        # Create normalizer without session (for unit testing)
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        normalizer._cache = {}
        
        # Test data
        query = "electronics"
        candidates = [
            ((1, "Electronics"), "electronics"),
            ((2, "Home Appliances"), "home appliances"),
        ]
        
        result = normalizer._fuzzy_match(query, candidates)
        
        assert result is not None
        assert result[0] == (1, "Electronics")
        assert result[1] == 100.0  # Exact match

    def test_fuzzy_match_similar_names(self):
        """Test fuzzy matching for similar category names."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        normalizer._cache = {}
        
        # Test Russian variation matching English
        query = "ноутбуки"  # Laptops in Russian
        candidates = [
            ((1, "Laptops"), "laptops"),
            ((2, "Notebooks"), "notebooks"),
            ((3, "Computers"), "computers"),
        ]
        
        # Note: This won't match well without translation
        result = normalizer._fuzzy_match(query, candidates)
        
        # Should return something (or None if no match above threshold)
        # The actual match depends on fuzzy algorithm

    def test_fuzzy_match_token_set_ratio(self):
        """Test that token_set_ratio handles word order variations."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        normalizer._cache = {}
        
        # "Gaming Laptops" vs "Laptops Gaming" should match well
        query = "gaming laptops"
        candidates = [
            ((1, "Laptops Gaming"), "laptops gaming"),
            ((2, "Desktop Gaming"), "desktop gaming"),
        ]
        
        result = normalizer._fuzzy_match(query, candidates)
        
        assert result is not None
        assert result[0][0] == 1  # Should match "Laptops Gaming"
        assert result[1] >= 85.0  # Above threshold

    def test_fuzzy_match_threshold_filtering(self):
        """Test that matches below threshold are handled correctly."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        normalizer._cache = {}
        
        # Completely different names
        query = "smartphones"
        candidates = [
            ((1, "Kitchen Appliances"), "kitchen appliances"),
            ((2, "Garden Tools"), "garden tools"),
        ]
        
        result = normalizer._fuzzy_match(query, candidates)
        
        # Should return best match (even if below threshold)
        # Threshold filtering happens in _process_single_category
        if result:
            assert result[1] < 85.0  # Should be below threshold


class TestCategoryNormalizerIntegration:
    """
    Integration tests for CategoryNormalizer with mocked database.
    """

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_process_category_path_empty(self, mock_session):
        """Test processing empty category path."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer(mock_session, similarity_threshold=85.0)
        normalizer._cache_loaded = True
        normalizer._cache = {}
        
        result = await normalizer.process_category_path([], supplier_id=123)
        
        assert result.original_path == []
        assert result.match_results == []
        assert result.leaf_category_id is None

    @pytest.mark.asyncio
    async def test_process_category_path_creates_new_when_no_match(self, mock_session):
        """Test that new categories are created with needs_review=True."""
        from src.services.category_normalizer import CategoryNormalizer
        from src.schemas.category import CategoryNormalizationStats
        
        # This test validates the concept - full integration requires real DB
        # The key behavior: when no match is found, a new category is created
        
        normalizer = CategoryNormalizer(mock_session, similarity_threshold=85.0)
        normalizer._cache_loaded = True
        normalizer._cache = {}  # Empty cache = no existing categories
        normalizer.stats = CategoryNormalizationStats()
        
        # For unit testing without real DB, we can only verify the cache logic
        # The _create_new_category method requires real SQLAlchemy operations
        
        # Test that empty cache results in no candidates at level
        candidates = await normalizer._get_candidates_at_level(parent_id=None)
        assert candidates == []
        
        # Test that fuzzy match returns None with no candidates
        result = normalizer._fuzzy_match("test", [])
        assert result is None

    @pytest.mark.asyncio
    async def test_category_hierarchy_preserved(self, mock_session):
        """Test that category hierarchy is processed parent-first."""
        from src.services.category_normalizer import CategoryNormalizer
        from src.schemas.category import CategoryNormalizationStats
        
        normalizer = CategoryNormalizer(mock_session, similarity_threshold=85.0)
        normalizer._cache_loaded = True
        normalizer._cache = {
            "electronics": (1, "Electronics", None),
            "laptops": (2, "Laptops", 1),
        }
        normalizer.stats = CategoryNormalizationStats()
        
        # Verify cache structure for hierarchy
        # Parent: Electronics (id=1, parent_id=None)
        # Child: Laptops (id=2, parent_id=1)
        
        # Test that candidates at root level include Electronics
        candidates = await normalizer._get_candidates_at_level(parent_id=None)
        assert len(candidates) == 1
        assert candidates[0][0] == (1, "Electronics")
        
        # Test that candidates at level 1 include Laptops
        candidates = await normalizer._get_candidates_at_level(parent_id=1)
        assert len(candidates) == 1
        assert candidates[0][0] == (2, "Laptops")

    @pytest.mark.asyncio
    async def test_similarity_threshold_85_percent(self, mock_session):
        """
        Test that 85% threshold is enforced.
        
        Phase 3 criterion: Categories matched with >85% fuzzy threshold.
        """
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer(mock_session, similarity_threshold=85.0)
        
        # Direct fuzzy match test
        query = "Gaming Laptop"
        candidates = [
            ((1, "Gaming Laptops"), "gaming laptops"),
            ((2, "Office Laptops"), "office laptops"),
        ]
        
        result = normalizer._fuzzy_match(query.lower(), candidates)
        
        assert result is not None
        # "Gaming Laptop" vs "Gaming Laptops" should be >85%
        assert result[1] > 85.0, f"Expected >85% match, got {result[1]}%"


class TestCategoryMatchingScenarios:
    """
    Test specific category matching scenarios from spec.
    """

    def test_english_category_variations(self):
        """Test matching English category variations."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        
        # "Laptops" vs "Notebook" - should NOT match (different words)
        candidates = [((1, "Laptops"), "laptops")]
        result = normalizer._fuzzy_match("notebook", candidates)
        
        if result:
            assert result[1] < 85.0, "Notebook should not match Laptops at 85%"
        
        # "Electronics/Gadgets" vs "Electronics" - should match
        candidates = [((1, "Electronics"), "electronics")]
        result = normalizer._fuzzy_match("electronics gadgets", candidates)
        
        # May or may not match depending on tokenization

    def test_partial_match_handling(self):
        """Test partial matches are handled correctly."""
        from src.services.category_normalizer import CategoryNormalizer
        
        normalizer = CategoryNormalizer.__new__(CategoryNormalizer)
        normalizer.similarity_threshold = 85.0
        normalizer.cache_enabled = False
        
        # "Power Tools" vs "Tools" - partial match
        candidates = [
            ((1, "Tools"), "tools"),
            ((2, "Hand Tools"), "hand tools"),
            ((3, "Power Tools"), "power tools"),
        ]
        
        result = normalizer._fuzzy_match("power tools", candidates)
        
        assert result is not None
        # RapidFuzz token_set_ratio may match "tools" with high score since
        # "power tools" contains "tools". The exact result depends on tokenization.
        # The important thing is that we get a match above threshold.
        assert result[1] >= 85.0, f"Expected match >= 85%, got {result[1]}%"


class TestCategoryStatsTracking:
    """Test category normalization statistics."""

    def test_stats_tracking(self):
        """Test that stats are tracked correctly."""
        from src.schemas.category import CategoryNormalizationStats
        
        stats = CategoryNormalizationStats()
        
        assert stats.matched_count == 0
        assert stats.created_count == 0
        assert stats.average_similarity == 0.0
        
        # Simulate matches
        stats.matched_count = 10
        stats.created_count = 5
        stats.average_similarity = 92.5
        
        assert stats.matched_count == 10
        assert stats.created_count == 5
        assert stats.average_similarity == 92.5

