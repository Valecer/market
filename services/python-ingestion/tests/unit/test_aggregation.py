"""Unit tests for aggregation service.

Tests cover:
    - calculate_product_aggregates: single product aggregate calculation
    - calculate_product_aggregates_batch: batch aggregate calculation
    - get_review_queue_stats: review queue statistics
    - Edge cases and error handling
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone

from src.services.aggregation.service import (
    calculate_product_aggregates,
    calculate_product_aggregates_batch,
    get_review_queue_stats,
)
from src.db.models import MatchStatus, ReviewStatus


class TestCalculateProductAggregates:
    """Tests for calculate_product_aggregates function."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session
    
    @pytest.mark.asyncio
    async def test_calculates_min_price_and_availability(self, mock_session):
        """Test that aggregate calculation returns expected values."""
        product_id = uuid4()
        
        # Mock the execute results
        # First call: linked_count_query
        count_result = MagicMock()
        count_result.scalar.return_value = 3
        
        # Second call: update with RETURNING
        update_result = MagicMock()
        update_result.one_or_none.return_value = (Decimal("99.99"), True)
        
        mock_session.execute = AsyncMock(side_effect=[count_result, update_result])
        
        result = await calculate_product_aggregates(
            session=mock_session,
            product_id=product_id,
            trigger="auto_match",
        )
        
        assert result["product_id"] == product_id
        assert result["min_price"] == Decimal("99.99")
        assert result["availability"] is True
        assert result["linked_items_count"] == 3
        assert result["trigger"] == "auto_match"
        assert "error" not in result
    
    @pytest.mark.asyncio
    async def test_handles_product_not_found(self, mock_session):
        """Test handling when product doesn't exist."""
        product_id = uuid4()
        
        # Mock the execute results
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        
        update_result = MagicMock()
        update_result.one_or_none.return_value = None  # Product not found
        
        mock_session.execute = AsyncMock(side_effect=[count_result, update_result])
        
        result = await calculate_product_aggregates(
            session=mock_session,
            product_id=product_id,
            trigger="manual_link",
        )
        
        assert result["product_id"] == product_id
        assert result["min_price"] is None
        assert result["availability"] is False
        assert result["linked_items_count"] == 0
        assert result["error"] == "Product not found"
    
    @pytest.mark.asyncio
    async def test_handles_no_linked_items(self, mock_session):
        """Test handling when product has no linked supplier items."""
        product_id = uuid4()
        
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        
        update_result = MagicMock()
        update_result.one_or_none.return_value = (None, False)
        
        mock_session.execute = AsyncMock(side_effect=[count_result, update_result])
        
        result = await calculate_product_aggregates(
            session=mock_session,
            product_id=product_id,
            trigger="price_change",
        )
        
        assert result["min_price"] is None
        assert result["availability"] is False
        assert result["linked_items_count"] == 0


class TestCalculateProductAggregatesBatch:
    """Tests for calculate_product_aggregates_batch function."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_processes_multiple_products(self, mock_session):
        """Test batch processing of multiple products."""
        product_ids = [uuid4(), uuid4(), uuid4()]
        
        # Mock each product's execution (2 calls per product: count + update)
        mock_results = []
        for i, _ in enumerate(product_ids):
            count_result = MagicMock()
            count_result.scalar.return_value = i + 1  # 1, 2, 3 linked items
            mock_results.append(count_result)
            
            update_result = MagicMock()
            update_result.one_or_none.return_value = (
                Decimal(f"{100 - i * 10}.00"),
                i % 2 == 0,  # Alternating availability
            )
            mock_results.append(update_result)
        
        mock_session.execute = AsyncMock(side_effect=mock_results)
        
        results = await calculate_product_aggregates_batch(
            session=mock_session,
            product_ids=product_ids,
            trigger="auto_match",
        )
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["product_id"] == product_ids[i]
            assert "error" not in result
    
    @pytest.mark.asyncio
    async def test_continues_on_individual_failure(self, mock_session):
        """Test that batch continues processing after individual failures."""
        product_ids = [uuid4(), uuid4(), uuid4()]
        
        # First product: success
        count_result1 = MagicMock()
        count_result1.scalar.return_value = 2
        update_result1 = MagicMock()
        update_result1.one_or_none.return_value = (Decimal("50.00"), True)
        
        # Second product: raises exception
        count_result2 = MagicMock()
        count_result2.scalar.side_effect = Exception("Database connection error")
        
        # Third product: success
        count_result3 = MagicMock()
        count_result3.scalar.return_value = 1
        update_result3 = MagicMock()
        update_result3.one_or_none.return_value = (Decimal("75.00"), False)
        
        mock_session.execute = AsyncMock(
            side_effect=[
                count_result1, update_result1,
                count_result2,  # This will raise
                count_result3, update_result3,
            ]
        )
        
        results = await calculate_product_aggregates_batch(
            session=mock_session,
            product_ids=product_ids,
            trigger="manual_link",
        )
        
        assert len(results) == 3
        # First should succeed
        assert "error" not in results[0]
        # Second should have error
        assert "error" in results[1]
        # Third should succeed
        assert "error" not in results[2]


class TestGetReviewQueueStats:
    """Tests for get_review_queue_stats function."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_returns_status_counts(self, mock_session):
        """Test that stats include counts by status."""
        # Mock status query result
        mock_row1 = MagicMock()
        mock_row1.status = ReviewStatus.PENDING
        mock_row1.count = 10
        
        mock_row2 = MagicMock()
        mock_row2.status = ReviewStatus.APPROVED
        mock_row2.count = 5
        
        mock_row3 = MagicMock()
        mock_row3.status = ReviewStatus.REJECTED
        mock_row3.count = 2
        
        status_result = MagicMock()
        status_result.__iter__ = MagicMock(
            return_value=iter([mock_row1, mock_row2, mock_row3])
        )
        
        # Mock by_supplier query
        supplier_result = MagicMock()
        supplier_result.__iter__ = MagicMock(return_value=iter([]))
        
        # Mock by_category query
        category_result = MagicMock()
        category_result.__iter__ = MagicMock(return_value=iter([]))
        
        mock_session.execute = AsyncMock(
            side_effect=[status_result, supplier_result, category_result]
        )
        
        stats = await get_review_queue_stats(session=mock_session)
        
        assert stats["total"] == 17
        assert stats["pending"] == 10
        assert stats["approved"] == 5
        assert stats["rejected"] == 2
        assert stats["expired"] == 0
        assert stats["needs_category"] == 0
    
    @pytest.mark.asyncio
    async def test_filters_by_supplier(self, mock_session):
        """Test filtering stats by supplier_id."""
        supplier_id = uuid4()
        
        # Mock status query result (filtered by supplier)
        mock_row = MagicMock()
        mock_row.status = ReviewStatus.PENDING
        mock_row.count = 3
        
        status_result = MagicMock()
        status_result.__iter__ = MagicMock(return_value=iter([mock_row]))
        
        # Mock by_category query (still returned since not filtered by category)
        category_result = MagicMock()
        category_result.__iter__ = MagicMock(return_value=iter([]))
        
        mock_session.execute = AsyncMock(
            side_effect=[status_result, category_result]
        )
        
        stats = await get_review_queue_stats(
            session=mock_session,
            supplier_id=supplier_id,
        )
        
        assert stats["pending"] == 3
        # by_supplier should not be included (we filtered by supplier)
        assert "by_supplier" not in stats
    
    @pytest.mark.asyncio
    async def test_filters_by_category(self, mock_session):
        """Test filtering stats by category_id."""
        category_id = uuid4()
        
        # Mock status query result (filtered by category)
        mock_row = MagicMock()
        mock_row.status = ReviewStatus.PENDING
        mock_row.count = 5
        
        status_result = MagicMock()
        status_result.__iter__ = MagicMock(return_value=iter([mock_row]))
        
        # Mock by_supplier query (still returned since not filtered by supplier)
        supplier_result = MagicMock()
        supplier_result.__iter__ = MagicMock(return_value=iter([]))
        
        mock_session.execute = AsyncMock(
            side_effect=[status_result, supplier_result]
        )
        
        stats = await get_review_queue_stats(
            session=mock_session,
            category_id=category_id,
        )
        
        assert stats["pending"] == 5
        # by_category should not be included (we filtered by category)
        assert "by_category" not in stats
    
    @pytest.mark.asyncio
    async def test_includes_breakdown_by_supplier_and_category(self, mock_session):
        """Test that stats include breakdowns when not filtered."""
        # Mock status query result
        mock_row = MagicMock()
        mock_row.status = ReviewStatus.PENDING
        mock_row.count = 10
        
        status_result = MagicMock()
        status_result.__iter__ = MagicMock(return_value=iter([mock_row]))
        
        # Mock by_supplier query
        supplier_id = uuid4()
        supplier_row = MagicMock()
        supplier_row.supplier_id = supplier_id
        supplier_row.count = 5
        
        supplier_result = MagicMock()
        supplier_result.__iter__ = MagicMock(return_value=iter([supplier_row]))
        
        # Mock by_category query
        category_id = uuid4()
        category_row = MagicMock()
        category_row.category_id = category_id
        category_row.count = 3
        
        category_result = MagicMock()
        category_result.__iter__ = MagicMock(return_value=iter([category_row]))
        
        mock_session.execute = AsyncMock(
            side_effect=[status_result, supplier_result, category_result]
        )
        
        stats = await get_review_queue_stats(session=mock_session)
        
        assert "by_supplier" in stats
        assert str(supplier_id) in stats["by_supplier"]
        assert stats["by_supplier"][str(supplier_id)] == 5
        
        assert "by_category" in stats
        assert str(category_id) in stats["by_category"]
        assert stats["by_category"][str(category_id)] == 3


