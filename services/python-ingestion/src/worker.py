"""arq worker configuration for processing parse tasks.

This module configures the arq worker with:
    - parse_task: Data source parsing (Google Sheets, CSV, Excel)
    - match_items_task: Product matching pipeline
    - recalc_product_aggregates_task: Aggregate recalculation
    - enrich_item_task: Feature extraction and enrichment
    - handle_manual_match_event: Manual link/unlink operations
    - expire_review_queue_task: Cron job to expire old review items
"""
from arq.connections import RedisSettings, ArqRedis
from arq.worker import Retry
from arq import cron
from typing import Dict, Any, Optional
from datetime import timedelta, datetime, timezone
import structlog
import asyncio
from src.config import settings, matching_settings, configure_logging
# Import parsers package to trigger __init__.py registration
import src.parsers  # noqa: F401
from src.parsers import create_parser_instance
from src.models.queue_message import ParseTaskMessage
from src.errors.exceptions import ParserError, ValidationError, DatabaseError
from src.db.base import async_session_maker
from src.db.operations import (
    get_or_create_supplier,
    upsert_supplier_item,
    create_price_history_entry,
    log_parsing_error
)
# Import matching pipeline tasks
from src.tasks.matching_tasks import (
    match_items_task,
    recalc_product_aggregates_task,
    enrich_item_task,
    handle_manual_match_event,
    expire_review_queue_task,
)
# Import sync pipeline tasks
from src.tasks.sync_tasks import (
    trigger_master_sync_task,
    scheduled_sync_task,
    poll_manual_sync_trigger,
    poll_parse_triggers,
    get_sync_interval_hours,
)
# Import ML integration tasks (Phase 8)
from src.tasks.download_tasks import download_and_trigger_ml
from src.tasks.ml_polling_tasks import poll_ml_job_status_task
from src.tasks.cleanup_tasks import cleanup_shared_files_task

# Configure logging
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)

# Exponential backoff delays: [1s, 5s, 25s]
RETRY_DELAYS = [1, 5, 25]  # seconds


async def parse_task(ctx: Dict[str, Any], message: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
    """Process a parse task from the queue.
    
    This function is called by arq worker when a task is received from Redis queue.
    It validates the message using ParseTaskMessage, creates parser instance,
    validates config, and parses the data source.
    
    Implements retry logic with exponential backoff (1s, 5s, 25s) and routes
    permanently failed tasks to dead letter queue after max_retries exceeded.
    
    Args:
        ctx: Worker context (contains Redis connection, job metadata)
        message: Task message dictionary (will be validated as ParseTaskMessage)
        **kwargs: Additional keyword arguments (merged with message if provided)
    
    Returns:
        Dictionary with task results:
            - task_id: Task identifier
            - status: "success", "partial_success", or "error"
            - items_parsed: Number of items successfully parsed
            - errors: List of error messages (if any)
    
    Raises:
        Retry: If task should be retried with exponential backoff
        ParserError: If parser fails permanently (after max retries)
        DatabaseError: If database operation fails permanently (after max retries)
    """
    # Merge message dict with kwargs (kwargs take precedence)
    task_data = {}
    if message:
        task_data.update(message)
    task_data.update(kwargs)
    
    # Validate message using Pydantic model
    try:
        task_msg = ParseTaskMessage(**task_data)
    except Exception as e:
        logger.error("invalid_message_format", error=str(e), task_data=task_data)
        # Invalid message format - don't retry
        return {
            "task_id": task_data.get("task_id", "unknown"),
            "status": "error",
            "items_parsed": 0,
            "errors": [f"Invalid message format: {str(e)}"]
        }
    
    task_id = task_msg.task_id
    parser_type = task_msg.parser_type
    supplier_name = task_msg.supplier_name
    source_config = task_msg.source_config
    # Use arq's job_try from context if available, otherwise use message retry_count
    # job_try is 1-indexed in arq (1=first attempt, 2=second attempt, etc.)
    job_try = ctx.get("job_try", 1) if ctx else 1
    retry_count = job_try - 1  # Convert to 0-indexed for our logic (0=first attempt, 1=first retry)
    max_retries = task_msg.max_retries
    # Get arq's max_tries to ensure we don't exceed it
    max_tries = WorkerSettings.max_tries
    
    # Create logger with task context
    log = logger.bind(task_id=task_id, parser_type=parser_type, supplier_name=supplier_name)
    
    try:
        log.info("parse_task_started", retry_count=retry_count, max_retries=max_retries)
        
        # Create parser instance
        try:
            parser = create_parser_instance(parser_type)
        except ParserError as e:
            log.error("parser_creation_failed", error=str(e))
            # Parser creation failure - retry with backoff if not exceeded max retries
            should_retry = _handle_retry(log, retry_count, max_tries, e, "ParserError")
            if should_retry:
                raise Retry(defer=_get_retry_delay(retry_count))
            else:
                # Max retries exceeded - raise original exception to trigger DLQ
                raise
        
        # Validate parser configuration
        try:
            if not parser.validate_config(source_config):
                raise ValidationError(f"Invalid configuration for parser '{parser_type}'")
        except ValidationError as e:
            log.error("config_validation_failed", error=str(e))
            # Validation errors don't trigger retry (invalid config won't fix itself)
            return {
                "task_id": task_id,
                "status": "error",
                "items_parsed": 0,
                "errors": [f"Validation error: {str(e)}"]
            }
        
        # Parse data source
        try:
            parsed_items = await parser.parse(source_config)
            items_count = len(parsed_items)
            
            log.info(
                "parse_completed",
                items_parsed=items_count,
                parser_name=parser.get_parser_name()
            )
        except ValidationError as e:
            # Validation errors during parsing are logged but don't crash the worker
            log.warning("parse_validation_error", error=str(e))
            return {
                "task_id": task_id,
                "status": "partial_success",
                "items_parsed": 0,
                "errors": [str(e)]
            }
        except (ParserError, DatabaseError) as e:
            # Parser and database errors trigger retry if not exceeded max retries
            log.error("parse_task_failed", error=str(e), error_type=type(e).__name__)
            should_retry = _handle_retry(log, retry_count, max_tries, e, type(e).__name__)
            if should_retry:
                raise Retry(defer=_get_retry_delay(retry_count))
            else:
                # Max retries exceeded - move to DLQ
                await _move_to_dlq(ctx, task_id, e)
                # Re-raise original exception to mark job as failed
                # Don't wrap it - let arq handle the failure
                raise
        
        # Process parsed items and persist to database
        start_time = datetime.now(timezone.utc)
        success_count = 0
        failed_count = 0
        price_history_count = 0
        
        try:
            # Get or create supplier within transaction
            async with async_session_maker() as session:
                async with session.begin():
                    try:
                        # Get or create supplier
                        # Map parser_type to valid source_type for database constraint
                        # "stub" is used in tests but not allowed in DB constraint
                        source_type_map = {
                            "stub": "csv",  # Map stub parser to csv for testing
                            "google_sheets": "google_sheets",
                            "csv": "csv",
                            "excel": "excel",
                        }
                        db_source_type = source_type_map.get(parser_type, parser_type)
                        
                        supplier = await get_or_create_supplier(
                            session=session,
                            supplier_name=supplier_name,
                            source_type=db_source_type,
                            metadata=source_config
                        )
                        supplier_id = supplier.id
                        
                        log.debug(
                            "supplier_ready",
                            supplier_id=str(supplier_id),
                            supplier_name=supplier_name
                        )
                        
                        # Process each parsed item
                        for row_number, parsed_item in enumerate(parsed_items, start=1):
                            try:
                                # Upsert supplier item
                                supplier_item, price_changed, is_new_item = await upsert_supplier_item(
                                    session=session,
                                    supplier_id=supplier_id,
                                    parsed_item=parsed_item
                                )
                                
                                # Create price history entry if price changed OR if it's a new item
                                # This ensures all items have price history entries
                                if price_changed or is_new_item:
                                    await create_price_history_entry(
                                        session=session,
                                        supplier_item_id=supplier_item.id,
                                        price=parsed_item.price
                                    )
                                    price_history_count += 1
                                
                                success_count += 1
                                
                            except ValidationError as e:
                                # Row-level validation error - log but continue processing
                                failed_count += 1
                                try:
                                    await log_parsing_error(
                                        session=session,
                                        task_id=task_id,
                                        supplier_id=supplier_id,
                                        error_type="ValidationError",
                                        error_message=str(e),
                                        row_number=row_number,
                                        row_data=parsed_item.model_dump() if hasattr(parsed_item, 'model_dump') else None
                                    )
                                except Exception as log_err:
                                    # Even logging errors shouldn't crash - just log to structlog
                                    log.error(
                                        "failed_to_log_parsing_error",
                                        error=str(log_err),
                                        original_error=str(e),
                                        row_number=row_number
                                    )
                                
                                log.warning(
                                    "row_validation_failed",
                                    row_number=row_number,
                                    error=str(e),
                                    supplier_sku=parsed_item.supplier_sku if hasattr(parsed_item, 'supplier_sku') else None
                                )
                                # Continue processing other rows
                                continue
                            
                            except DatabaseError as e:
                                # Database errors during row processing - rollback transaction
                                log.error(
                                    "row_database_error",
                                    row_number=row_number,
                                    error=str(e),
                                    error_type=type(e).__name__
                                )
                                # Transaction will rollback automatically
                                raise
                        
                        # Transaction commits automatically on successful exit from context manager
                        log.info(
                            "database_transaction_committed",
                            supplier_id=str(supplier_id),
                            success_count=success_count,
                            failed_count=failed_count
                        )
                    
                    except DatabaseError as e:
                        # Database errors trigger transaction rollback and task retry
                        log.error(
                            "database_transaction_failed",
                            error=str(e),
                            error_type=type(e).__name__
                        )
                        # Transaction will rollback automatically
                        # Re-raise to trigger retry logic
                        raise
                    
                    except Exception as e:
                        # Unexpected errors during database operations
                        log.error(
                            "unexpected_database_error",
                            error=str(e),
                            error_type=type(e).__name__
                        )
                        # Transaction will rollback automatically
                        raise DatabaseError(f"Unexpected database error: {e}") from e
        
        except DatabaseError as e:
            # Database errors trigger retry if not exceeded max retries
            log.error("database_operation_failed", error=str(e), error_type=type(e).__name__)
            should_retry = _handle_retry(log, retry_count, max_tries, e, type(e).__name__)
            if should_retry:
                raise Retry(defer=_get_retry_delay(retry_count))
            else:
                # Max retries exceeded - move to DLQ
                await _move_to_dlq(ctx, task_id, e)
                # Re-raise original exception to mark job as failed
                raise
        
        # Calculate task statistics
        end_time = datetime.now(timezone.utc)
        duration_seconds = (end_time - start_time).total_seconds()
        
        # Determine status
        if failed_count == 0:
            status = "success"
        elif success_count > 0:
            status = "partial_success"
        else:
            status = "error"
        
        log.info(
            "parse_task_completed",
            status=status,
            items_total=items_count,
            items_success=success_count,
            items_failed=failed_count,
            price_history_entries=price_history_count,
            duration_seconds=duration_seconds
        )
        
        # Chain to matching pipeline on successful ingestion
        if status in ("success", "partial_success") and success_count > 0:
            redis: Optional[ArqRedis] = ctx.get("redis")
            if redis:
                try:
                    match_task_id = f"match-{task_id}-{int(datetime.now(timezone.utc).timestamp())}"
                    await redis.enqueue_job(
                        "match_items_task",
                        task_id=match_task_id,
                        batch_size=matching_settings.batch_size,
                    )
                    log.info(
                        "match_task_chained",
                        match_task_id=match_task_id,
                        batch_size=matching_settings.batch_size,
                    )
                except Exception as chain_err:
                    # Don't fail parse task if chaining fails
                    log.warning(
                        "match_task_chain_failed",
                        error=str(chain_err),
                    )
        
        return {
            "task_id": task_id,
            "status": status,
            "items_parsed": success_count,
            "items_failed": failed_count,
            "price_history_entries": price_history_count,
            "duration_seconds": duration_seconds,
            "errors": [] if failed_count == 0 else [f"{failed_count} rows failed validation"]
        }
    
    except ValidationError as e:
        # Validation errors don't trigger retry (invalid config won't fix itself)
        log.error("task_validation_failed", error=str(e))
        return {
            "task_id": task_id,
            "status": "error",
            "items_parsed": 0,
            "errors": [f"Validation error: {str(e)}"]
        }
    
    except Retry:
        # Re-raise Retry exception to let arq handle it
        raise
    
    except (ParserError, DatabaseError):
        # These were already handled above - re-raise to let arq mark job as failed
        # They've already been moved to DLQ if max retries exceeded
        raise
    
    except Exception as e:
        # Unexpected errors - retry with backoff if not exceeded max retries
        log.error("unexpected_error", error=str(e), error_type=type(e).__name__)
        should_retry = _handle_retry(log, retry_count, max_tries, e, "UnexpectedError")
        if should_retry:
            raise Retry(defer=_get_retry_delay(retry_count))
        else:
            # Max retries exceeded - move to DLQ
            await _move_to_dlq(ctx, task_id, e)
            # Wrap in ParserError to mark job as failed (only for truly unexpected errors)
            raise ParserError(f"Unexpected error after {max_retries} retries: {e}") from e


def _get_retry_delay(retry_count: int) -> timedelta:
    """Get exponential backoff delay for retry attempt.
    
    Args:
        retry_count: Current retry attempt number (0-indexed)
    
    Returns:
        Timedelta delay before next retry
    """
    if retry_count < len(RETRY_DELAYS):
        delay_seconds = RETRY_DELAYS[retry_count]
    else:
        # Use last delay if retry_count exceeds available delays
        delay_seconds = RETRY_DELAYS[-1]
    
    return timedelta(seconds=delay_seconds)


async def _move_to_dlq(ctx: Dict[str, Any], task_id: str, error: Exception) -> None:
    """Move a failed job to the dead letter queue.
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Task identifier
        error: Exception that caused the failure
    """
    try:
        redis: ArqRedis = ctx.get("redis")
        if redis:
            dlq_name = settings.dlq_name
            logger.warning(
                "job_moved_to_dlq",
                task_id=task_id,
                dlq_name=dlq_name,
                error=str(error)
            )
            # Store task_id in DLQ set for tracking
            await redis.sadd(f"arq:dlq:{dlq_name}", task_id)
            await redis.expire(f"arq:dlq:{dlq_name}", 86400 * 7)  # Keep for 7 days
    except Exception as e:
        logger.error("dlq_routing_failed", error=str(e), task_id=task_id)


def _handle_retry(
    log: Any,
    retry_count: int,
    max_tries: int,
    error: Exception,
    error_type: str
) -> bool:
    """Handle retry logic and DLQ routing.
    
    Args:
        log: Structured logger instance
        retry_count: Current retry attempt (0-indexed: 0=first attempt, 1=first retry, etc.)
        max_tries: Maximum total attempts allowed (arq's max_tries setting)
        error: Exception that triggered retry
        error_type: Type name of the error
    
    Returns:
        True if task should be retried, False if max retries exceeded (should go to DLQ)
    
    Note:
        retry_count is 0-indexed (0 = first attempt, 1 = first retry, 2 = second retry)
        max_tries is arq's maximum total attempts (e.g., 3 means attempts 1, 2, 3)
        job_try = retry_count + 1 (1-indexed)
        We should stop when job_try > max_tries, which means retry_count >= max_tries
        Example: max_tries=3, we allow job_try 1, 2, 3 (retry_count 0, 1, 2)
        We stop when retry_count >= 3 (which would be job_try=4, exceeding max_tries)
    """
    # retry_count is 0-indexed: 0=first attempt, 1=first retry, 2=second retry
    # max_tries is arq's maximum total attempts (e.g., 3 means attempts 1, 2, 3)
    # job_try = retry_count + 1 (1-indexed)
    # We should stop when job_try > max_tries, which means retry_count >= max_tries
    # Example: max_tries=3, we allow job_try 1, 2, 3 (retry_count 0, 1, 2)
    # We stop when retry_count >= 3 (which would be job_try=4, exceeding max_tries)
    if retry_count >= max_tries:
        log.error(
            "task_max_retries_exceeded",
            retry_count=retry_count,
            job_try=retry_count + 1,
            max_tries=max_tries,
            error=str(error),
            error_type=error_type
        )
        # Task will be moved to dead letter queue by arq after this exception
        # Don't raise Retry - let the exception propagate to trigger DLQ
        return False
    else:
        next_retry = retry_count + 1
        delay = _get_retry_delay(retry_count)
        log.warning(
            "task_retry_scheduled",
            retry_count=next_retry,
            max_tries=max_tries,
            delay_seconds=delay.total_seconds(),
            error=str(error),
            error_type=error_type
        )
        return True


async def monitor_queue_depth(ctx: Dict[str, Any]) -> None:
    """Periodic task to monitor queue depth and log statistics.
    
    This function runs periodically to log queue depth for monitoring.
    It's registered as a cron job in WorkerSettings.
    
    Args:
        ctx: Worker context (contains Redis connection)
    """
    try:
        redis: ArqRedis = ctx.get("redis")
        if not redis:
            logger.warning("monitor_queue_depth_no_redis")
            return
        
        # Get queue depth
        queue_name = settings.queue_name
        dlq_name = settings.dlq_name
        
        queue_depth = await redis.llen(f"arq:queue:{queue_name}")
        dlq_depth = await redis.llen(f"arq:queue:{dlq_name}")
        
        logger.info(
            "queue_depth_monitor",
            queue_name=queue_name,
            queue_depth=queue_depth,
            dlq_name=dlq_name,
            dlq_depth=dlq_depth
        )
    except Exception as e:
        logger.error("monitor_queue_depth_error", error=str(e))


async def on_job_end(ctx: Dict[str, Any]) -> None:
    """Hook called after each job ends (success or failure).
    
    Moves failed jobs that exceeded max retries to the dead letter queue.
    
    Args:
        ctx: Worker context containing job metadata
    """
    try:
        # Log context to debug
        logger.debug("on_job_end_called", ctx_keys=list(ctx.keys()) if ctx else [])
        
        job_try = ctx.get("job_try", 1)
        job_result = ctx.get("job_result")
        job_id = ctx.get("job_id", "unknown")
        
        # Check if job failed (job_result is an exception)
        # arq's max_tries is the total number of attempts (including first try)
        # So if job_try > max_tries, the job has exceeded retries
        max_tries = WorkerSettings.max_tries
        
        # Check if job failed and exceeded max retries
        is_failed = job_result is not None and isinstance(job_result, Exception)
        exceeded_retries = job_try > max_tries
        
        if is_failed and exceeded_retries:
            # Job failed after max retries - move to DLQ
            redis: ArqRedis = ctx.get("redis")
            if redis:
                dlq_name = settings.dlq_name
                
                logger.warning(
                    "job_moved_to_dlq",
                    job_id=job_id,
                    job_try=job_try,
                    max_tries=max_tries,
                    dlq_name=dlq_name,
                    error=str(job_result) if job_result else None
                )
                
                # Store job_id in DLQ set for tracking
                await redis.sadd(f"arq:dlq:{dlq_name}", job_id)
                await redis.expire(f"arq:dlq:{dlq_name}", 86400 * 7)  # Keep for 7 days
        else:
            logger.debug(
                "on_job_end_skipped",
                job_id=job_id,
                job_try=job_try,
                max_tries=max_tries,
                is_failed=is_failed,
                exceeded_retries=exceeded_retries
            )
    except Exception as e:
        logger.error("on_job_end_error", error=str(e), ctx_keys=list(ctx.keys()) if ctx else [])


class WorkerSettings:
    """arq worker configuration settings.
    
    This class is imported by arq CLI: `python -m arq src.worker.WorkerSettings`
    
    Registered Tasks:
        - parse_task: Parse data sources (Google Sheets, CSV, Excel)
        - match_items_task: Match supplier items to products
        - recalc_product_aggregates_task: Recalculate product min_price/availability
        - enrich_item_task: Extract features from item names
        - handle_manual_match_event: Process manual link/unlink events
        - expire_review_queue_task: Expire old review queue items (cron)
        
    Cron Jobs:
        - monitor_queue_depth: Every 5 minutes
        - expire_review_queue_task: Daily at midnight
    """
    
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.queue_name  # Match the queue name used by Bun API
    max_jobs = settings.max_workers
    job_timeout = settings.job_timeout
    keep_result = 3600  # Keep results for 1 hour
    max_tries = 3  # Maximum retry attempts (matches max_retries in ParseTaskMessage)
    
    # Register all worker functions
    functions = [
        # Phase 1: Data ingestion
        parse_task,
        # Phase 4: Matching pipeline
        match_items_task,
        recalc_product_aggregates_task,
        enrich_item_task,
        handle_manual_match_event,
        expire_review_queue_task,
        # Phase 6: Master sync pipeline
        trigger_master_sync_task,
        scheduled_sync_task,
        # Phase 8: ML integration pipeline
        download_and_trigger_ml,
        poll_ml_job_status_task,
        cleanup_shared_files_task,
    ]
    
    # Register job lifecycle hooks
    on_job_end = on_job_end
    
    # Register cron jobs
    cron_jobs = [
        # Queue monitoring: every 5 minutes
        cron(monitor_queue_depth, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # Review queue expiration: daily at midnight UTC
        cron(expire_review_queue_task, hour=0, minute=0),
        # Master sync: at configurable interval (default every 8 hours)
        # Hours are calculated from SYNC_INTERVAL_HOURS env var
        cron(
            scheduled_sync_task,
            hour=set(range(0, 24, get_sync_interval_hours())),
            minute=0,
            unique=True,
            run_at_startup=False,
        ),
        # Poll for manual sync triggers every minute
        # Bun API sets sync:trigger key, worker polls and executes
        cron(
            poll_manual_sync_trigger,
            minute=set(range(0, 60)),  # Every minute
            unique=True,
        ),
        # Poll for parse triggers every 10 seconds
        # Bun API sets parse:triggers list, worker polls and enqueues parse_task
        cron(
            poll_parse_triggers,
            second={0, 10, 20, 30, 40, 50},  # Every 10 seconds
            unique=True,
        ),
        # Phase 8: Poll ML job status every 10 seconds
        # Syncs job progress from ml-analyze to Redis
        cron(
            poll_ml_job_status_task,
            second={5, 15, 25, 35, 45, 55},  # Every 10 seconds, offset from parse triggers
            unique=True,
        ),
        # Phase 8: Cleanup shared files every 6 hours
        # Removes files older than FILE_CLEANUP_TTL_HOURS (default 24)
        cron(
            cleanup_shared_files_task,
            hour={0, 6, 12, 18},  # Every 6 hours
            minute=30,  # Offset from other hourly tasks
            unique=True,
        ),
    ]

