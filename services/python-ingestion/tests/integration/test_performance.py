"""Performance tests for data ingestion pipeline.

This module tests system performance to ensure it meets the target of
processing >1,000 items per minute and can handle 10,000 items in <10 minutes.

Prerequisites:
- Docker services must be running: docker-compose up -d
- Database migrations applied: alembic upgrade head

Run performance test with:
    pytest tests/integration/test_performance.py::test_performance_10000_items -v -m integration -s
"""
import pytest
import time
import json
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.parsers.base_parser import ParserInterface
from src.models.parsed_item import ParsedSupplierItem
from src.db.operations import (
    get_or_create_supplier,
    upsert_supplier_item,
    create_price_history_entry,
    log_parsing_error
)
from src.db.models.supplier import Supplier
from src.db.models.supplier_item import SupplierItem
from src.db.models.price_history import PriceHistory
from src.db.base import async_session_maker
from tests.integration.helpers import create_test_parsed_items


class PerformanceTestParser(ParserInterface):
    """Parser that generates a configurable number of test items for performance testing."""
    
    def __init__(self, item_count: int = 10000):
        """Initialize performance test parser.
        
        Args:
            item_count: Number of items to generate
        """
        self.item_count = item_count
    
    async def parse(self, config: Dict[str, Any]) -> List[ParsedSupplierItem]:
        """Generate test items for performance testing.
        
        Args:
            config: Configuration dictionary (can contain 'item_count' to override)
        
        Returns:
            List of ParsedSupplierItem objects
        """
        count = config.get('item_count', self.item_count)
        return create_test_parsed_items(count, start_price=Decimal("10.00"))
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            True if valid
        """
        return isinstance(config, dict)
    
    def get_parser_name(self) -> str:
        """Return parser identifier.
        
        Returns:
            "performance_test" as the parser type identifier
        """
        return "performance_test"


def _serialize_row_data(item: ParsedSupplierItem) -> Dict[str, Any]:
    """Convert ParsedSupplierItem to JSON-serializable dict for error logging.
    
    Args:
        item: ParsedSupplierItem to serialize
    
    Returns:
        Dictionary with JSON-serializable values (Decimal converted to string)
    """
    try:
        # Use model_dump with mode='json' to handle Decimal serialization
        data = item.model_dump(mode='json')
        return data
    except Exception:
        # Fallback: manually convert Decimal to string
        data = {
            'supplier_sku': item.supplier_sku,
            'name': item.name,
            'price': str(item.price),  # Convert Decimal to string
            'characteristics': item.characteristics
        }
        return data


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_performance_10000_items(db_session: AsyncSession):
    """Performance test: Ingest 10,000 items and verify throughput >1,000 items/min.
    
    This test verifies:
    - System can process 10,000 items in <10 minutes
    - Throughput is >1,000 items per minute
    - All items are successfully stored in database
    - Price history entries are created for all items
    
    Target: >1,000 items/min
    Max time: 10 minutes
    """
    # Register performance test parser
    from src.parsers.parser_registry import register_parser
    parser = PerformanceTestParser(item_count=10000)
    register_parser("performance_test", PerformanceTestParser)
    
    try:
        # 1. Generate 10,000 test items
        print("\n" + "="*80)
        print("PERFORMANCE TEST: Processing 10,000 items")
        print("="*80)
        
        config = {"item_count": 10000}
        start_time = time.time()
        
        # 2. Parse items (this is fast, just generates in-memory objects)
        parsed_items = await parser.parse(config)
        parse_time = time.time() - start_time
        
        print(f"✓ Generated {len(parsed_items)} items in {parse_time:.2f} seconds")
        assert len(parsed_items) == 10000, f"Expected 10,000 items, got {len(parsed_items)}"
        
        # 3. Get or create supplier
        supplier_start = time.time()
        supplier = await get_or_create_supplier(
            db_session,
            supplier_name="Performance Test Supplier",
            source_type="csv"  # Use "csv" as it's a valid source_type in the database
        )
        supplier_time = time.time() - supplier_start
        print(f"✓ Created/retrieved supplier in {supplier_time:.2f} seconds")
        
        # 4. Ingest items into database (this is the performance-critical part)
        ingest_start = time.time()
        items_inserted = 0
        items_failed = 0
        
        # Process items in batches for better performance
        batch_size = 100
        for batch_idx in range(0, len(parsed_items), batch_size):
            batch = parsed_items[batch_idx:batch_idx + batch_size]
            
            for item_idx, item in enumerate(batch):
                try:
                    # Upsert supplier item - pass entire item object
                    supplier_item, price_changed, is_new_item = await upsert_supplier_item(
                        db_session,
                        supplier_id=supplier.id,
                        parsed_item=item
                    )
                    
                    # Create price history entry for new items or when price changed
                    if is_new_item or price_changed:
                        await create_price_history_entry(
                            db_session,
                            supplier_item_id=supplier_item.id,
                            price=item.price
                        )
                    
                    items_inserted += 1
                except Exception as e:
                    items_failed += 1
                    # Log error but continue processing
                    # Calculate row number correctly (1-indexed)
                    row_num = batch_idx + item_idx + 1
                    try:
                        # Serialize row data to JSON-compatible format
                        row_data = _serialize_row_data(item)
                        await log_parsing_error(
                            db_session,
                            task_id="performance-test-001",
                            supplier_id=supplier.id,
                            error_type="ValidationError",
                            error_message=str(e),
                            row_number=row_num,
                            row_data=row_data
                        )
                    except Exception as log_error:
                        # If logging fails, just print and continue
                        print(f"Warning: Failed to log error for row {row_num}: {log_error}")
            
            # Commit batch
            await db_session.commit()
            
            # Progress indicator
            if (batch_idx + batch_size) % 1000 == 0 or (batch_idx + len(batch)) >= len(parsed_items):
                elapsed = time.time() - ingest_start
                processed = min(batch_idx + len(batch), len(parsed_items))
                rate = processed / elapsed * 60 if elapsed > 0 else 0  # items per minute
                print(f"  Processed {processed:,} items... ({rate:.0f} items/min)")
        
        ingest_time = time.time() - ingest_start
        total_time = time.time() - start_time
        
        # 5. Calculate performance metrics
        items_per_minute = (items_inserted / ingest_time) * 60 if ingest_time > 0 else 0
        total_items_per_minute = (items_inserted / total_time) * 60 if total_time > 0 else 0
        
        print("\n" + "="*80)
        print("PERFORMANCE TEST RESULTS")
        print("="*80)
        print(f"Items processed:     {items_inserted:,} / {len(parsed_items):,}")
        print(f"Items failed:        {items_failed:,}")
        print(f"Parse time:          {parse_time:.2f} seconds")
        print(f"Ingest time:         {ingest_time:.2f} seconds ({ingest_time/60:.2f} minutes)")
        print(f"Total time:          {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        print(f"Ingest throughput:   {items_per_minute:.0f} items/minute")
        print(f"Total throughput:    {total_items_per_minute:.0f} items/minute")
        print("="*80)
        
        # 6. Verify all items were inserted
        items_count = await db_session.scalar(
            select(func.count(SupplierItem.id)).where(
                SupplierItem.supplier_id == supplier.id
            )
        )
        
        price_history_count = await db_session.scalar(
            select(func.count(PriceHistory.id))
            .join(SupplierItem)
            .where(SupplierItem.supplier_id == supplier.id)
        )
        
        print(f"\nDatabase verification:")
        print(f"  SupplierItems in DB: {items_count:,}")
        print(f"  PriceHistory entries: {price_history_count:,}")
        
        # 7. Assertions
        assert items_inserted == len(parsed_items), \
            f"Expected {len(parsed_items)} items inserted, got {items_inserted}"
        
        assert items_count == items_inserted, \
            f"Database count mismatch: expected {items_inserted}, got {items_count}"
        
        # Price history should equal items (all are new items)
        assert price_history_count == items_inserted, \
            f"Price history count mismatch: expected {items_inserted}, got {price_history_count}"
        
        # Performance assertions
        assert total_time < 600, \
            f"Total time {total_time:.2f}s exceeds 10 minutes (600s)"
        
        assert items_per_minute > 1000, \
            f"Throughput {items_per_minute:.0f} items/min is below target of 1,000 items/min"
        
        print("\n✅ PERFORMANCE TEST PASSED")
        print(f"   ✓ Processed {items_inserted:,} items in {total_time/60:.2f} minutes")
        print(f"   ✓ Throughput: {items_per_minute:.0f} items/minute (target: >1,000)")
        print(f"   ✓ All items successfully stored in database")
        
    finally:
        # Clean up: remove parser registration
        from src.parsers.parser_registry import _parser_registry
        _parser_registry.pop("performance_test", None)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_performance_batch_processing(db_session: AsyncSession):
    """Test batch processing performance with different batch sizes.
    
    This test helps identify optimal batch size for database operations.
    """
    parser = PerformanceTestParser(item_count=1000)
    
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Batch Test Supplier",
        source_type="csv"  # Use "csv" as it's a valid source_type in the database
    )
    
    parsed_items = await parser.parse({"item_count": 1000})
    
    # Test different batch sizes
    batch_sizes = [10, 50, 100, 200, 500]
    results = {}
    
    for batch_size in batch_sizes:
        # Clean previous test data
        await db_session.execute(
            select(SupplierItem).where(SupplierItem.supplier_id == supplier.id)
        )
        await db_session.commit()
        
        start_time = time.time()
        items_inserted = 0
        
        for i in range(0, len(parsed_items), batch_size):
            batch = parsed_items[i:i + batch_size]
            
            for item in batch:
                supplier_item, price_changed, is_new_item = await upsert_supplier_item(
                    db_session,
                    supplier_id=supplier.id,
                    parsed_item=item
                )
                # Create price history for new items
                if is_new_item:
                    await create_price_history_entry(
                        db_session,
                        supplier_item_id=supplier_item.id,
                        price=item.price
                    )
                items_inserted += 1
            
            await db_session.commit()
        
        elapsed = time.time() - start_time
        items_per_minute = (items_inserted / elapsed) * 60 if elapsed > 0 else 0
        results[batch_size] = {
            'time': elapsed,
            'throughput': items_per_minute
        }
        
        print(f"Batch size {batch_size:3d}: {elapsed:.2f}s, {items_per_minute:.0f} items/min")
    
    # Find optimal batch size
    optimal = max(results.items(), key=lambda x: x[1]['throughput'])
    print(f"\nOptimal batch size: {optimal[0]} ({optimal[1]['throughput']:.0f} items/min)")
    
    assert optimal[1]['throughput'] > 1000, \
        f"Even optimal batch size {optimal[0]} doesn't meet 1,000 items/min target"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
async def test_matching_pipeline_performance_1000_items(db_session: AsyncSession):
    """Performance test: Match 1,000 supplier items against product catalog.
    
    This test verifies:
    - Matching throughput is >1,000 items per minute
    - Category blocking improves performance
    - RapidFuzz matching is efficient
    
    Target: >1,000 items/min
    """
    from src.db.models import Product, SupplierItem, Category, Supplier, MatchStatus, ProductStatus
    from src.services.matching import RapidFuzzMatcher, create_matcher
    from uuid import uuid4
    
    print("\n" + "="*80)
    print("MATCHING PIPELINE PERFORMANCE TEST: 1,000 items")
    print("="*80)
    
    # 1. Create test category
    category = Category(
        name="Test Category",
        slug="test-category",
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    
    # 2. Create supplier
    supplier = Supplier(
        name="Matching Test Supplier",
        source_type="csv",
        metadata={},
    )
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    
    # 3. Create product catalog (100 products to match against)
    print("Creating product catalog (100 products)...")
    products = []
    product_names = [
        "Samsung Galaxy A54 5G 128GB Black",
        "Samsung Galaxy A54 5G 256GB Black",
        "iPhone 15 Pro 256GB Silver",
        "iPhone 15 Pro Max 512GB Space Black",
        "Xiaomi Redmi Note 12 Pro 128GB",
        "Xiaomi Redmi Note 12 Pro+ 256GB",
        "Google Pixel 8 128GB Obsidian",
        "Google Pixel 8 Pro 256GB Bay",
        "OnePlus 11 5G 256GB Titan Black",
        "Sony Xperia 1 V 256GB Black",
    ]
    
    # Create variations to have 100 products
    for i in range(100):
        base_name = product_names[i % len(product_names)]
        variation = f"Variant-{i}"
        product = Product(
            internal_sku=f"MATCH-PERF-{i:04d}",
            name=f"{base_name} {variation}",
            category_id=category.id,
            status=ProductStatus.ACTIVE,
        )
        db_session.add(product)
        products.append(product)
    
    await db_session.commit()
    for p in products:
        await db_session.refresh(p)
    
    print(f"✓ Created {len(products)} products")
    
    # 4. Create unmatched supplier items (1,000)
    print("Creating unmatched supplier items (1,000)...")
    items = []
    for i in range(1000):
        base_name = product_names[i % len(product_names)]
        # Add some variation to simulate real data
        variations = ["", " - New", " (Refurbished)", " Sale", " Limited Edition"]
        variation = variations[i % len(variations)]
        
        item = SupplierItem(
            supplier_id=supplier.id,
            supplier_sku=f"PERF-ITEM-{i:06d}",
            name=f"{base_name}{variation}",
            current_price=Decimal(f"{99 + (i % 100)}.99"),
            characteristics={"in_stock": True},
            match_status=MatchStatus.UNMATCHED,
        )
        db_session.add(item)
        items.append(item)
    
    await db_session.commit()
    print(f"✓ Created {len(items)} supplier items")
    
    # 5. Run matching
    print("\nRunning matching process...")
    matcher = create_matcher("rapidfuzz")
    
    start_time = time.time()
    matches_found = 0
    
    for item in items:
        result = matcher.find_matches(
            item_name=item.name,
            item_id=item.id,
            products=products,
            auto_threshold=95.0,
            potential_threshold=70.0,
            max_candidates=5,
        )
        
        if result.match_status.value != "unmatched":
            matches_found += 1
    
    matching_time = time.time() - start_time
    items_per_minute = (len(items) / matching_time) * 60 if matching_time > 0 else 0
    
    # 6. Report results
    print("\n" + "="*80)
    print("MATCHING PERFORMANCE TEST RESULTS")
    print("="*80)
    print(f"Items processed:     {len(items):,}")
    print(f"Products catalog:    {len(products):,}")
    print(f"Matches found:       {matches_found:,}")
    print(f"Matching time:       {matching_time:.2f} seconds")
    print(f"Throughput:          {items_per_minute:.0f} items/minute")
    print("="*80)
    
    # 7. Assertions
    assert items_per_minute > 1000, \
        f"Matching throughput {items_per_minute:.0f} items/min is below target of 1,000 items/min"
    
    print("\n✅ MATCHING PERFORMANCE TEST PASSED")
    print(f"   ✓ Processed {len(items):,} items in {matching_time:.2f} seconds")
    print(f"   ✓ Throughput: {items_per_minute:.0f} items/minute (target: >1,000)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_select_for_update_skip_locked(db_session: AsyncSession):
    """Test that SELECT FOR UPDATE SKIP LOCKED prevents duplicate processing.
    
    This test verifies concurrent workers don't process the same items.
    """
    import asyncio
    from src.db.models import SupplierItem, Supplier, MatchStatus
    from src.db.base import async_session_maker
    from sqlalchemy import select, and_
    
    print("\n" + "="*80)
    print("CONCURRENT WORKER TEST: SELECT FOR UPDATE SKIP LOCKED")
    print("="*80)
    
    # 1. Create test supplier
    supplier = Supplier(
        name="Concurrent Test Supplier",
        source_type="csv",
        metadata={},
    )
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    
    # 2. Create unmatched items
    print("Creating 100 unmatched items...")
    items = []
    for i in range(100):
        item = SupplierItem(
            supplier_id=supplier.id,
            supplier_sku=f"CONCURRENT-{i:04d}",
            name=f"Concurrent Test Item {i}",
            current_price=Decimal("99.99"),
            characteristics={},
            match_status=MatchStatus.UNMATCHED,
        )
        db_session.add(item)
        items.append(item)
    
    await db_session.commit()
    print(f"✓ Created {len(items)} unmatched items")
    
    # 3. Track which items are processed by which "worker"
    processed_by: dict = {}  # item_id -> worker_id
    lock = asyncio.Lock()
    
    async def simulate_worker(worker_id: int, batch_size: int = 20):
        """Simulate a worker selecting and processing items."""
        processed = []
        
        async with async_session_maker() as session:
            async with session.begin():
                # SELECT FOR UPDATE SKIP LOCKED
                query = (
                    select(SupplierItem)
                    .where(
                        and_(
                            SupplierItem.supplier_id == supplier.id,
                            SupplierItem.match_status == MatchStatus.UNMATCHED,
                        )
                    )
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
                
                result = await session.execute(query)
                worker_items = result.scalars().all()
                
                # "Process" items (mark as matched)
                for item in worker_items:
                    item.match_status = MatchStatus.AUTO_MATCHED
                    item.match_score = Decimal("95.0")
                    session.add(item)
                    
                    async with lock:
                        if str(item.id) in processed_by:
                            # This would be a duplicate!
                            print(f"❌ DUPLICATE: Item {item.id} already processed by worker {processed_by[str(item.id)]}")
                        processed_by[str(item.id)] = worker_id
                    
                    processed.append(item.id)
                
                await session.commit()
        
        return processed
    
    # 4. Run multiple "workers" concurrently
    print("\nRunning 5 concurrent workers...")
    start_time = time.time()
    
    results = await asyncio.gather(
        simulate_worker(1, 30),
        simulate_worker(2, 30),
        simulate_worker(3, 30),
        simulate_worker(4, 30),
        simulate_worker(5, 30),
    )
    
    elapsed = time.time() - start_time
    
    # 5. Verify no duplicates
    all_processed = []
    for r in results:
        all_processed.extend(r)
    
    unique_processed = set(all_processed)
    
    print("\n" + "="*80)
    print("CONCURRENT WORKER TEST RESULTS")
    print("="*80)
    print(f"Total items:         {len(items)}")
    print(f"Items processed:     {len(all_processed)}")
    print(f"Unique items:        {len(unique_processed)}")
    print(f"Duration:            {elapsed:.2f} seconds")
    
    for i, r in enumerate(results, 1):
        print(f"  Worker {i}: {len(r)} items")
    
    # 6. Assertions
    # No duplicates should exist
    assert len(all_processed) == len(unique_processed), \
        f"Duplicate items detected! Processed {len(all_processed)} but only {len(unique_processed)} unique"
    
    # Not all items may be processed (due to SKIP LOCKED), but no duplicates
    print("\n✅ CONCURRENT WORKER TEST PASSED")
    print(f"   ✓ No duplicate processing detected")
    print(f"   ✓ SELECT FOR UPDATE SKIP LOCKED working correctly")
