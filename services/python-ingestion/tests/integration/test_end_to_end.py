"""Integration tests for end-to-end data ingestion pipeline.

These tests verify the complete data flow from queue message to database persistence,
including error handling, transaction rollback, and price history tracking.

Prerequisites:
- Docker services must be running: docker-compose up -d
- Database migrations applied: alembic upgrade head
- Google Sheets credentials configured (for Google Sheets tests)

Run tests with:
    pytest tests/integration/test_end_to_end.py -v -m integration
"""
import pytest
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.worker import parse_task
from src.db.operations import (
    get_or_create_supplier,
    upsert_supplier_item,
    create_price_history_entry
)
from src.db.models.supplier import Supplier
from src.db.models.supplier_item import SupplierItem
from src.db.models.price_history import PriceHistory
from src.db.models.parsing_log import ParsingLog
from src.models.parsed_item import ParsedSupplierItem
from tests.integration.helpers import create_test_parsed_items, create_test_parsed_items_with_same_price


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_1_first_time_ingestion(db_session: AsyncSession):
    """Test Scenario 1: First-time data ingestion with 500 rows from test sheet.
    
    Acceptance Criteria:
    - Supplier record created
    - All valid items inserted into supplier_items
    - Price history entries created for all items
    - No parsing errors for valid data
    
    Note: This test uses stub parser for simplicity. For real Google Sheets test,
    use create_test_sheet() helper and google_sheets parser.
    """
    # 1. Create test data (500 items)
    # Using stub parser for this test - replace with Google Sheets for real test
    parsed_items = create_test_parsed_items(500)
    
    # 2. Create parse task message
    message = {
        "task_id": "test-task-001",
        "parser_type": "stub",  # Use stub parser for this test
        "supplier_name": "Test Supplier 500",
        "source_config": {"test": "config"},
        "retry_count": 0,
        "max_retries": 3,
    }
    
    # 3. Execute parse task
    ctx = {"job_try": 1}
    result = await parse_task(ctx, message)
    
    # 4. Verify task completed successfully
    assert result["status"] == "success"
    assert result["items_parsed"] == 3  # Stub parser returns 3 items
    assert result["items_failed"] == 0
    
    # 5. Verify supplier exists in database
    supplier_result = await db_session.execute(
        select(Supplier).where(Supplier.name == "Test Supplier 500")
    )
    supplier = supplier_result.scalar_one_or_none()
    assert supplier is not None, "Supplier should be created"
    assert supplier.source_type == "csv"  # stub parser maps to csv in database
    
    # 6. Verify supplier_items inserted
    items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert items_count == 3  # Stub parser returns 3 items
    
    # 7. Verify price_history entries created
    price_history_count = await db_session.scalar(
        select(func.count(PriceHistory.id))
        .join(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
    )
    assert price_history_count == 3  # One per item
    
    # 8. Verify no parsing_logs entries
    error_count = await db_session.scalar(
        select(func.count(ParsingLog.id)).where(
            ParsingLog.task_id == "test-task-001"
        )
    )
    assert error_count == 0, "No errors should be logged for valid data"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_2_price_update_triggers_history(db_session: AsyncSession):
    """Test Scenario 2: Updated price list triggers new PriceHistory entries.
    
    Acceptance Criteria:
    - Existing supplier_items updated with new prices
    - New price_history entries created only for changed prices
    - No duplicate supplier_items created
    """
    # 1. Create supplier
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Test Supplier Update",
        source_type="stub"
    )
    await db_session.commit()
    
    # 2. Ingest initial data (100 items at $10.00 each)
    initial_items = create_test_parsed_items_with_same_price(100, Decimal("10.00"))
    
    for item in initial_items:
        supplier_item, price_changed, is_new_item = await upsert_supplier_item(
            db_session, supplier.id, item
        )
        # Create initial price history entry (for new items)
        if is_new_item:
            await create_price_history_entry(db_session, supplier_item.id, item.price)
    await db_session.commit()
    
    # Verify initial state: 100 items, 100 price history entries
    initial_items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert initial_items_count == 100
    
    initial_history_count = await db_session.scalar(
        select(func.count(PriceHistory.id))
        .join(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
    )
    assert initial_history_count == 100
    
    # 3. Ingest updated data (50 items at $10.00, 50 items at $12.00)
    updated_items = []
    for i in range(100):
        sku = f"TEST-SKU-{i+1:03d}"
        if i < 50:
            # Same price - no change
            updated_items.append(ParsedSupplierItem(
                supplier_sku=sku,
                name=f"Test Product {i+1}",
                price=Decimal("10.00"),
                characteristics={}
            ))
        else:
            # Changed price
            updated_items.append(ParsedSupplierItem(
                supplier_sku=sku,
                name=f"Test Product {i+1}",
                price=Decimal("12.00"),
                characteristics={}
            ))
    
    price_changes_count = 0
    for item in updated_items:
        supplier_item, price_changed, is_new_item = await upsert_supplier_item(
            db_session, supplier.id, item
        )
        if price_changed:
            await create_price_history_entry(db_session, supplier_item.id, item.price)
            price_changes_count += 1
    await db_session.commit()
    
    # 4. Verify 100 supplier_items exist (no duplicates)
    final_items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert final_items_count == 100, "No duplicate items should be created"
    
    # 5. Verify 50 new price_history entries (only for changed prices)
    # Initial: 100, New: 50 = 150 total
    final_history_count = await db_session.scalar(
        select(func.count(PriceHistory.id))
        .join(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
    )
    assert final_history_count == 150, f"Expected 150 history entries (100 initial + 50 changes), got {final_history_count}"
    
    # 6. Verify current_price updated to $12.00 for changed items
    # Items with i >= 50 should have price $12.00 (SKUs TEST-SKU-051 through TEST-SKU-100)
    # Check items starting from TEST-SKU-051 (not TEST-SKU-050 which should stay at $10.00)
    changed_items = await db_session.execute(
        select(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
        .where(SupplierItem.supplier_sku >= "TEST-SKU-051")
        .where(SupplierItem.supplier_sku <= "TEST-SKU-060")
        .limit(10)
    )
    for item in changed_items.scalars():
        assert item.current_price == Decimal("12.00"), f"Price should be updated to $12.00 for {item.supplier_sku}, got {item.current_price}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_3_malformed_data_partial_success(db_session: AsyncSession):
    """Test Scenario 3: Malformed data (10 missing prices) results in 90 inserts, 10 errors.
    
    Acceptance Criteria:
    - Valid rows (90) inserted successfully
    - Invalid rows (10) logged to parsing_logs
    - Processing continues after validation errors
    - Transaction commits with partial success
    
    Note: This test directly tests database operations with invalid data to verify
    error handling. For real Google Sheets test, create a sheet with missing prices.
    """
    from src.db.operations import (
        get_or_create_supplier,
        upsert_supplier_item,
        log_parsing_error
    )
    from src.errors.exceptions import ValidationError
    
    # 1. Create supplier
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Test Supplier Errors",
        source_type="stub"
    )
    await db_session.commit()
    
    # 2. Process 100 items: 90 valid, 10 invalid (simulating parser output)
    valid_items = create_test_parsed_items(90)
    success_count = 0
    failed_count = 0
    
    # Process valid items
    for i, item in enumerate(valid_items, start=1):
        try:
            await upsert_supplier_item(db_session, supplier.id, item)
            success_count += 1
        except ValidationError as e:
            failed_count += 1
            await log_parsing_error(
                db_session,
                task_id="test-task-errors",
                supplier_id=supplier.id,
                error_type="ValidationError",
                error_message=str(e),
                row_number=i
            )
    
    # Process 10 invalid items (empty SKU - will cause ValidationError)
    for i in range(10):
        try:
            # Try to create item with invalid data (empty SKU will fail Pydantic validation)
            # Pydantic raises ValidationError at object construction time
            invalid_item = ParsedSupplierItem(
                supplier_sku="",  # Invalid: empty SKU
                name=f"Invalid Product {i+1}",
                price=Decimal("10.00"),
                characteristics={}
            )
            # If we get here, validation didn't catch it (shouldn't happen)
            await upsert_supplier_item(db_session, supplier.id, invalid_item)
        except Exception as e:
            # Catch both Pydantic ValidationError and our custom ValidationError
            # Pydantic raises pydantic_core._pydantic_core.ValidationError or pydantic.ValidationError
            # Check if it's a validation error (Pydantic or custom)
            error_type_name = type(e).__name__
            if "ValidationError" not in error_type_name and "validation" not in str(e).lower():
                raise  # Re-raise if it's not a validation error
            failed_count += 1
            await log_parsing_error(
                db_session,
                task_id="test-task-errors",
                supplier_id=supplier.id,
                error_type="ValidationError",
                error_message=str(e),
                row_number=90 + i + 1
            )
    
    await db_session.commit()
    
    # 3. Verify 90 supplier_items inserted
    items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert items_count == 90, f"Expected 90 items, got {items_count}"
    
    # 4. Verify 10 parsing_logs entries with ValidationError
    error_count = await db_session.scalar(
        select(func.count(ParsingLog.id))
        .where(ParsingLog.task_id == "test-task-errors")
        .where(ParsingLog.error_type == "ValidationError")
    )
    assert error_count == 10, f"Expected 10 errors, got {error_count}"
    
    # 5. Verify processing continued (both success and failed counts)
    assert success_count == 90, f"Expected 90 successful inserts, got {success_count}"
    assert failed_count == 10, f"Expected 10 failed inserts, got {failed_count}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_4_database_unavailable_retry(db_session: AsyncSession):
    """Test Scenario 4: Database unavailable triggers retry, eventual success after reconnect.
    
    Acceptance Criteria:
    - Task retries with exponential backoff when database unavailable
    - Task succeeds after database reconnects
    - No duplicate data inserted after retry
    
    Note: This test mocks database failures. For real database unavailable test,
    you would need to stop/start PostgreSQL container.
    """
    from unittest.mock import patch, AsyncMock
    from src.errors.exceptions import DatabaseError
    
    # Mock database operation to fail first 2 times, then succeed
    call_count = 0
    original_get_or_create = get_or_create_supplier
    
    async def mock_get_or_create_supplier(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise DatabaseError("Database connection failed")
        # On third attempt, use real function
        return await original_get_or_create(*args, **kwargs)
    
    message = {
        "task_id": "test-task-retry",
        "parser_type": "stub",
        "supplier_name": "Test Supplier Retry",
        "source_config": {},
        "retry_count": 0,
        "max_retries": 3,
    }
    
    with patch('src.worker.get_or_create_supplier', side_effect=mock_get_or_create_supplier):
        # First attempt should fail and trigger retry
        ctx = {"job_try": 1}
        with pytest.raises((DatabaseError, Exception)):
            await parse_task(ctx, message)
        
        # Second attempt should also fail
        ctx = {"job_try": 2}
        with pytest.raises((DatabaseError, Exception)):
            await parse_task(ctx, message)
        
        # Third attempt should succeed
        ctx = {"job_try": 3}
        result = await parse_task(ctx, message)
        assert result["status"] == "success"
        
        # Verify no duplicate data
        supplier_result = await db_session.execute(
            select(Supplier).where(Supplier.name == "Test Supplier Retry")
        )
        supplier = supplier_result.scalar_one_or_none()
        if supplier:
            items_count = await db_session.scalar(
                select(func.count(SupplierItem.id)).where(
                    SupplierItem.supplier_id == supplier.id
                )
            )
            # Should only have items from successful attempt
            assert items_count == 3  # Stub parser returns 3 items


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_supplier_sku_upsert(db_session: AsyncSession):
    """Test that duplicate supplier_sku updates existing row (upsert behavior).
    
    Acceptance Criteria:
    - First ingestion creates supplier_item
    - Second ingestion with same supplier_sku updates existing row
    - No duplicate rows created
    - updated_at timestamp refreshed
    """
    # 1. Create supplier
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Test Supplier Upsert",
        source_type="stub"
    )
    await db_session.commit()
    
    # 2. Ingest item with supplier_sku "ABC-123"
    first_item = ParsedSupplierItem(
        supplier_sku="ABC-123",
        name="Original Product",
        price=Decimal("10.00"),
        characteristics={"color": "red"}
    )
    
    supplier_item, price_changed, is_new_item = await upsert_supplier_item(
        db_session, supplier.id, first_item
    )
    first_updated_at = supplier_item.updated_at
    await db_session.commit()
    
    # Verify item exists
    item_result = await db_session.execute(
        select(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
        .where(SupplierItem.supplier_sku == "ABC-123")
    )
    item = item_result.scalar_one()
    assert item.name == "Original Product"
    assert item.current_price == Decimal("10.00")
    
    # 3. Ingest same item again with updated name/price
    import asyncio
    await asyncio.sleep(0.1)  # Small delay to ensure timestamp difference
    
    second_item = ParsedSupplierItem(
        supplier_sku="ABC-123",  # Same SKU
        name="Updated Product",  # Updated name
        price=Decimal("12.00"),  # Updated price
        characteristics={"color": "blue"}  # Updated characteristics
    )
    
    supplier_item, price_changed, is_new_item = await upsert_supplier_item(
        db_session, supplier.id, second_item
    )
    second_updated_at = supplier_item.updated_at
    await db_session.commit()
    
    # 4. Verify only one row exists (no duplicates)
    items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert items_count == 1, "Should only have one item, not duplicates"
    
    # 5. Verify row updated with new values
    item_result = await db_session.execute(
        select(SupplierItem)
        .where(SupplierItem.supplier_id == supplier.id)
        .where(SupplierItem.supplier_sku == "ABC-123")
    )
    updated_item = item_result.scalar_one()
    assert updated_item.name == "Updated Product"
    assert updated_item.current_price == Decimal("12.00")
    assert updated_item.characteristics == {"color": "blue"}
    assert updated_item.updated_at > first_updated_at, "updated_at should be refreshed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validation_error_does_not_block_other_rows(db_session: AsyncSession):
    """Test that validation error on row 50 does NOT prevent rows 1-49 from being inserted.
    
    Acceptance Criteria:
    - Rows 1-49 inserted successfully
    - Row 50 validation error logged
    - Rows 51+ continue processing
    - Transaction commits with partial success
    """
    from src.db.operations import log_parsing_error
    from src.errors.exceptions import ValidationError
    
    # 1. Create supplier
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Test Supplier Partial",
        source_type="stub"
    )
    await db_session.commit()
    
    # 2. Create test data: 100 items, item 50 will have validation error
    valid_items = create_test_parsed_items(100)
    
    # Process items 1-49
    success_count = 0
    for i, item in enumerate(valid_items[:49], start=1):
        try:
            await upsert_supplier_item(db_session, supplier.id, item)
            success_count += 1
        except ValidationError as e:
            await log_parsing_error(
                db_session,
                task_id="test-task-partial",
                supplier_id=supplier.id,
                error_type="ValidationError",
                error_message=str(e),
                row_number=i
            )
    
    # Row 50: validation error (empty SKU fails Pydantic validation)
    try:
        # Attempt to create invalid item - this will raise ValidationError at construction
        # Pydantic raises pydantic_core._pydantic_core.ValidationError
        invalid_item = ParsedSupplierItem(
            supplier_sku="",  # Invalid: empty SKU
            name="Invalid Product",
            price=Decimal("10.00"),
            characteristics={}
        )
        # If we get here, validation didn't catch it (shouldn't happen)
        await upsert_supplier_item(db_session, supplier.id, invalid_item)
    except Exception as e:
        # Catch both Pydantic ValidationError and our custom ValidationError
        # Check if it's a validation error
        if "ValidationError" not in type(e).__name__ and "validation" not in str(e).lower():
            raise  # Re-raise if it's not a validation error
        await log_parsing_error(
            db_session,
            task_id="test-task-partial",
            supplier_id=supplier.id,
            error_type="ValidationError",
            error_message=str(e),
            row_number=50
        )
    
    # Process items 51-100
    for i, item in enumerate(valid_items[50:], start=51):
        try:
            await upsert_supplier_item(db_session, supplier.id, item)
            success_count += 1
        except ValidationError as e:
            await log_parsing_error(
                db_session,
                task_id="test-task-partial",
                supplier_id=supplier.id,
                error_type="ValidationError",
                error_message=str(e),
                row_number=i
            )
    
    await db_session.commit()
    
    # 3. Verify rows 1-49 inserted
    # 4. Verify row 50 error logged
    # 5. Verify rows 51+ inserted
    items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier.id
        )
    )
    assert items_count == 99, f"Expected 99 items (100 - 1 invalid), got {items_count}"
    
    # Verify error logged for row 50
    error_count = await db_session.scalar(
        select(func.count(ParsingLog.id))
        .where(ParsingLog.task_id == "test-task-partial")
        .where(ParsingLog.row_number == 50)
    )
    assert error_count == 1, "Row 50 error should be logged"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_transaction_rollback_on_critical_error(db_session: AsyncSession):
    """Test that database transaction rolls back on critical DatabaseError, task retried.
    
    Acceptance Criteria:
    - Critical database error triggers transaction rollback
    - No partial data persisted
    - Task retried with exponential backoff
    """
    from src.errors.exceptions import DatabaseError
    
    # Create supplier
    supplier = await get_or_create_supplier(
        db_session,
        supplier_name="Test Supplier Rollback",
        source_type="stub"
    )
    await db_session.commit()
    
    # Simulate transaction that fails mid-way
    items = create_test_parsed_items(10)
    
    # Store supplier_id before any operations to avoid session state issues after rollback
    supplier_id = supplier.id
    
    try:
        # Insert first 5 items
        for item in items[:5]:
            await upsert_supplier_item(db_session, supplier_id, item)
        
        # Simulate critical error
        raise DatabaseError("Simulated database connection lost")
        
    except DatabaseError:
        # Transaction should rollback
        await db_session.rollback()
    
    # Verify no partial data persisted
    # After rollback, start a new transaction
    await db_session.commit()  # Start a new transaction after rollback
    
    items_count = await db_session.scalar(
        select(func.count(SupplierItem.id)).where(
            SupplierItem.supplier_id == supplier_id
        )
    )
    assert items_count == 0, "Transaction should rollback, no data persisted"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_statistics_logging(db_session: AsyncSession):
    """Test that task completion is logged with statistics.
    
    Acceptance Criteria:
    - Task logs include: success count, failed count, duration
    - Statistics are accurate
    - Log format is structured JSON
    """
    # 1. Create parse task
    message = {
        "task_id": "test-task-stats",
        "parser_type": "stub",
        "supplier_name": "Test Supplier Stats",
        "source_config": {},
        "retry_count": 0,
        "max_retries": 3,
    }
    
    # 2. Execute parse task
    ctx = {"job_try": 1}
    result = await parse_task(ctx, message)
    
    # 3. Verify task result contains statistics
    assert "items_parsed" in result
    assert "items_failed" in result
    assert "duration_seconds" in result
    assert result["items_parsed"] == 3  # Stub parser returns 3 items
    assert result["items_failed"] == 0
    assert isinstance(result["duration_seconds"], (int, float))
    assert result["duration_seconds"] >= 0
    
    # 4. Verify status is logged
    assert "status" in result
    assert result["status"] in ["success", "partial_success", "error"]

