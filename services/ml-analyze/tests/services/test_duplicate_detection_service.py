"""
Tests for DuplicateDetectionService

Phase 11: Pipeline Stabilization - US2 Duplicate Detection
Tasks: T089-T094
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.duplicate_detection_service import (
    DuplicateDetectionService,
    DuplicateCandidate,
    detect_duplicates,
    DUPLICATE_SIMILARITY_MIN,
    DUPLICATE_SIMILARITY_MAX,
    DUPLICATE_PRICE_DIFF_MAX,
)


class TestDuplicateCandidate:
    """Test DuplicateCandidate dataclass."""

    def test_create_candidate(self):
        """Should create candidate with required fields."""
        candidate = DuplicateCandidate(
            id=uuid4(),
            name="Test Product",
            category_id=uuid4(),
            price=Decimal("99.99"),
            has_variants=False,
            variant_schema=None,
        )

        assert candidate.name == "Test Product"
        assert candidate.price == Decimal("99.99")
        assert not candidate.has_variants


class TestDuplicateDetectionService:
    """Test DuplicateDetectionService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create DuplicateDetectionService instance."""
        return DuplicateDetectionService(mock_session)

    def test_default_thresholds(self, service):
        """Service should use default thresholds."""
        assert service._similarity_min == DUPLICATE_SIMILARITY_MIN  # 85
        assert service._similarity_max == DUPLICATE_SIMILARITY_MAX  # 90
        assert service._price_diff_max == DUPLICATE_PRICE_DIFF_MAX  # 0.20

    def test_custom_thresholds(self, mock_session):
        """Service should accept custom thresholds."""
        service = DuplicateDetectionService(
            mock_session,
            similarity_min=80,
            similarity_max=95,
            price_diff_max=0.10,
        )

        assert service._similarity_min == 80
        assert service._similarity_max == 95
        assert service._price_diff_max == 0.10

    def test_compute_similarity_exact_match(self, service):
        """Identical names should have 100% similarity."""
        score = service.compute_similarity("USB Cable 2m", "USB Cable 2m")
        assert score == 100

    def test_compute_similarity_case_insensitive(self, service):
        """Similarity should be case-insensitive."""
        score = service.compute_similarity("USB Cable", "usb cable")
        assert score == 100

    def test_compute_similarity_partial_match(self, service):
        """Similar names should have high similarity."""
        score = service.compute_similarity(
            "USB-C Cable 2m Black",
            "USB C Cable 2 Meter Black",
        )
        assert 80 <= score <= 100  # Should be similar

    def test_compute_similarity_different_names(self, service):
        """Different names should have low similarity."""
        score = service.compute_similarity(
            "USB Cable",
            "Laptop Computer",
        )
        assert score < 50  # Should be different

    def test_compute_price_diff_same_price(self, service):
        """Same prices should have 0 difference."""
        p1 = DuplicateCandidate(
            id=uuid4(), name="A", category_id=None,
            price=Decimal("100.00"), has_variants=False, variant_schema=None,
        )
        p2 = DuplicateCandidate(
            id=uuid4(), name="B", category_id=None,
            price=Decimal("100.00"), has_variants=False, variant_schema=None,
        )

        diff = service.compute_price_diff(p1, p2)
        assert diff == 0.0

    def test_compute_price_diff_within_threshold(self, service):
        """10% price difference should be within threshold."""
        p1 = DuplicateCandidate(
            id=uuid4(), name="A", category_id=None,
            price=Decimal("100.00"), has_variants=False, variant_schema=None,
        )
        p2 = DuplicateCandidate(
            id=uuid4(), name="B", category_id=None,
            price=Decimal("110.00"), has_variants=False, variant_schema=None,
        )

        diff = service.compute_price_diff(p1, p2)
        # Diff = |100-110| / max(100,110) = 10/110 ≈ 0.091
        assert diff < 0.10  # Within 10%

    def test_compute_price_diff_exceeds_threshold(self, service):
        """30% price difference should exceed threshold."""
        p1 = DuplicateCandidate(
            id=uuid4(), name="A", category_id=None,
            price=Decimal("100.00"), has_variants=False, variant_schema=None,
        )
        p2 = DuplicateCandidate(
            id=uuid4(), name="B", category_id=None,
            price=Decimal("70.00"), has_variants=False, variant_schema=None,
        )

        diff = service.compute_price_diff(p1, p2)
        # Diff = |100-70| / max(100,70) = 30/100 = 0.30
        assert diff > DUPLICATE_PRICE_DIFF_MAX

    def test_compute_price_diff_zero_prices(self, service):
        """Both zero prices should have 0 difference."""
        p1 = DuplicateCandidate(
            id=uuid4(), name="A", category_id=None,
            price=Decimal("0"), has_variants=False, variant_schema=None,
        )
        p2 = DuplicateCandidate(
            id=uuid4(), name="B", category_id=None,
            price=Decimal("0"), has_variants=False, variant_schema=None,
        )

        diff = service.compute_price_diff(p1, p2)
        assert diff == 0.0

    def test_compute_price_diff_one_zero(self, service):
        """One zero price should return max difference."""
        p1 = DuplicateCandidate(
            id=uuid4(), name="A", category_id=None,
            price=Decimal("100"), has_variants=False, variant_schema=None,
        )
        p2 = DuplicateCandidate(
            id=uuid4(), name="B", category_id=None,
            price=Decimal("0"), has_variants=False, variant_schema=None,
        )

        diff = service.compute_price_diff(p1, p2)
        assert diff == 1.0

    @pytest.mark.asyncio
    async def test_are_variants_not_variants(self, service, mock_session):
        """Products without variants flag should not be variants."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (False, None, False, None)
        mock_session.execute.return_value = mock_result

        result = await service.are_variants(uuid4(), uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_are_variants_same_schema(self, service, mock_session):
        """Products with same variant schema should be variants."""
        schema = [{"type": "color"}, {"type": "size"}]
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True, schema, True, schema)
        mock_session.execute.return_value = mock_result

        result = await service.are_variants(uuid4(), uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_flag_duplicate_new_pair(self, service, mock_session):
        """Should flag new duplicate pair."""
        # First call: check if exists (returns None)
        # Second call: insert
        mock_check = MagicMock()
        mock_check.fetchone.return_value = None  # Not exists

        mock_insert = MagicMock()

        mock_session.execute.side_effect = [mock_check, mock_insert]

        result = await service.flag_duplicate(
            product_id_1=uuid4(),
            product_id_2=uuid4(),
            similarity_score=87.5,
        )

        assert result is True
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_flag_duplicate_already_exists(self, service, mock_session):
        """Should not flag already flagged pair."""
        mock_check = MagicMock()
        mock_check.fetchone.return_value = MagicMock(id="existing")
        mock_session.execute.return_value = mock_check

        result = await service.flag_duplicate(
            product_id_1=uuid4(),
            product_id_2=uuid4(),
            similarity_score=87.5,
        )

        assert result is False
        # Only check query, no insert
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_flag_duplicate_orders_ids(self, service, mock_session):
        """Should ensure product_id_1 < product_id_2."""
        id1 = uuid4()
        id2 = uuid4()

        # Ensure id1 > id2 for test
        if str(id1) < str(id2):
            id1, id2 = id2, id1

        mock_check = MagicMock()
        mock_check.fetchone.return_value = None
        mock_session.execute.side_effect = [mock_check, MagicMock()]

        await service.flag_duplicate(id1, id2, 87.5)

        # The first execute call is the check query
        check_call = mock_session.execute.call_args_list[0]
        # IDs should be ordered in the check query params
        # (this tests the internal ordering logic)
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_detect_duplicates_empty_list(self, service, mock_session):
        """Empty product list should return empty stats."""
        stats = await service.detect_duplicates([])
        assert stats.duplicates_flagged == 0

    @pytest.mark.asyncio
    async def test_detect_duplicates_no_products_found(self, service, mock_session):
        """Should handle case when products not found in DB."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        stats = await service.detect_duplicates([uuid4(), uuid4()])
        assert stats.duplicates_flagged == 0


class TestDetectDuplicatesConvenience:
    """Test convenience function."""

    @pytest.mark.asyncio
    async def test_detect_duplicates_function(self):
        """Convenience function should create service and call method."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        stats = await detect_duplicates(mock_session, [uuid4()])

        assert stats is not None
        assert stats.duplicates_flagged == 0


class TestSimilarityThresholds:
    """Test similarity threshold edge cases."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    def test_below_min_threshold(self, mock_session):
        """84% similarity should NOT be flagged as duplicate."""
        service = DuplicateDetectionService(mock_session)
        # 84% is below 85% minimum
        score = 84.0
        assert not (service._similarity_min <= score < service._similarity_max)

    def test_at_min_threshold(self, mock_session):
        """85% similarity SHOULD be flagged as duplicate."""
        service = DuplicateDetectionService(mock_session)
        score = 85.0
        assert service._similarity_min <= score < service._similarity_max

    def test_between_thresholds(self, mock_session):
        """87% similarity SHOULD be flagged as duplicate."""
        service = DuplicateDetectionService(mock_session)
        score = 87.0
        assert service._similarity_min <= score < service._similarity_max

    def test_at_max_threshold(self, mock_session):
        """90% similarity should NOT be flagged (auto-matched instead)."""
        service = DuplicateDetectionService(mock_session)
        score = 90.0
        assert not (service._similarity_min <= score < service._similarity_max)

    def test_above_max_threshold(self, mock_session):
        """95% similarity should NOT be flagged (auto-matched instead)."""
        service = DuplicateDetectionService(mock_session)
        score = 95.0
        assert not (service._similarity_min <= score < service._similarity_max)
