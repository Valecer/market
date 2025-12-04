"""Database operations for data ingestion pipeline.

Phase 9: Simplified - only logging and supplier operations remain.
Product/item persistence now handled by ml-analyze service.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from decimal import Decimal
from typing import Optional, Dict, Any
import uuid
import structlog

from src.db.base import async_session_maker
from src.db.models.supplier import Supplier
from src.db.models.parsing_log import ParsingLog
from src.errors.exceptions import DatabaseError

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
        source_type: Type of data source (google_sheets, csv, excel)
        metadata: Optional metadata dictionary
    
    Returns:
        Supplier instance (existing or newly created)
    
    Raises:
        DatabaseError: If database operation fails
    """
    try:
        # Map parser types to valid database source_type values
        source_type_map = {
            "google_sheets": "google_sheets",
            "csv": "csv",
            "excel": "excel",
        }
        db_source_type = source_type_map.get(source_type, "csv")
        
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
