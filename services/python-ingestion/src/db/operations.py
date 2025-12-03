"""Database operations for data ingestion pipeline."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid
import structlog

from src.db.base import async_session_maker
from src.db.models.supplier import Supplier
from src.db.models.supplier_item import SupplierItem
from src.db.models.price_history import PriceHistory
from src.db.models.parsing_log import ParsingLog
from src.models.parsed_item import ParsedSupplierItem
from src.errors.exceptions import DatabaseError, ValidationError

logger = structlog.get_logger(__name__)


async def get_or_create_supplier(
    session: AsyncSession,
    supplier_name: str,
    source_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Supplier:
    """Get existing supplier or create new one.
    
    Args:
        session: Async database session
        supplier_name: Name of the supplier
        source_type: Type of data source (google_sheets, csv, excel, or stub for testing)
        metadata: Optional metadata dictionary
    
    Returns:
        Supplier instance (existing or newly created)
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        # Map parser types to valid database source_type values
        # "stub" is used in tests but not allowed in DB constraint
        source_type_map = {
            "stub": "csv",  # Map stub parser to csv for testing
            "google_sheets": "google_sheets",
            "csv": "csv",
            "excel": "excel",
        }
        db_source_type = source_type_map.get(source_type, source_type)
        
        # Try to find existing supplier by name and source_type
        result = await session.execute(
            select(Supplier)
            .where(Supplier.name == supplier_name)
            .where(Supplier.source_type == db_source_type)
        )
        supplier = result.scalar_one_or_none()
        
        if supplier:
            logger.debug(
                "supplier_found",
                supplier_id=str(supplier.id),
                supplier_name=supplier_name,
                source_type=db_source_type
            )
            return supplier
        
        # Create new supplier
        supplier = Supplier(
            name=supplier_name,
            source_type=db_source_type,
            metadata=metadata or {}
        )
        session.add(supplier)
        await session.flush()  # Flush to get the ID
        
        logger.info(
            "supplier_created",
            supplier_id=str(supplier.id),
            supplier_name=supplier_name,
            source_type=db_source_type
        )
        return supplier
    
    except Exception as e:
        logger.error(
            "get_or_create_supplier_failed",
            supplier_name=supplier_name,
            source_type=source_type,
            error=str(e),
            error_type=type(e).__name__
        )
        raise DatabaseError(f"Failed to get or create supplier: {e}") from e


async def upsert_supplier_item(
    session: AsyncSession,
    supplier_id: uuid.UUID,
    parsed_item: ParsedSupplierItem,
    product_id: Optional[uuid.UUID] = None
) -> tuple[SupplierItem, bool, bool]:
    """Upsert supplier item with conflict resolution.
    
    Uses PostgreSQL INSERT ... ON CONFLICT to handle duplicates.
    Detects price changes and returns flags indicating if price changed and if item is new.
    
    Args:
        session: Async database session
        supplier_id: UUID of the supplier
        parsed_item: Validated parsed item from parser
        product_id: Optional UUID of linked product
    
    Returns:
        Tuple of (SupplierItem instance, price_changed: bool, is_new_item: bool)
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        # Check if item exists and get current price
        existing_result = await session.execute(
            select(SupplierItem)
            .where(SupplierItem.supplier_id == supplier_id)
            .where(SupplierItem.supplier_sku == parsed_item.supplier_sku)
        )
        existing_item = existing_result.scalar_one_or_none()
        
        is_new_item = existing_item is None
        price_changed = False
        old_price: Optional[Decimal] = None
        
        if existing_item:
            old_price = existing_item.current_price
            # Check if price changed (compare with 2 decimal precision)
            if old_price != parsed_item.price:
                price_changed = True
                logger.debug(
                    "price_change_detected",
                    supplier_item_id=str(existing_item.id),
                    supplier_sku=parsed_item.supplier_sku,
                    old_price=str(old_price),
                    new_price=str(parsed_item.price)
                )
        
        # Use PostgreSQL INSERT ... ON CONFLICT for upsert
        stmt = insert(SupplierItem).values(
            supplier_id=supplier_id,
            supplier_sku=parsed_item.supplier_sku,
            name=parsed_item.name,
            current_price=parsed_item.price,
            characteristics=parsed_item.characteristics,
            product_id=product_id,
            last_ingested_at=func.now(),
            updated_at=func.now()
        )
        
        # ON CONFLICT: update existing row
        # In SQLAlchemy, excluded columns are accessed via stmt.excluded.column_name
        # This references the values from the row that would have been inserted
        # Use string keys (column names) as shown in SQLAlchemy examples
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=['supplier_id', 'supplier_sku'],
            set_={
                'name': excluded.name,
                'current_price': excluded.current_price,
                'characteristics': excluded.characteristics,
                'product_id': excluded.product_id,
                'last_ingested_at': excluded.last_ingested_at,
                'updated_at': excluded.updated_at
            }
        ).returning(SupplierItem)
        
        result = await session.execute(stmt)
        supplier_item = result.scalar_one()
        await session.flush()  # Flush to ensure item is available
        
        # Refresh the object to ensure we have the latest values from the database
        # This is especially important for ON CONFLICT UPDATE where the returned
        # object might be cached
        await session.refresh(supplier_item)
        
        logger.debug(
            "supplier_item_upserted",
            supplier_item_id=str(supplier_item.id),
            supplier_sku=parsed_item.supplier_sku,
            price_changed=price_changed,
            is_new_item=is_new_item,
            current_price=str(supplier_item.current_price),
            name=supplier_item.name
        )
        
        return supplier_item, price_changed, is_new_item
    
    except Exception as e:
        logger.error(
            "upsert_supplier_item_failed",
            supplier_id=str(supplier_id),
            supplier_sku=parsed_item.supplier_sku,
            error=str(e),
            error_type=type(e).__name__
        )
        raise DatabaseError(f"Failed to upsert supplier item: {e}") from e


async def create_price_history_entry(
    session: AsyncSession,
    supplier_item_id: uuid.UUID,
    price: Decimal
) -> PriceHistory:
    """Create a new price history entry.
    
    Args:
        session: Async database session
        supplier_item_id: UUID of the supplier item
        price: Price value to record
    
    Returns:
        PriceHistory instance
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        price_history = PriceHistory(
            supplier_item_id=supplier_item_id,
            price=price
        )
        session.add(price_history)
        await session.flush()  # Flush to get the ID
        
        logger.debug(
            "price_history_created",
            price_history_id=str(price_history.id),
            supplier_item_id=str(supplier_item_id),
            price=str(price)
        )
        return price_history
    
    except Exception as e:
        logger.error(
            "create_price_history_entry_failed",
            supplier_item_id=str(supplier_item_id),
            price=str(price),
            error=str(e),
            error_type=type(e).__name__
        )
        raise DatabaseError(f"Failed to create price history entry: {e}") from e


async def log_parsing_error(
    session: AsyncSession,
    task_id: str,
    supplier_id: Optional[uuid.UUID],
    error_type: str,
    error_message: str,
    row_number: Optional[int] = None,
    row_data: Optional[Dict[str, Any]] = None
) -> ParsingLog:
    """Log a parsing error to parsing_logs table.
    
    Args:
        session: Async database session
        task_id: Task identifier
        supplier_id: Optional UUID of the supplier
        error_type: Type of error (ValidationError, ParserError, etc.)
        error_message: Detailed error message
        row_number: Optional row number in source data
        row_data: Optional raw row data that caused error
    
    Returns:
        ParsingLog instance
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        parsing_log = ParsingLog(
            task_id=task_id,
            supplier_id=supplier_id,
            error_type=error_type,
            error_message=error_message,
            row_number=row_number,
            row_data=row_data
        )
        session.add(parsing_log)
        await session.flush()  # Flush to get the ID
        
        logger.debug(
            "parsing_error_logged",
            parsing_log_id=str(parsing_log.id),
            task_id=task_id,
            error_type=error_type,
            row_number=row_number
        )
        return parsing_log
    
    except Exception as e:
        logger.error(
            "log_parsing_error_failed",
            task_id=task_id,
            error_type=error_type,
            error=str(e),
            exception_type=type(e).__name__
        )
        # Don't raise - logging errors should not crash the worker
        # But we should still log the failure
        raise DatabaseError(f"Failed to log parsing error: {e}") from e


async def log_parsing_event(
    task_id: str,
    supplier_id: Optional[uuid.UUID],
    error_type: str,
    message: str,
) -> None:
    """
    Log a parsing event to the database for UI visibility.
    
    Convenience wrapper that creates a session and calls log_parsing_error.
    This enables events from the ML pipeline to appear in LiveLogViewer.
    
    Args:
        task_id: Task identifier
        supplier_id: Supplier UUID
        error_type: Event type (INFO, SUCCESS, WARNING, ERROR, etc.)
        message: Human-readable message
    """
    try:
        async with async_session_maker() as session:
            await log_parsing_error(
                session=session,
                task_id=task_id,
                supplier_id=supplier_id,
                error_type=error_type,
                error_message=message,
            )
            await session.commit()
    except Exception as e:
        # Don't fail the task if logging fails
        logger.warning(
            "failed_to_log_parsing_event",
            task_id=task_id,
            error_type=error_type,
            error=str(e),
        )


async def clear_parsing_logs(
    session: AsyncSession,
    keep_last_n: int = 0,
) -> int:
    """Clear parsing logs from the database.
    
    Args:
        session: Async database session
        keep_last_n: Number of recent logs to keep (0 = delete all)
    
    Returns:
        Number of deleted log entries
    
    Raises:
        DatabaseError: If database operation fails
    """
    from sqlalchemy import delete, text
    
    try:
        if keep_last_n > 0:
            # Keep the N most recent logs
            subquery = text(f"""
                DELETE FROM parsing_logs 
                WHERE id NOT IN (
                    SELECT id FROM parsing_logs 
                    ORDER BY created_at DESC 
                    LIMIT {keep_last_n}
                )
            """)
            result = await session.execute(subquery)
        else:
            # Delete all logs
            result = await session.execute(delete(ParsingLog))
        
        deleted_count = result.rowcount
        await session.commit()
        
        logger.info(
            "parsing_logs_cleared",
            deleted_count=deleted_count,
            kept_last_n=keep_last_n,
        )
        return deleted_count
    
    except Exception as e:
        logger.error(
            "clear_parsing_logs_failed",
            error=str(e),
            exception_type=type(e).__name__
        )
        raise DatabaseError(f"Failed to clear parsing logs: {e}") from e

