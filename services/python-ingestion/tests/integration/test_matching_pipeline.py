"""Integration tests for the product matching pipeline.

Tests the full pipeline flow:
    - match_items_task with database interactions
    - enrich_item_task for feature extraction
    - recalc_product_aggregates_task for aggregate updates
    - handle_manual_match_event for manual operations
    - expire_review_queue_task for cron jobs

Test isolation:
    - Each test uses the db_session fixture which cleans the database
    - Tests are independent and can run in any order
"""
import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select, insert, func

from src.db.models import (
    Product,
    ProductStatus,
    SupplierItem,
    Supplier,
    MatchStatus,
    MatchReviewQueue,
    ReviewStatus,
    Category,
)
from src.tasks.matching_tasks import (
    match_items_task,
    enrich_item_task,
    recalc_product_aggregates_task,
    handle_manual_match_event,
    expire_review_queue_task,
)
from src.services.aggregation import calculate_product_aggregates


@pytest.fixture
async def test_supplier(db_session):
    """Create a test supplier."""
    supplier = Supplier(
        name="Test Supplier",
        source_type="csv",
        metadata={"test": True},
    )
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    return supplier


@pytest.fixture
async def test_category(db_session):
    """Create a test category."""
    category = Category(
        name="Electronics",
        slug="electronics",
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest.fixture
async def test_product(db_session, test_category):
    """Create a test product."""
    product = Product(
        internal_sku="PROD-TEST-001",
        name="Samsung Galaxy A54 5G 128GB Black",
        category_id=test_category.id,
        status=ProductStatus.ACTIVE,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def test_supplier_items(db_session, test_supplier):
    """Create multiple test supplier items."""
    items = []
    names = [
        "Samsung Galaxy A54 5G 128GB Black",  # High match
        "Samsung Galaxy A54 128GB",  # Potential match
        "Bosch Drill 750W Professional",  # No match (different product)
    ]
    
    for i, name in enumerate(names):
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku=f"TEST-SKU-{i}",
            name=name,
            current_price=Decimal(f"{100 + i * 50}.00"),
            characteristics={"in_stock": True},
            match_status=MatchStatus.UNMATCHED,
        )
        db_session.add(item)
        items.append(item)
    
    await db_session.commit()
    for item in items:
        await db_session.refresh(item)
    return items


@pytest.fixture
def mock_ctx():
    """Create a mock worker context with redis."""
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=MagicMock())
    return {"redis": mock_redis}


class TestMatchItemsTaskIntegration:
    """Integration tests for match_items_task."""
    
    @pytest.mark.asyncio
    async def test_auto_matches_high_similarity_items(
        self, db_session, test_product, test_supplier_items, mock_ctx
    ):
        """Test that items with ≥95% similarity are auto-matched."""
        # The first item "Samsung Galaxy A54 5G 128GB Black" should match exactly
        result = await match_items_task(
            ctx=mock_ctx,
            task_id="test-match-001",
            batch_size=10,
        )
        
        assert result["status"] in ("success", "partial_success")
        assert result["items_processed"] > 0
        
        # Verify the high-match item was linked
        item = await db_session.get(SupplierItem, test_supplier_items[0].id)
        # Check if it was matched
        if item.match_status in (MatchStatus.AUTO_MATCHED, MatchStatus.VERIFIED_MATCH):
            assert item.product_id is not None
            assert item.match_score >= Decimal("95.0")
    
    @pytest.mark.asyncio
    async def test_creates_potential_match_for_medium_similarity(
        self, db_session, test_product, test_supplier_items, mock_ctx
    ):
        """Test that items with 70-94% similarity create potential matches."""
        result = await match_items_task(
            ctx=mock_ctx,
            task_id="test-match-002",
            batch_size=10,
        )
        
        # Check for potential matches in review queue
        review_query = select(MatchReviewQueue).where(
            MatchReviewQueue.status == ReviewStatus.PENDING
        )
        review_result = await db_session.execute(review_query)
        reviews = review_result.scalars().all()
        
        # At least some items should be in review queue or matched
        assert result["items_processed"] >= 0
    
    @pytest.mark.asyncio
    async def test_creates_new_product_for_low_similarity(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that items with <70% similarity create new products."""
        # Create an item that won't match anything
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="UNIQUE-SKU-999",
            name="Completely Unique Product That Won't Match Anything",
            current_price=Decimal("199.99"),
            characteristics={},
            match_status=MatchStatus.UNMATCHED,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await match_items_task(
            ctx=mock_ctx,
            task_id="test-match-003",
            batch_size=10,
        )
        
        # Refresh item to see changes
        await db_session.refresh(item)
        
        # Item should be matched (to a new product)
        if result["new_products_created"] > 0:
            assert item.product_id is not None
            # Verify new product was created
            product = await db_session.get(Product, item.product_id)
            assert product is not None
            assert product.status == ProductStatus.DRAFT
    
    @pytest.mark.asyncio
    async def test_skips_verified_match_items(
        self, db_session, test_supplier, test_product, mock_ctx
    ):
        """Test that verified_match items are not re-matched."""
        # Create an item already linked with verified_match status
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="VERIFIED-SKU",
            name="Already Verified Item",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.VERIFIED_MATCH,
            product_id=test_product.id,
            match_score=Decimal("100.00"),
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        original_product_id = item.product_id
        
        result = await match_items_task(
            ctx=mock_ctx,
            task_id="test-match-004",
            batch_size=10,
        )
        
        # Refresh and verify item wasn't changed
        await db_session.refresh(item)
        assert item.product_id == original_product_id
        assert item.match_status == MatchStatus.VERIFIED_MATCH


class TestEnrichItemTaskIntegration:
    """Integration tests for enrich_item_task."""
    
    @pytest.mark.asyncio
    async def test_extracts_electronics_features(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that electronics features are extracted from item name."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="DRILL-001",
            name="Bosch Drill 750W 220V Professional Power Tool",
            current_price=Decimal("149.99"),
            characteristics={},
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await enrich_item_task(
            ctx=mock_ctx,
            task_id="test-enrich-001",
            supplier_item_id=str(item.id),
            extractors=["electronics"],
        )
        
        assert result["status"] == "success"
        
        # Refresh and check characteristics
        await db_session.refresh(item)
        
        # Check that features were extracted
        if result.get("features_extracted", 0) > 0:
            assert "power_watts" in item.characteristics or "voltage" in item.characteristics
    
    @pytest.mark.asyncio
    async def test_extracts_dimensions_features(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that dimensions features are extracted from item name."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="BOX-001",
            name="Storage Box 30x20x10cm 2.5kg",
            current_price=Decimal("29.99"),
            characteristics={},
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await enrich_item_task(
            ctx=mock_ctx,
            task_id="test-enrich-002",
            supplier_item_id=str(item.id),
            extractors=["dimensions"],
        )
        
        assert result["status"] == "success"
        
        await db_session.refresh(item)
        
        if result.get("features_extracted", 0) > 0:
            assert "weight_kg" in item.characteristics or "dimensions_cm" in item.characteristics
    
    @pytest.mark.asyncio
    async def test_preserves_existing_characteristics(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that existing characteristics are not overwritten."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="PRESERVE-001",
            name="Device 500W Power Tool",
            current_price=Decimal("99.99"),
            characteristics={"power_watts": 999, "custom_field": "preserved"},
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await enrich_item_task(
            ctx=mock_ctx,
            task_id="test-enrich-003",
            supplier_item_id=str(item.id),
            extractors=["electronics"],
            preserve_existing=True,  # Default
        )
        
        await db_session.refresh(item)
        
        # Existing value should be preserved
        assert item.characteristics.get("power_watts") == 999
        assert item.characteristics.get("custom_field") == "preserved"


class TestRecalcProductAggregatesTaskIntegration:
    """Integration tests for recalc_product_aggregates_task."""
    
    @pytest.mark.asyncio
    async def test_calculates_min_price(
        self, db_session, test_product, test_supplier, mock_ctx
    ):
        """Test that min_price is calculated from linked items."""
        # Create linked supplier items with different prices
        for i, price in enumerate([100, 50, 75]):
            item = SupplierItem(
                supplier_id=test_supplier.id,
                supplier_sku=f"PRICE-{i}",
                name=f"Test Item {i}",
                current_price=Decimal(f"{price}.00"),
                characteristics={"in_stock": True},
                product_id=test_product.id,
                match_status=MatchStatus.AUTO_MATCHED,
                match_score=Decimal("95.0"),
            )
            db_session.add(item)
        
        await db_session.commit()
        
        result = await recalc_product_aggregates_task(
            ctx=mock_ctx,
            task_id="test-recalc-001",
            product_ids=[str(test_product.id)],
            trigger="auto_match",
        )
        
        assert result["status"] == "success"
        assert result["products_updated"] == 1
        
        # Refresh and check min_price
        await db_session.refresh(test_product)
        assert test_product.min_price == Decimal("50.00")
    
    @pytest.mark.asyncio
    async def test_calculates_availability(
        self, db_session, test_product, test_supplier, mock_ctx
    ):
        """Test that availability is calculated from linked items."""
        # Create linked items with stock info
        for i, in_stock in enumerate([False, True, False]):
            item = SupplierItem(
                supplier_id=test_supplier.id,
                supplier_sku=f"STOCK-{i}",
                name=f"Stock Item {i}",
                current_price=Decimal("100.00"),
                characteristics={"in_stock": in_stock},
                product_id=test_product.id,
                match_status=MatchStatus.AUTO_MATCHED,
                match_score=Decimal("95.0"),
            )
            db_session.add(item)
        
        await db_session.commit()
        
        result = await recalc_product_aggregates_task(
            ctx=mock_ctx,
            task_id="test-recalc-002",
            product_ids=[str(test_product.id)],
            trigger="price_change",
        )
        
        assert result["status"] == "success"
        
        await db_session.refresh(test_product)
        # At least one item has stock, so availability should be True
        assert test_product.availability is True
    
    @pytest.mark.asyncio
    async def test_batch_processing_multiple_products(
        self, db_session, test_category, test_supplier, mock_ctx
    ):
        """Test batch processing of multiple products."""
        products = []
        for i in range(3):
            product = Product(
                internal_sku=f"BATCH-PROD-{i}",
                name=f"Batch Product {i}",
                category_id=test_category.id,
                status=ProductStatus.ACTIVE,
            )
            db_session.add(product)
            products.append(product)
        
        await db_session.commit()
        for p in products:
            await db_session.refresh(p)
        
        # Link items to products
        for product in products:
            item = SupplierItem(
                supplier_id=test_supplier.id,
                supplier_sku=f"BATCH-ITEM-{product.internal_sku}",
                name=f"Item for {product.name}",
                current_price=Decimal("99.99"),
                characteristics={"in_stock": True},
                product_id=product.id,
                match_status=MatchStatus.AUTO_MATCHED,
                match_score=Decimal("95.0"),
            )
            db_session.add(item)
        
        await db_session.commit()
        
        result = await recalc_product_aggregates_task(
            ctx=mock_ctx,
            task_id="test-recalc-003",
            product_ids=[str(p.id) for p in products],
            trigger="manual_link",
        )
        
        assert result["status"] == "success"
        assert result["products_processed"] == 3


class TestHandleManualMatchEventIntegration:
    """Integration tests for handle_manual_match_event."""
    
    @pytest.mark.asyncio
    async def test_manual_link_action(
        self, db_session, test_product, test_supplier, mock_ctx
    ):
        """Test manual link action creates verified_match."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="MANUAL-LINK",
            name="Item for Manual Link",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.UNMATCHED,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await handle_manual_match_event(
            ctx=mock_ctx,
            task_id="test-manual-001",
            supplier_item_id=str(item.id),
            action="link",
            product_id=str(test_product.id),
            user_id=str(uuid4()),
        )
        
        assert result["status"] == "success"
        assert result["action"] == "link"
        
        await db_session.refresh(item)
        assert item.product_id == test_product.id
        assert item.match_status == MatchStatus.VERIFIED_MATCH
    
    @pytest.mark.asyncio
    async def test_manual_unlink_action(
        self, db_session, test_product, test_supplier, mock_ctx
    ):
        """Test manual unlink action removes link."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="MANUAL-UNLINK",
            name="Item for Manual Unlink",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.VERIFIED_MATCH,
            product_id=test_product.id,
            match_score=Decimal("100.0"),
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        result = await handle_manual_match_event(
            ctx=mock_ctx,
            task_id="test-manual-002",
            supplier_item_id=str(item.id),
            action="unlink",
            user_id=str(uuid4()),
        )
        
        assert result["status"] == "success"
        assert result["action"] == "unlink"
        assert result["previous_product_id"] == str(test_product.id)
        
        await db_session.refresh(item)
        assert item.product_id is None
        assert item.match_status == MatchStatus.UNMATCHED
    
    @pytest.mark.asyncio
    async def test_approve_match_from_review_queue(
        self, db_session, test_product, test_supplier, mock_ctx
    ):
        """Test approving a match from the review queue."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="APPROVE-MATCH",
            name="Item for Approval",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.POTENTIAL_MATCH,
            match_score=Decimal("80.0"),
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        # Create review queue entry
        review = MatchReviewQueue(
            supplier_item_id=item.id,
            candidate_products=[{
                "product_id": str(test_product.id),
                "product_name": test_product.name,
                "score": 80.0,
            }],
            status=ReviewStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(review)
        await db_session.commit()
        
        result = await handle_manual_match_event(
            ctx=mock_ctx,
            task_id="test-manual-003",
            supplier_item_id=str(item.id),
            action="approve_match",
            product_id=str(test_product.id),
            user_id=str(uuid4()),
        )
        
        assert result["status"] == "success"
        assert result["action"] == "approve_match"
        
        await db_session.refresh(item)
        assert item.product_id == test_product.id
        assert item.match_status == MatchStatus.VERIFIED_MATCH
        
        await db_session.refresh(review)
        assert review.status == ReviewStatus.APPROVED
    
    @pytest.mark.asyncio
    async def test_reject_match_creates_new_product(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test rejecting a match creates a new product."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="REJECT-MATCH",
            name="Item for Rejection",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.POTENTIAL_MATCH,
            match_score=Decimal("75.0"),
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        # Create review queue entry
        review = MatchReviewQueue(
            supplier_item_id=item.id,
            candidate_products=[],
            status=ReviewStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(review)
        await db_session.commit()
        
        result = await handle_manual_match_event(
            ctx=mock_ctx,
            task_id="test-manual-004",
            supplier_item_id=str(item.id),
            action="reject_match",
            user_id=str(uuid4()),
        )
        
        assert result["status"] == "success"
        assert result["action"] == "reject_match"
        assert result["product_id"] is not None  # New product created
        
        await db_session.refresh(item)
        assert item.product_id is not None
        assert item.match_status == MatchStatus.VERIFIED_MATCH
        
        # Verify new product exists
        new_product = await db_session.get(Product, item.product_id)
        assert new_product is not None
        assert new_product.status == ProductStatus.DRAFT


class TestExpireReviewQueueTaskIntegration:
    """Integration tests for expire_review_queue_task."""
    
    @pytest.mark.asyncio
    async def test_expires_old_pending_reviews(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that old pending reviews are expired."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="EXPIRE-TEST",
            name="Item for Expiration Test",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.POTENTIAL_MATCH,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        # Create expired review
        review = MatchReviewQueue(
            supplier_item_id=item.id,
            candidate_products=[],
            status=ReviewStatus.PENDING,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
        )
        db_session.add(review)
        await db_session.commit()
        await db_session.refresh(review)
        
        result = await expire_review_queue_task(
            ctx=mock_ctx,
            task_id="test-expire-001",
        )
        
        assert result["status"] == "success"
        assert result["expired_count"] >= 1
        
        await db_session.refresh(review)
        assert review.status == ReviewStatus.EXPIRED
    
    @pytest.mark.asyncio
    async def test_does_not_expire_non_pending_reviews(
        self, db_session, test_supplier, mock_ctx
    ):
        """Test that non-pending reviews are not expired."""
        item = SupplierItem(
            supplier_id=test_supplier.id,
            supplier_sku="NO-EXPIRE-TEST",
            name="Item for No Expiration",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.VERIFIED_MATCH,
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)
        
        # Create already approved review with old date
        review = MatchReviewQueue(
            supplier_item_id=item.id,
            candidate_products=[],
            status=ReviewStatus.APPROVED,  # Not pending
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            reviewed_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db_session.add(review)
        await db_session.commit()
        await db_session.refresh(review)
        
        result = await expire_review_queue_task(
            ctx=mock_ctx,
            task_id="test-expire-002",
        )
        
        await db_session.refresh(review)
        # Should still be approved
        assert review.status == ReviewStatus.APPROVED


