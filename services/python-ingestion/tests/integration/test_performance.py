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
