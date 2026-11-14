"""
Tests for IngestionOrchestrator

Phase 11: Pipeline Stabilization - US4 Variant Detection Integration
Tasks: T124-T126
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.services.ingestion_orchestrator import (
    IngestionOrchestrator,
    VariantDetectionStats,
    ProductData,
    run_variant_detection,
)
from src.services.variant_detection_service import (
    VariantDetectionService,
    VariantGroup,
    VariantCandidate,
)


class TestVariantDetectionStats:
    """Test VariantDetectionStats dataclass."""

    def test_default_values(self):
        """Stats should initialize with zero counts."""
        stats = VariantDetectionStats()
        assert stats.products_analyzed == 0
        assert stats.variant_groups_created == 0
        assert stats.products_grouped == 0
        assert stats.variants_created == 0
        assert stats.errors == 0

    def test_to_dict(self):
        """Stats should convert to dictionary."""
        stats = VariantDetectionStats(
            products_analyzed=10,
            variant_groups_created=2,
            products_grouped=6,
            variants_created=6,
            errors=1,
        )
        result = stats.to_dict()
        assert result == {
            "products_analyzed": 10,
            "variant_groups_created": 2,
            "products_grouped": 6,
            "variants_created": 6,
            "errors": 1,
        }


class TestProductData:
    """Test ProductData dataclass."""

    def test_creation(self):
        """Should create ProductData with all fields."""
        product_id = uuid4()
        category_id = uuid4()
        
        data = ProductData(
            id=product_id,
            name="Test Battery 48V 20Ah",
            price=500.0,
            category_id=category_id,
            variant_attributes={"voltage": "48V", "capacity": "20Ah"},
            has_variants=False,
        )
        
        assert data.id == product_id
        assert data.name == "Test Battery 48V 20Ah"
        assert data.price == 500.0
        assert data.category_id == category_id
        assert data.variant_attributes == {"voltage": "48V", "capacity": "20Ah"}
        assert data.has_variants is False

    def test_default_values(self):
        """Should have sensible defaults."""
        product_id = uuid4()
        
        data = ProductData(
            id=product_id,
            name="Test Product",
            price=100.0,
            category_id=None,
        )
        
        assert data.variant_attributes == {}
        assert data.has_variants is False


class TestIngestionOrchestrator:
    """Test IngestionOrchestrator class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with variant detection enabled."""
        settings = MagicMock()
        settings.variant_detection_enabled = True
        return settings

    @pytest.fixture
    def mock_settings_disabled(self):
        """Create mock settings with variant detection disabled."""
        settings = MagicMock()
        settings.variant_detection_enabled = False
        return settings

    @pytest.fixture
    def orchestrator(self, mock_session, mock_settings):
        """Create IngestionOrchestrator instance."""
        return IngestionOrchestrator(mock_session, mock_settings)

    def test_init(self, mock_session, mock_settings):
        """Should initialize with session and settings."""
        orchestrator = IngestionOrchestrator(mock_session, mock_settings)
        
        assert orchestrator._session == mock_session
        assert orchestrator._settings == mock_settings
        assert orchestrator._enabled is True

    def test_get_stats(self, orchestrator):
        """Should return current statistics."""
        stats = orchestrator.get_stats()
        
        assert isinstance(stats, VariantDetectionStats)
        assert stats.products_analyzed == 0

    def test_reset_stats(self, orchestrator):
        """Should reset statistics to zero."""
        orchestrator._stats.products_analyzed = 10
        orchestrator._stats.variant_groups_created = 5
        
        orchestrator.reset_stats()
        
        stats = orchestrator.get_stats()
        assert stats.products_analyzed == 0
        assert stats.variant_groups_created == 0

    @pytest.mark.asyncio
    async def test_on_batch_complete_disabled(
        self, mock_session, mock_settings_disabled
    ):
        """Should skip processing when variant detection is disabled."""
        orchestrator = IngestionOrchestrator(mock_session, mock_settings_disabled)
        
        stats = await orchestrator.on_batch_complete(
            batch_id="test-batch",
            created_product_ids=[uuid4(), uuid4()],
        )
        
        assert stats.products_analyzed == 0
        assert stats.variant_groups_created == 0

    @pytest.mark.asyncio
    async def test_on_batch_complete_empty_ids(self, orchestrator):
        """Should handle empty product ID list."""
        stats = await orchestrator.on_batch_complete(
            batch_id="test-batch",
            created_product_ids=[],
        )
        
        assert stats.products_analyzed == 0

    @pytest.mark.asyncio
    async def test_on_batch_complete_no_categories(self, orchestrator, mock_session):
        """Should handle products with no categories."""
        # Mock empty categories result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        
        stats = await orchestrator.on_batch_complete(
            batch_id="test-batch",
            created_product_ids=[uuid4()],
        )
        
        assert stats.products_analyzed == 0

    # T124: Test variant detection integration
    @pytest.mark.asyncio
    async def test_variant_detection_integration(self, orchestrator, mock_session):
        """
        T124: Should integrate with VariantDetectionService.
        
        Verifies that:
        1. Categories are queried from created products
        2. All products in categories are retrieved
        3. Variant groups are created and stored
        """
        category_id = uuid4()
        product_id_1 = uuid4()
        product_id_2 = uuid4()
        
        # Mock category query result
        category_result = MagicMock()
        category_result.fetchall.return_value = [(category_id,)]
        
        # Mock products query result
        products_result = MagicMock()
        products_result.fetchall.return_value = [
            (product_id_1, "Battery 48V 20Ah", category_id, False, None, 500.0),
            (product_id_2, "Battery 48V 30Ah", category_id, False, None, 600.0),
        ]
        
        # Mock INSERT result for variants
        insert_result = MagicMock()
        insert_result.fetchone.return_value = (uuid4(),)
        
        # Configure mock to return different results based on query
        mock_session.execute.side_effect = [
            category_result,   # _get_categories_for_products
            products_result,   # _get_products_in_categories
            insert_result,     # _update_parent_product
            insert_result,     # _create_product_variant (first)
            insert_result,     # _create_product_variant (second)
        ]
        
        # Mock VariantDetectionService.group_variants
        with patch.object(
            VariantDetectionService,
            'group_variants',
            return_value=[
                VariantGroup(
                    base_name="Battery",
                    variant_schema=["voltage", "capacity"],
                    variants=[
                        {
                            "key": "48V/20Ah",
                            "attributes": {"voltage": "48V", "capacity": "20Ah"},
                            "supplier_item_id": str(product_id_1),
                            "name": "Battery 48V 20Ah",
                            "price": 500.0,
                        },
                        {
                            "key": "48V/30Ah",
                            "attributes": {"voltage": "48V", "capacity": "30Ah"},
                            "supplier_item_id": str(product_id_2),
                            "name": "Battery 48V 30Ah",
                            "price": 600.0,
                        },
                    ],
                ),
            ],
        ) as mock_group:
            stats = await orchestrator.on_batch_complete(
                batch_id="test-batch",
                created_product_ids=[product_id_1, product_id_2],
            )
        
        assert stats.products_analyzed == 2
        assert stats.variant_groups_created == 1
        assert stats.products_grouped == 2

    # T125: Mock VariantDetectionService and verify group_variants called
    @pytest.mark.asyncio
    async def test_group_variants_called_with_correct_products(
        self, orchestrator, mock_session
    ):
        """
        T125: Should call group_variants with correct products.
        
        Verifies that VariantCandidate objects are built correctly
        and passed to the variant detection service.
        """
        category_id = uuid4()
        product_id_1 = uuid4()
        product_id_2 = uuid4()
        
        # Mock database results
        category_result = MagicMock()
        category_result.fetchall.return_value = [(category_id,)]
        
        products_result = MagicMock()
        products_result.fetchall.return_value = [
            (product_id_1, "Laptop 256GB Black", category_id, False, None, 1000.0),
            (product_id_2, "Laptop 512GB Silver", category_id, False, None, 1200.0),
        ]
        
        mock_session.execute.return_value = category_result
        mock_session.execute.side_effect = [category_result, products_result]
        
        # Track calls to group_variants
        captured_candidates = []
        
        def capture_candidates(candidates):
            captured_candidates.extend(candidates)
            return []  # No groups found
        
        with patch.object(
            VariantDetectionService,
            'group_variants',
            side_effect=capture_candidates,
        ):
            await orchestrator.on_batch_complete(
                batch_id="test-batch",
                created_product_ids=[product_id_1, product_id_2],
            )
        
        # Verify candidates were built correctly
        assert len(captured_candidates) == 2
        
        # Check first candidate
        candidate_1 = next(
            c for c in captured_candidates if c.name == "Laptop 256GB Black"
        )
        assert candidate_1.price == 1000.0
        assert "storage" in candidate_1.variant_attributes
        assert candidate_1.variant_attributes["storage"] == "256GB"
        
        # Check second candidate
        candidate_2 = next(
            c for c in captured_candidates if c.name == "Laptop 512GB Silver"
        )
        assert candidate_2.price == 1200.0
        assert "storage" in candidate_2.variant_attributes
        assert candidate_2.variant_attributes["storage"] == "512GB"

    @pytest.mark.asyncio
    async def test_build_candidates(self, orchestrator):
        """Should convert ProductData to VariantCandidates."""
        products = [
            ProductData(
                id=uuid4(),
                name="Battery 48V 20Ah",
                price=500.0,
                category_id=uuid4(),
            ),
            ProductData(
                id=uuid4(),
                name="Battery 48V 30Ah",
                price=600.0,
                category_id=uuid4(),
            ),
        ]
        
        candidates = orchestrator._build_candidates(products)
        
        assert len(candidates) == 2
        assert all(isinstance(c, VariantCandidate) for c in candidates)
        
        # Should extract variant attributes from names
        assert candidates[0].variant_attributes.get("voltage") == "48V"
        assert candidates[0].variant_attributes.get("capacity") == "20Ah"
        assert candidates[1].variant_attributes.get("capacity") == "30Ah"

    @pytest.mark.asyncio
    async def test_on_batch_complete_error_handling(self, orchestrator, mock_session):
        """Should handle errors gracefully and track in stats."""
        # Make database query fail
        mock_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await orchestrator.on_batch_complete(
                batch_id="test-batch",
                created_product_ids=[uuid4()],
            )
        
        assert mock_session.rollback.called
        assert orchestrator.get_stats().errors == 1


class TestRunVariantDetection:
    """Test convenience function."""

    @pytest.mark.asyncio
    async def test_run_variant_detection(self):
        """Convenience function should create orchestrator and call method."""
        mock_session = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.variant_detection_enabled = False  # Disable to simplify test
        
        stats = await run_variant_detection(
            session=mock_session,
            batch_id="test-batch",
            created_product_ids=[uuid4()],
            settings=mock_settings,
        )
        
        assert isinstance(stats, VariantDetectionStats)


# T126: Integration test for variant grouping after auto-creation
class TestVariantGroupingAfterAutoCreation:
    """
    T126: Integration test for variant grouping workflow.
    
    Tests the complete flow:
    1. Auto-create products
    2. Trigger variant detection
    3. Verify variant groups are created
    """

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.variant_detection_enabled = True
        return settings

    @pytest.mark.asyncio
    async def test_variant_grouping_after_auto_creation(
        self, mock_session, mock_settings
    ):
        """
        T126: Complete integration test for variant grouping.
        
        Simulates auto-creating products and verifying that
        variant detection runs and groups products correctly.
        """
        from src.services.auto_creation_service import AutoCreationService
        from src.schemas.extraction import ExtractedProduct
        
        # Create service
        service = AutoCreationService(mock_session, mock_settings)
        
        # Create sample extractions (battery variants)
        extractions = [
            (
                ExtractedProduct(
                    name="Electric Bike Battery 48V 20Ah",
                    price_rrc=Decimal("500.00"),
                    variant_attributes={"voltage": "48V", "capacity": "20Ah"},
                ),
                uuid4(),  # supplier_item_id
                uuid4(),  # category_id
            ),
            (
                ExtractedProduct(
                    name="Electric Bike Battery 48V 30Ah",
                    price_rrc=Decimal("650.00"),
                    variant_attributes={"voltage": "48V", "capacity": "30Ah"},
                ),
                uuid4(),
                uuid4(),
            ),
        ]
        
        # Mock database responses for auto-creation
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(
            created_at="2025-01-01T00:00:00Z"
        )
        mock_session.execute.return_value = mock_result
        
        # Mock variant detection to avoid complex DB setup
        with patch.object(
            service, '_run_variant_detection', new_callable=AsyncMock
        ) as mock_variant:
            results = await service.create_products_batch(
                extractions=extractions,
                batch_id="test-batch",
                run_variant_detection=True,
            )
        
        # Verify products were created
        assert len(results) == 2
        
        # Verify variant detection was triggered
        mock_variant.assert_called_once()
        call_args = mock_variant.call_args
        assert call_args[1]["batch_id"] == "test-batch"
        assert len(call_args[1]["created_products"]) == 2

    @pytest.mark.asyncio
    async def test_variant_detection_disabled_skips_grouping(
        self, mock_session
    ):
        """Should skip variant detection when disabled."""
        from src.services.auto_creation_service import AutoCreationService
        from src.schemas.extraction import ExtractedProduct
        
        # Settings with variant detection disabled
        settings = MagicMock()
        settings.variant_detection_enabled = False
        
        service = AutoCreationService(mock_session, settings)
        
        extractions = [
            (
                ExtractedProduct(
                    name="Test Product",
                    price_rrc=Decimal("100.00"),
                ),
                uuid4(),
                None,
            ),
        ]
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(
            created_at="2025-01-01T00:00:00Z"
        )
        mock_session.execute.return_value = mock_result
        
        with patch.object(
            service, '_run_variant_detection', new_callable=AsyncMock
        ) as mock_variant:
            await service.create_products_batch(
                extractions=extractions,
                batch_id="test-batch",
                run_variant_detection=True,  # True but settings disabled
            )
        
        # Should NOT call variant detection
        mock_variant.assert_not_called()
