"""
Tests for AutoCreationService

Phase 11: Pipeline Stabilization - US2 Auto-Creation
Tasks: T085-T088
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.auto_creation_service import (
    AutoCreationService,
    AutoCreationStats,
    auto_create_product,
)
from src.schemas.extraction import ExtractedProduct


class TestAutoCreationStats:
    """Test AutoCreationStats dataclass."""

    def test_default_values(self):
        """Stats should initialize with zero counts."""
        stats = AutoCreationStats()
        assert stats.products_created == 0
        assert stats.supplier_items_linked == 0
        assert stats.errors == 0

    def test_to_dict(self):
        """Stats should convert to dictionary."""
        stats = AutoCreationStats(
            products_created=5,
            supplier_items_linked=10,
            errors=2,
        )
        result = stats.to_dict()
        assert result == {
            "products_created": 5,
            "supplier_items_linked": 10,
            "errors": 2,
            "variant_groups_created": 0,
            "products_grouped": 0,
        }


class TestAutoCreationService:
    """Test AutoCreationService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create AutoCreationService instance."""
        return AutoCreationService(mock_session)

    @pytest.fixture
    def sample_extraction(self):
        """Create sample ExtractedProduct."""
        return ExtractedProduct(
            name="Test Product - ML Cleaned",
            price_rrc=99.99,
            price_opt=89.99,
            category_path=["Electronics", "Gadgets"],
            variant_attributes={"color": "red"},
        )

    def test_generate_internal_sku(self):
        """SKU should have AUTO-{8char} format."""
        sku = AutoCreationService.generate_internal_sku()

        assert sku.startswith("AUTO-")
        assert len(sku) == 13  # AUTO- (5) + 8 hex chars
        assert sku[5:].isupper()  # hex should be uppercase

    def test_generate_internal_sku_uniqueness(self):
        """Generated SKUs should be unique."""
        skus = {AutoCreationService.generate_internal_sku() for _ in range(100)}
        assert len(skus) == 100  # All unique

    def test_stats_tracking(self, service):
        """Service should track creation statistics."""
        assert service.get_stats().products_created == 0

    def test_reset_stats(self, service):
        """Stats should reset to zero."""
        service._stats.products_created = 10
        service.reset_stats()
        assert service.get_stats().products_created == 0

    @pytest.mark.asyncio
    async def test_create_product_from_extraction(self, service, sample_extraction, mock_session):
        """Should create product with correct data."""
        supplier_item_id = uuid4()
        category_id = uuid4()

        # Mock database responses
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(created_at="2025-01-01T00:00:00Z")
        mock_session.execute.return_value = mock_result

        with patch.object(service, '_log_auto_creation_event'):
            result = await service.create_product_from_extraction(
                extraction=sample_extraction,
                supplier_item_id=supplier_item_id,
                category_id=category_id,
            )

        assert result["name"] == sample_extraction.name
        assert result["internal_sku"].startswith("AUTO-")
        assert result["category_id"] == category_id
        assert result["status"] == "active"

        # Verify DB calls
        assert mock_session.execute.call_count == 2  # INSERT + UPDATE
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_create_product_updates_stats(self, service, sample_extraction, mock_session):
        """Stats should increment after successful creation."""
        supplier_item_id = uuid4()

        # Mock database
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(created_at="2025-01-01T00:00:00Z")
        mock_session.execute.return_value = mock_result

        with patch.object(service, '_log_auto_creation_event'):
            await service.create_product_from_extraction(
                extraction=sample_extraction,
                supplier_item_id=supplier_item_id,
            )

        stats = service.get_stats()
        assert stats.products_created == 1
        assert stats.supplier_items_linked == 1
        assert stats.errors == 0

    @pytest.mark.asyncio
    async def test_create_product_handles_error(self, service, sample_extraction, mock_session):
        """Should rollback and increment error count on failure."""
        supplier_item_id = uuid4()

        mock_session.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await service.create_product_from_extraction(
                extraction=sample_extraction,
                supplier_item_id=supplier_item_id,
            )

        assert mock_session.rollback.called
        assert service.get_stats().errors == 1

    @pytest.mark.asyncio
    async def test_create_products_batch(self, service, sample_extraction, mock_session):
        """Should process multiple products with error isolation."""
        # Mock database
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(created_at="2025-01-01T00:00:00Z")
        mock_session.execute.return_value = mock_result

        extractions = [
            (sample_extraction, uuid4(), uuid4()),
            (sample_extraction, uuid4(), uuid4()),
            (sample_extraction, uuid4(), None),
        ]

        with patch.object(service, '_log_auto_creation_event'):
            results = await service.create_products_batch(extractions)

        assert len(results) == 3
        stats = service.get_stats()
        assert stats.products_created == 3


class TestAutoCreateProductConvenience:
    """Test convenience function."""

    @pytest.mark.asyncio
    async def test_auto_create_product(self):
        """Convenience function should create service and call method."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(created_at="2025-01-01T00:00:00Z")
        mock_session.execute.return_value = mock_result

        extraction = ExtractedProduct(
            name="Test Product",
            price_rrc=10.0,
        )

        result = await auto_create_product(
            session=mock_session,
            extraction=extraction,
            supplier_item_id=uuid4(),
        )

        assert result is not None
        assert "internal_sku" in result
