"""
Unit Tests for CategoryHierarchyService

Phase 11 US3: Category Hierarchy Enforcement
Tests T107-T112: Verify 3-level hierarchy enforcement behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.services.category_hierarchy_service import (
    CategoryHierarchyService,
    CategoryLevelResult,
    HierarchyEnforcementResult,
    MAX_HIERARCHY_LEVELS,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def hierarchy_service(mock_session):
    """Create a CategoryHierarchyService instance with mocked session."""
    return CategoryHierarchyService(
        session=mock_session,
        task_id="test-task-123",
    )


# =============================================================================
# T107: test_ensure_3_level_hierarchy_full_path
# =============================================================================


class TestEnsure3LevelHierarchyFullPath:
    """T107: Tests for complete 3-level category paths."""

    @pytest.mark.asyncio
    async def test_full_path_creates_3_levels(self, hierarchy_service, mock_session):
        """Given a 3-element path, should create/find 3 categories."""
        # Mock no existing categories found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Mock category creation - simulate ID assignment
        created_ids = []

        def mock_add(obj):
            obj.id = uuid4()
            created_ids.append(obj.id)

        mock_session.add.side_effect = mock_add

        # Execute
        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Electronics", "Laptops", "Dell"],
            supplier_id=uuid4(),
        )

        # Verify
        assert result.is_complete is True
        assert result.was_truncated is False
        assert result.needs_review is False
        assert len(result.level_results) == 3
        assert result.processed_path == ["Electronics", "Laptops", "Dell"]
        assert result.leaf_category_id is not None

    @pytest.mark.asyncio
    async def test_full_path_levels_are_correct(self, hierarchy_service, mock_session):
        """Verify each level has correct level number."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Level1", "Level2", "Level3"],
        )

        assert result.level_results[0].level == 1
        assert result.level_results[1].level == 2
        assert result.level_results[2].level == 3

    @pytest.mark.asyncio
    async def test_full_path_parent_chain_is_correct(self, hierarchy_service, mock_session):
        """Verify parent_id chain is correctly set."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        created_categories = []

        def mock_add(obj):
            obj.id = uuid4()
            created_categories.append(obj)

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Root", "Middle", "Leaf"],
        )

        # Level 1 should have no parent
        assert result.level_results[0].parent_id is None
        # Level 2 parent should be Level 1
        assert result.level_results[1].parent_id == result.level_results[0].category_id
        # Level 3 parent should be Level 2
        assert result.level_results[2].parent_id == result.level_results[1].category_id


# =============================================================================
# T108: test_ensure_3_level_hierarchy_partial_path
# =============================================================================


class TestEnsure3LevelHierarchyPartialPath:
    """T108: Tests for incomplete (<3 levels) category paths."""

    @pytest.mark.asyncio
    async def test_1_level_path_flags_needs_review(self, hierarchy_service, mock_session):
        """Given a 1-element path, should flag for review."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["OnlyOne"],
        )

        assert result.is_complete is False
        assert result.needs_review is True
        assert result.was_truncated is False
        assert len(result.level_results) == 1
        assert result.warning_message is not None
        assert "1 of 3" in result.warning_message

    @pytest.mark.asyncio
    async def test_2_level_path_flags_needs_review(self, hierarchy_service, mock_session):
        """Given a 2-element path, should flag for review."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Parent", "Child"],
        )

        assert result.is_complete is False
        assert result.needs_review is True
        assert len(result.level_results) == 2
        assert "2 of 3" in result.warning_message

    @pytest.mark.asyncio
    async def test_partial_path_calls_flag_incomplete(self, hierarchy_service, mock_session):
        """Verify flag_incomplete_hierarchy is called for partial paths."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        # Track if ParsingLog was added
        added_objects = []
        original_add = mock_session.add.side_effect

        def track_add(obj):
            added_objects.append(obj.__class__.__name__)
            original_add(obj)

        mock_session.add.side_effect = track_add

        await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Incomplete"],
            supplier_id=uuid4(),
        )

        # Should have added Category + ParsingLog
        assert "Category" in added_objects
        assert "ParsingLog" in added_objects

    @pytest.mark.asyncio
    async def test_empty_path_returns_warning(self, hierarchy_service):
        """Empty path should return result with warning."""
        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=[],
        )

        assert result.leaf_category_id is None
        assert result.is_complete is False
        assert result.warning_message is not None
        assert "Empty" in result.warning_message


# =============================================================================
# T109: test_ensure_3_level_hierarchy_excess_path
# =============================================================================


class TestEnsure3LevelHierarchyExcessPath:
    """T109: Tests for paths with more than 3 levels."""

    @pytest.mark.asyncio
    async def test_4_level_path_truncates_to_3(self, hierarchy_service, mock_session):
        """Given a 4-element path, should truncate to first 3."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Level1", "Level2", "Level3", "Level4"],
        )

        assert result.is_complete is True
        assert result.was_truncated is True
        assert result.needs_review is False
        assert len(result.level_results) == 3
        assert result.processed_path == ["Level1", "Level2", "Level3"]
        assert "Level4" in result.warning_message

    @pytest.mark.asyncio
    async def test_5_level_path_truncates_to_3(self, hierarchy_service, mock_session):
        """Given a 5-element path, should truncate to first 3."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["A", "B", "C", "D", "E"],
        )

        assert result.was_truncated is True
        assert result.processed_path == ["A", "B", "C"]
        assert result.original_path == ["A", "B", "C", "D", "E"]

    @pytest.mark.asyncio
    async def test_truncated_path_preserves_original(self, hierarchy_service, mock_session):
        """Original path should be preserved in result."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        original = ["Electronics", "Computers", "Laptops", "Gaming", "ASUS"]
        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=original.copy(),
        )

        # Original path preserves full input, processed path is truncated
        assert result.original_path == original  # Full original path
        assert result.processed_path == original[:3]  # Truncated to 3 levels


# =============================================================================
# T110: test_find_or_create_category_existing
# =============================================================================


class TestFindOrCreateCategoryExisting:
    """T110: Tests for finding existing categories."""

    @pytest.mark.asyncio
    async def test_finds_existing_root_category(self, hierarchy_service, mock_session):
        """Should find existing root category and return 'found' action."""
        existing_id = uuid4()
        existing_cat = MagicMock()
        existing_cat.id = existing_id
        existing_cat.name = "Electronics"
        existing_cat.needs_review = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cat
        mock_session.execute.return_value = mock_result

        result = await hierarchy_service.find_or_create_category(
            name="Electronics",
            parent_id=None,
            level=1,
        )

        assert result.action == "found"
        assert result.category_id == existing_id
        assert result.category_name == "Electronics"

    @pytest.mark.asyncio
    async def test_finds_existing_child_category(self, hierarchy_service, mock_session):
        """Should find existing child category with parent match."""
        parent_id = uuid4()
        existing_id = uuid4()
        existing_cat = MagicMock()
        existing_cat.id = existing_id
        existing_cat.name = "Laptops"
        existing_cat.needs_review = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cat
        mock_session.execute.return_value = mock_result

        result = await hierarchy_service.find_or_create_category(
            name="Laptops",
            parent_id=parent_id,
            level=2,
        )

        assert result.action == "found"
        assert result.category_id == existing_id
        assert result.parent_id == parent_id

    @pytest.mark.asyncio
    async def test_increments_found_stat(self, hierarchy_service, mock_session):
        """Stats should track found categories."""
        existing_cat = MagicMock()
        existing_cat.id = uuid4()
        existing_cat.name = "Test"
        existing_cat.needs_review = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_cat
        mock_session.execute.return_value = mock_result

        await hierarchy_service.find_or_create_category(
            name="Test",
            parent_id=None,
            level=1,
        )

        stats = hierarchy_service.get_stats()
        assert stats["categories_found"] == 1


# =============================================================================
# T111: test_find_or_create_category_new
# =============================================================================


class TestFindOrCreateCategoryNew:
    """T111: Tests for creating new categories."""

    @pytest.mark.asyncio
    async def test_creates_new_root_category(self, hierarchy_service, mock_session):
        """Should create new category when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        new_id = uuid4()

        def mock_add(obj):
            obj.id = new_id

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.find_or_create_category(
            name="NewCategory",
            parent_id=None,
            level=1,
        )

        assert result.action == "created"
        assert result.category_id == new_id
        assert result.category_name == "NewCategory"

    @pytest.mark.asyncio
    async def test_new_category_has_correct_level(self, hierarchy_service, mock_session):
        """New category should have correct level set."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        created_categories = []

        def mock_add(obj):
            obj.id = uuid4()
            created_categories.append(obj)

        mock_session.add.side_effect = mock_add

        await hierarchy_service.find_or_create_category(
            name="Level2Cat",
            parent_id=uuid4(),
            level=2,
        )

        assert len(created_categories) == 1
        assert created_categories[0].category_level == 2

    @pytest.mark.asyncio
    async def test_invalid_level_raises_error(self, hierarchy_service):
        """Should raise ValueError for invalid level."""
        with pytest.raises(ValueError, match="Invalid category level"):
            await hierarchy_service.find_or_create_category(
                name="Invalid",
                parent_id=None,
                level=4,  # Invalid
            )

    @pytest.mark.asyncio
    async def test_level2_without_parent_raises_error(self, hierarchy_service):
        """Level 2+ categories must have parent_id."""
        with pytest.raises(ValueError, match="must have a parent_id"):
            await hierarchy_service.find_or_create_category(
                name="NoParent",
                parent_id=None,
                level=2,  # Level 2 without parent
            )

    @pytest.mark.asyncio
    async def test_increments_created_stat(self, hierarchy_service, mock_session):
        """Stats should track created categories."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        await hierarchy_service.find_or_create_category(
            name="New",
            parent_id=None,
            level=1,
        )

        stats = hierarchy_service.get_stats()
        assert stats["categories_created"] == 1


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Additional edge case tests."""

    @pytest.mark.asyncio
    async def test_whitespace_names_cleaned(self, hierarchy_service, mock_session):
        """Whitespace in names should be cleaned."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["  Trimmed  ", " Names ", "  Here  "],
        )

        assert result.processed_path == ["Trimmed", "Names", "Here"]

    @pytest.mark.asyncio
    async def test_empty_elements_filtered(self, hierarchy_service, mock_session):
        """Empty elements in path should be filtered."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.ensure_3_level_hierarchy(
            category_path=["Valid", "", "  ", "Also Valid"],
        )

        # Should treat as 2 valid elements (incomplete)
        assert result.needs_review is True
        assert len(result.level_results) == 2

    @pytest.mark.asyncio
    async def test_stats_reset(self, hierarchy_service):
        """Stats should reset correctly."""
        hierarchy_service._stats["hierarchies_processed"] = 10
        hierarchy_service._stats["categories_created"] = 5

        hierarchy_service.reset_stats()
        stats = hierarchy_service.get_stats()

        assert stats["hierarchies_processed"] == 0
        assert stats["categories_created"] == 0

    @pytest.mark.asyncio
    async def test_level1_with_parent_logs_warning(self, hierarchy_service, mock_session):
        """Level 1 with parent_id should log warning and ignore parent."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        created_categories = []

        def mock_add(obj):
            obj.id = uuid4()
            created_categories.append(obj)

        mock_session.add.side_effect = mock_add

        result = await hierarchy_service.find_or_create_category(
            name="Root",
            parent_id=uuid4(),  # Should be ignored
            level=1,
        )

        # Should still work but parent_id should be None
        assert result.parent_id is None
        assert created_categories[0].parent_id is None

