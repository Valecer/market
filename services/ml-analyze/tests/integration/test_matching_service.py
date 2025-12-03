"""
Integration Tests for Matching Service
=======================================

End-to-end tests for the matching service orchestration.
Tests the full pipeline: item → vector search → LLM → database update.

Run: pytest tests/integration/test_matching_service.py -v
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.schemas.domain import MatchResult, SimilarityResult
from src.services.matching_service import (
    ItemMatchResult,
    MatchingService,
    MatchingStats,
)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_llm_model = "llama3"
    settings.embedding_dimensions = 768
    settings.match_confidence_auto_threshold = 0.9
    settings.match_confidence_review_threshold = 0.7
    return settings


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_supplier_items_repo():
    """Create mock supplier items repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value={
        "id": uuid4(),
        "supplier_id": uuid4(),
        "name": "Test Product",
        "price": 19.99,
        "sku": "TEST-001",
        "characteristics": {
            "_brand": "TestBrand",
            "_category": "TestCategory",
            "_description": "A test product description",
        },
    })
    repo.update_product_id = AsyncMock(return_value=True)
    repo.get_pending_match = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_match_review_repo():
    """Create mock match review repository."""
    repo = AsyncMock()
    repo.insert = AsyncMock(return_value=uuid4())
    return repo


@pytest.fixture
def mock_parsing_logs_repo():
    """Create mock parsing logs repository."""
    repo = AsyncMock()
    repo.log_error = AsyncMock()
    return repo


@pytest.fixture
def mock_vector_service():
    """Create mock vector service."""
    service = AsyncMock()
    service.similarity_search_text = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_merger_agent():
    """Create mock merger agent."""
    agent = AsyncMock()
    agent.find_matches = AsyncMock(return_value=[])
    return agent


class TestMatchingServiceInit:
    """Tests for MatchingService initialization."""

    def test_init_creates_dependencies(self, mock_session, mock_settings):
        """Test that initialization creates all dependencies."""
        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent"), \
             patch("src.services.matching_service.SupplierItemsRepository"), \
             patch("src.services.matching_service.MatchReviewRepository"), \
             patch("src.services.matching_service.ParsingLogsRepository"):

            service = MatchingService(mock_session, mock_settings)

            assert service._auto_threshold == 0.9
            assert service._review_threshold == 0.7


class TestMatchingServiceMatchItem:
    """Tests for match_item method."""

    @pytest.mark.asyncio
    async def test_match_item_auto_match(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test item is auto-matched when confidence >= 0.9."""
        item_id = uuid4()
        product_id = uuid4()

        # Setup high-confidence match
        mock_merger_agent.find_matches.return_value = [
            MatchResult(
                product_id=product_id,
                product_name="Matched Product",
                confidence=0.95,
                reasoning="High confidence match",
                similarity_score=0.92,
            )
        ]

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            result = await service.match_item(item_id)

            assert result.status == "auto_matched"
            assert result.match is not None
            assert result.match.product_id == product_id
            mock_supplier_items_repo.update_product_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_match_item_review(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test item is sent to review when 0.7 <= confidence < 0.9."""
        item_id = uuid4()
        product_id = uuid4()

        # Setup medium-confidence match
        mock_merger_agent.find_matches.return_value = [
            MatchResult(
                product_id=product_id,
                product_name="Review Product",
                confidence=0.82,
                reasoning="Medium confidence match",
                similarity_score=0.80,
            )
        ]

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            result = await service.match_item(item_id)

            assert result.status == "review"
            assert result.match is not None
            mock_match_review_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_match_item_rejected(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test item is rejected when confidence < 0.7."""
        item_id = uuid4()
        product_id = uuid4()

        # Setup low-confidence match
        mock_merger_agent.find_matches.return_value = [
            MatchResult(
                product_id=product_id,
                product_name="Low Match",
                confidence=0.55,
                reasoning="Low confidence match",
                similarity_score=0.50,
            )
        ]

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            result = await service.match_item(item_id)

            assert result.status == "rejected"
            mock_parsing_logs_repo.log_error.assert_called()

    @pytest.mark.asyncio
    async def test_match_item_no_match(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test no_match status when no matches found."""
        item_id = uuid4()

        # No matches
        mock_merger_agent.find_matches.return_value = []

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            result = await service.match_item(item_id)

            assert result.status == "no_match"
            assert result.match is None

    @pytest.mark.asyncio
    async def test_match_item_not_found(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test error when item not found."""
        item_id = uuid4()
        mock_supplier_items_repo.get_by_id.return_value = None

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            result = await service.match_item(item_id)

            assert result.status == "error"
            assert "not found" in result.error_message.lower()


class TestMatchingServiceMatchBatch:
    """Tests for match_batch method."""

    @pytest.mark.asyncio
    async def test_match_batch_processes_all_items(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test batch matching processes all items."""
        item_ids = [uuid4(), uuid4(), uuid4()]

        # Different confidence levels for each
        mock_merger_agent.find_matches.side_effect = [
            [MatchResult(product_id=uuid4(), product_name="Auto", confidence=0.95, reasoning="Test", similarity_score=0.9)],  # Auto
            [MatchResult(product_id=uuid4(), product_name="Review", confidence=0.82, reasoning="Test", similarity_score=0.8)],  # Review
            [],  # No match
        ]

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            results, stats = await service.match_batch(item_ids)

            assert len(results) == 3
            assert stats.items_processed == 3
            assert stats.auto_matched == 1
            assert stats.sent_to_review == 1

    @pytest.mark.asyncio
    async def test_match_batch_empty_list(
        self,
        mock_session,
        mock_settings,
    ):
        """Test batch matching with empty list."""
        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent"), \
             patch("src.services.matching_service.SupplierItemsRepository"), \
             patch("src.services.matching_service.MatchReviewRepository"), \
             patch("src.services.matching_service.ParsingLogsRepository"):

            service = MatchingService(mock_session, mock_settings)
            results, stats = await service.match_batch([])

            assert results == []
            assert stats.items_processed == 0

    @pytest.mark.asyncio
    async def test_match_batch_error_isolation(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test that errors in one item don't stop batch processing."""
        item_ids = [uuid4(), uuid4(), uuid4()]

        # Middle item raises error
        mock_merger_agent.find_matches.side_effect = [
            [MatchResult(product_id=uuid4(), product_name="Success", confidence=0.95, reasoning="Test", similarity_score=0.9)],
            Exception("LLM failed"),
            [MatchResult(product_id=uuid4(), product_name="Success", confidence=0.95, reasoning="Test", similarity_score=0.9)],
        ]

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            results, stats = await service.match_batch(item_ids)

            # All items should be processed
            assert len(results) == 3
            assert stats.items_processed == 3
            assert stats.errors == 1
            assert stats.auto_matched == 2


class TestMatchingStats:
    """Tests for MatchingStats dataclass."""

    def test_total_matches(self):
        """Test total_matches calculation."""
        stats = MatchingStats(
            items_processed=10,
            auto_matched=5,
            sent_to_review=3,
            rejected=2,
        )

        assert stats.total_matches == 8

    def test_to_dict(self):
        """Test to_dict conversion."""
        stats = MatchingStats(
            items_processed=10,
            auto_matched=5,
            sent_to_review=3,
            rejected=1,
            errors=1,
        )

        result = stats.to_dict()

        assert result["items_processed"] == 10
        assert result["auto_matched"] == 5
        assert result["sent_to_review"] == 3
        assert result["rejected"] == 1
        assert result["errors"] == 1
        assert result["total_matches"] == 8


class TestItemMatchResult:
    """Tests for ItemMatchResult dataclass."""

    def test_successful_match(self):
        """Test successful match result."""
        match = MatchResult(product_id=uuid4(), product_name="Test", confidence=0.9, reasoning="Test", similarity_score=0.8)
        result = ItemMatchResult(
            supplier_item_id=uuid4(),
            status="auto_matched",
            match=match,
        )

        assert result.status == "auto_matched"
        assert result.match is not None
        assert result.error_message is None

    def test_error_result(self):
        """Test error result."""
        result = ItemMatchResult(
            supplier_item_id=uuid4(),
            status="error",
            error_message="Something went wrong",
        )

        assert result.status == "error"
        assert result.match is None
        assert result.error_message == "Something went wrong"


class TestMatchPendingItems:
    """Tests for match_pending_items method."""

    @pytest.mark.asyncio
    async def test_match_pending_with_supplier_filter(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
        mock_merger_agent,
    ):
        """Test matching pending items filtered by supplier."""
        supplier_id = uuid4()
        pending_items = [
            {"id": uuid4(), "name": "Item 1"},
            {"id": uuid4(), "name": "Item 2"},
        ]
        mock_supplier_items_repo.get_pending_match.return_value = pending_items
        mock_merger_agent.find_matches.return_value = []

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent", return_value=mock_merger_agent), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            results, stats = await service.match_pending_items(
                supplier_id=supplier_id,
                limit=50,
            )

            mock_supplier_items_repo.get_pending_match.assert_called_once_with(
                supplier_id=supplier_id,
                limit=50,
            )
            assert stats.items_processed == 2

    @pytest.mark.asyncio
    async def test_match_pending_no_items(
        self,
        mock_session,
        mock_settings,
        mock_supplier_items_repo,
        mock_match_review_repo,
        mock_parsing_logs_repo,
    ):
        """Test when no pending items exist."""
        mock_supplier_items_repo.get_pending_match.return_value = []

        with patch("src.services.matching_service.VectorService"), \
             patch("src.services.matching_service.MergerAgent"), \
             patch("src.services.matching_service.SupplierItemsRepository", return_value=mock_supplier_items_repo), \
             patch("src.services.matching_service.MatchReviewRepository", return_value=mock_match_review_repo), \
             patch("src.services.matching_service.ParsingLogsRepository", return_value=mock_parsing_logs_repo):

            service = MatchingService(mock_session, mock_settings)
            results, stats = await service.match_pending_items()

            assert results == []
            assert stats.items_processed == 0


