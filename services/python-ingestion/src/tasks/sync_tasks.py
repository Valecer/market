"""Queue tasks for the master sync pipeline.

This module implements the sync pipeline tasks:
    - trigger_master_sync_task: Main sync orchestration task
    - scheduled_sync_task: Cron wrapper for automatic scheduled syncs
"""
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from uuid import UUID

from arq.connections import ArqRedis
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import settings
from src.db.base import async_session_maker
from src.db.models import Supplier
from src.db.operations import log_parsing_error, clear_parsing_logs
from src.services.master_sheet_ingestor import MasterSheetIngestor
from src.services.sync_state import (
    acquire_sync_lock,
    release_sync_lock,
    set_sync_started,
    set_sync_processing_suppliers,
    set_sync_idle,
    update_sync_progress,
    record_sync_completion,
    get_sync_trigger,
    clear_sync_trigger,
    get_pending_parse_triggers,
)
from src.models.sync_messages import TriggerMasterSyncMessage
from src.models.master_sheet_config import MasterSyncResult
from src.errors.exceptions import ParserError

logger = structlog.get_logger(__name__)


async def _log_sync_event(
    task_id: str,
    error_type: str,
    message: str,
    supplier_id: Optional[UUID] = None,
) -> None:
    """
    Log a sync event to parsing_logs for UI visibility.

    Args:
        task_id: Sync task identifier
        error_type: Event type (INFO, SUCCESS, WARNING, ERROR)
        message: Human-readable message
        supplier_id: Optional supplier UUID for context
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
        logger.warning(
            "failed_to_log_sync_event",
            task_id=task_id,
            error_type=error_type,
            error=str(e),
        )


async def _clear_old_logs() -> int:
    """
    Clear old parsing logs before a new sync.
    
    Returns:
        Number of deleted log entries
    """
    try:
        async with async_session_maker() as session:
            deleted = await clear_parsing_logs(session, keep_last_n=0)
            return deleted
    except Exception as e:
        logger.warning(
            "failed_to_clear_old_logs",
            error=str(e),
        )
        return 0


def get_sync_interval_hours() -> int:
    """Get sync interval from settings.
    
    Uses the SYNC_INTERVAL_HOURS environment variable via pydantic-settings.
    
    Returns:
        Sync interval in hours (default: 8)
    """
    return settings.sync_interval_hours


def get_master_sheet_url() -> Optional[str]:
    """Get Master Sheet URL from environment variable.
    
    Returns:
        Master Sheet URL or None if not configured
    """
    return os.getenv("MASTER_SHEET_URL")


async def get_master_sheet_url_from_redis(redis: Redis) -> Optional[str]:
    """Get Master Sheet URL from Redis settings.
    
    Args:
        redis: Redis connection
    
    Returns:
        Master Sheet URL or None if not configured
    """
    try:
        url = await redis.get("settings:master_sheet_url")
        if url:
            decoded = url.decode("utf-8") if isinstance(url, bytes) else url
            return decoded if decoded else None
        return None
    except Exception as e:
        logger.warning("failed_to_get_sheet_url_from_redis", error=str(e))
        return None


async def get_master_sheet_name(redis: Redis, default: str = "Suppliers") -> str:
    """Get Master Sheet worksheet name from Redis.
    
    Args:
        redis: Redis connection
        default: Default sheet name if not configured (default: "Suppliers")
    
    Returns:
        Worksheet name to parse
    """
    try:
        sheet_name = await redis.get("settings:master_sheet_name")
        if sheet_name:
            return sheet_name.decode("utf-8") if isinstance(sheet_name, bytes) else sheet_name
        return default
    except Exception as e:
        logger.warning("failed_to_get_sheet_name", error=str(e), default=default)
        return default


@dataclass
class SyncMetrics:
    """Metrics collected during sync task execution."""
    master_sheet_parsed: bool = False
    suppliers_created: int = 0
    suppliers_updated: int = 0
    suppliers_deactivated: int = 0
    suppliers_skipped: int = 0
    parse_tasks_enqueued: int = 0
    ml_jobs_triggered: int = 0
    ml_job_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/response."""
        return {
            "master_sheet_parsed": self.master_sheet_parsed,
            "suppliers_created": self.suppliers_created,
            "suppliers_updated": self.suppliers_updated,
            "suppliers_deactivated": self.suppliers_deactivated,
            "suppliers_skipped": self.suppliers_skipped,
            "parse_tasks_enqueued": self.parse_tasks_enqueued,
            "ml_jobs_triggered": self.ml_jobs_triggered,
            "ml_job_ids": self.ml_job_ids,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
        }


async def trigger_master_sync_task(
    ctx: Dict[str, Any],
    task_id: str,
    triggered_by: str = "manual",
    triggered_at: Optional[str] = None,
    master_sheet_url: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute the master sync pipeline.
    
    This task orchestrates the full sync pipeline:
    1. Acquire sync lock (prevent concurrent syncs)
    2. Update status to syncing_master
    3. Parse Master Sheet and get supplier configs
    4. Sync suppliers to database (create/update/deactivate)
    5. Update status to processing_suppliers
    6. Enqueue parse_task for each active supplier
    7. Record completion and release lock
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique identifier for tracking the sync job
        triggered_by: What initiated the sync ("manual" or "scheduled")
        triggered_at: ISO timestamp when sync was triggered
        master_sheet_url: Optional override for Master Sheet URL
        
    Returns:
        Dictionary with task results and metrics:
            - task_id: Task identifier
            - status: "success", "partial_success", or "error"
            - triggered_by: What triggered the sync
            - metrics: Detailed sync metrics
    """
    start_time = time.time()
    metrics = SyncMetrics()
    
    log = logger.bind(
        task_id=task_id,
        triggered_by=triggered_by,
    )
    log.info("trigger_master_sync_task_started")
    
    # Log sync start to parsing_logs for UI visibility
    await _log_sync_event(
        task_id=task_id,
        error_type="INFO",
        message=f"Master sync started ({triggered_by})",
    )
    
    # Get Redis connection from arq context
    redis: Optional[ArqRedis] = ctx.get("redis")
    if not redis:
        log.error("no_redis_connection")
        return {
            "task_id": task_id,
            "status": "error",
            "error": "No Redis connection available",
            **metrics.to_dict(),
        }
    
    # Resolve Master Sheet URL (optional - can sync without it)
    # Priority: parameter > Redis > environment variable
    if not master_sheet_url:
        master_sheet_url = await get_master_sheet_url_from_redis(redis)
        if master_sheet_url:
            log.debug("master_sheet_url_from_redis", url=master_sheet_url)
    if not master_sheet_url:
        master_sheet_url = get_master_sheet_url()
        if master_sheet_url:
            log.debug("master_sheet_url_from_env", url=master_sheet_url)
    sheet_url = master_sheet_url
    
    if not sheet_url:
        log.warning("no_master_sheet_url_configured", message="Master sheet URL not found in Redis or environment")
    
    try:
        # Step 1: Acquire sync lock
        # Convert ArqRedis to regular Redis for our sync_state functions
        # ArqRedis is a subclass of Redis, so this should work
        lock_acquired, current_holder = await acquire_sync_lock(redis, task_id)
        
        if not lock_acquired:
            log.warning(
                "sync_lock_not_acquired",
                current_holder=current_holder,
            )
            return {
                "task_id": task_id,
                "status": "error",
                "error": f"Sync already in progress (task: {current_holder})",
                **metrics.to_dict(),
            }
        
        try:
            # Step 2: Clear old logs for fresh sync display
            deleted_logs = await _clear_old_logs()
            if deleted_logs > 0:
                log.info("old_logs_cleared", deleted_count=deleted_logs)
            
            # Step 3: Update status to syncing_master
            await set_sync_started(redis, task_id)
            
            # Step 4: Parse Master Sheet (if URL is configured)
            if sheet_url:
                log.info("parsing_master_sheet", sheet_url=sheet_url)
                ingestor = MasterSheetIngestor()
                
                # Get sheet name from Redis settings
                sheet_name = await get_master_sheet_name(redis)
                log.debug("using_sheet_name", sheet_name=sheet_name)
                
                try:
                    configs = await ingestor.ingest(
                        master_sheet_url=sheet_url,
                        sheet_name=sheet_name,
                    )
                    metrics.master_sheet_parsed = True
                    log.info("master_sheet_parsed", configs_count=len(configs))
                except ParserError as e:
                    log.error("master_sheet_parse_failed", error=str(e))
                    metrics.errors.append(f"Master sheet parse error: {e}")
                    raise
                
                # Step 4: Sync suppliers to database
                log.info("syncing_suppliers")
                sync_result: MasterSyncResult = await ingestor.sync_suppliers(configs)
                
                metrics.suppliers_created = sync_result.suppliers_created
                metrics.suppliers_updated = sync_result.suppliers_updated
                metrics.suppliers_deactivated = sync_result.suppliers_deactivated
                metrics.suppliers_skipped = sync_result.suppliers_skipped
                metrics.errors.extend(sync_result.errors)
                
                log.info(
                    "suppliers_synced",
                    created=sync_result.suppliers_created,
                    updated=sync_result.suppliers_updated,
                    deactivated=sync_result.suppliers_deactivated,
                )
            else:
                log.info(
                    "no_master_sheet_skipping",
                    message="Master sheet URL not configured, processing existing suppliers only",
                )
            
            # Step 5: Get active suppliers for parsing
            active_suppliers = await _get_active_suppliers()
            
            # Step 6: Update status to processing_suppliers
            await set_sync_processing_suppliers(
                redis, task_id, len(active_suppliers)
            )
            
            # Step 7: Enqueue parse_task for each active supplier
            log.info(
                "enqueuing_parse_tasks",
                active_suppliers=len(active_suppliers),
            )
            
            for idx, supplier in enumerate(active_suppliers, start=1):
                try:
                    job_id = await _enqueue_supplier_parse(
                        redis=redis,
                        supplier=supplier,
                        parent_task_id=task_id,
                        log=log,
                    )
                    metrics.parse_tasks_enqueued += 1
                    
                    # Track ML job IDs for status monitoring
                    if job_id:
                        metrics.ml_jobs_triggered += 1
                        metrics.ml_job_ids.append(job_id)
                    
                    # Update progress
                    await update_sync_progress(redis, idx, len(active_suppliers))
                    
                except Exception as e:
                    error_msg = f"Failed to enqueue parse for {supplier.name}: {e}"
                    metrics.errors.append(error_msg)
                    log.warning(
                        "parse_task_enqueue_failed",
                        supplier_name=supplier.name,
                        error=str(e),
                    )
            
            # Step 8: Record completion
            await record_sync_completion(redis)
            
            metrics.duration_seconds = time.time() - start_time
            
            # Determine status
            if not metrics.errors:
                status = "success"
            elif metrics.parse_tasks_enqueued > 0 or metrics.master_sheet_parsed:
                status = "partial_success"
            else:
                status = "error"
            
            log.info(
                "trigger_master_sync_task_completed",
                status=status,
                **metrics.to_dict(),
            )
            
            # Log completion to parsing_logs
            if status == "success":
                await _log_sync_event(
                    task_id=task_id,
                    error_type="SUCCESS",
                    message=f"Sync completed: {metrics.parse_tasks_enqueued} suppliers queued for processing",
                )
            elif status == "partial_success":
                await _log_sync_event(
                    task_id=task_id,
                    error_type="WARNING",
                    message=f"Sync completed with warnings: {len(metrics.errors)} errors, {metrics.parse_tasks_enqueued} suppliers queued",
                )
            else:
                await _log_sync_event(
                    task_id=task_id,
                    error_type="ERROR",
                    message=f"Sync failed: {'; '.join(metrics.errors[:2])}",
                )
            
            return {
                "task_id": task_id,
                "status": status,
                "triggered_by": triggered_by,
                **metrics.to_dict(),
            }
            
        finally:
            # Always release lock and set idle
            await set_sync_idle(redis)
            await release_sync_lock(redis, task_id)
    
    except Exception as e:
        metrics.duration_seconds = time.time() - start_time
        metrics.errors.append(str(e))
        
        log.error(
            "trigger_master_sync_task_failed",
            error=str(e),
            error_type=type(e).__name__,
            **metrics.to_dict(),
        )
        
        # Log error to parsing_logs
        await _log_sync_event(
            task_id=task_id,
            error_type="ERROR",
            message=f"Sync failed: {type(e).__name__}: {str(e)[:100]}",
        )
        
        return {
            "task_id": task_id,
            "status": "error",
            "triggered_by": triggered_by,
            "error": str(e),
            **metrics.to_dict(),
        }


async def scheduled_sync_task(
    ctx: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """Cron wrapper for scheduled automatic sync.
    
    This task is registered as a cron job and calls trigger_master_sync_task
    with triggered_by="scheduled".
    
    Args:
        ctx: Worker context (contains Redis connection)
        
    Returns:
        Result from trigger_master_sync_task
    """
    task_id = f"sync-scheduled-{int(datetime.now(timezone.utc).timestamp())}"
    
    logger.info(
        "scheduled_sync_task_started",
        task_id=task_id,
    )
    
    return await trigger_master_sync_task(
        ctx=ctx,
        task_id=task_id,
        triggered_by="scheduled",
    )


async def poll_manual_sync_trigger(
    ctx: Dict[str, Any],
    **kwargs
) -> Optional[Dict[str, Any]]:
    """Poll for manual sync trigger requests from Bun API.
    
    This task runs every 5 seconds to check if a manual sync
    has been requested via the sync:trigger Redis key.
    
    Args:
        ctx: Worker context (contains Redis connection)
        
    Returns:
        Result from trigger_master_sync_task if trigger found, else None
    """
    redis: Optional[ArqRedis] = ctx.get("redis")
    if not redis:
        return None
    
    # Check for pending trigger
    trigger = await get_sync_trigger(redis)
    
    if trigger:
        task_id = trigger.get("task_id", f"sync-manual-{int(time.time())}")
        triggered_by = trigger.get("triggered_by", "manual")
        
        logger.info(
            "manual_sync_trigger_detected",
            task_id=task_id,
            triggered_by=triggered_by,
        )
        
        # Clear the trigger before starting (prevent duplicate runs)
        await clear_sync_trigger(redis)
        
        # Execute the sync
        return await trigger_master_sync_task(
            ctx=ctx,
            task_id=task_id,
            triggered_by=triggered_by,
        )
    
    return None


async def _get_active_suppliers() -> List[Supplier]:
    """Get all active suppliers from database.
    
    Active suppliers have meta.is_active != False (default True)
    
    Returns:
        List of active Supplier models
    """
    async with async_session_maker() as session:
        # Get all suppliers
        query = select(Supplier).order_by(Supplier.name)
        result = await session.execute(query)
        suppliers = result.scalars().all()
        
        # Filter active suppliers
        # is_active is stored in meta JSONB field
        active_suppliers = []
        for supplier in suppliers:
            meta = supplier.meta or {}
            is_active = meta.get("is_active", True)  # Default to True
            if is_active:
                active_suppliers.append(supplier)
        
        return active_suppliers


async def _enqueue_supplier_parse(
    redis: ArqRedis,
    supplier: Supplier,
    parent_task_id: str,
    log: Any,
) -> str:
    """Enqueue a parse task for a supplier.
    
    Phase 9: Always uses ML pipeline (download_and_trigger_ml).
    All parsing/extraction handled by ml-analyze service.
    
    Args:
        redis: ArqRedis connection
        supplier: Supplier model with configuration
        parent_task_id: Parent sync task ID for correlation
        log: Logger instance
        
    Returns:
        Job ID for ML processing
    """
    from uuid import uuid4
    from pathlib import Path
    
    meta = supplier.meta or {}
    source_url = meta.get("source_url")
    
    if not source_url:
        raise ValueError(f"Supplier {supplier.name} has no source_url configured")
    
    # Generate task ID
    timestamp = int(datetime.now(timezone.utc).timestamp())
    task_id = f"parse-{supplier.name.lower().replace(' ', '-')}-{timestamp}"
    
    # Determine source type from supplier
    source_type = supplier.source_type
    if source_type not in ("google_sheets", "csv", "excel"):
        # Default to google_sheets for unknown types
        source_type = "google_sheets"
    
    # ML pipeline: download file and trigger ml-analyze
    job_id = str(uuid4())
    
    # Extract original filename from URL or use supplier name
    original_filename = None
    if source_url.startswith(("http://", "https://")):
        url_path = source_url.split("?")[0]  # Remove query params
        original_filename = Path(url_path).name or None
    
    # Default filename if not extractable
    if not original_filename:
        ext = ".xlsx" if source_type == "google_sheets" else f".{source_type}"
        original_filename = f"{supplier.name}_export{ext}"
    
    # Get sheet name for Google Sheets
    sheet_name = meta.get("sheet_name", "Sheet1") if source_type == "google_sheets" else None
    
    await redis.enqueue_job(
        "download_and_trigger_ml",
        task_id=task_id,
        job_id=job_id,
        supplier_id=str(supplier.id),
        supplier_name=supplier.name,
        source_type=source_type,
        source_url=source_url,
        original_filename=original_filename,
        sheet_name=sheet_name,
        use_ml_processing=True,
    )
    
    log.info(
        "ml_download_task_enqueued",
        task_id=task_id,
        job_id=job_id,
        supplier_name=supplier.name,
        source_type=source_type,
        parent_task_id=parent_task_id,
    )
    
    return job_id


async def poll_parse_triggers(
    ctx: Dict[str, Any],
    **kwargs
) -> Optional[Dict[str, Any]]:
    """Poll for parse triggers from Bun API file uploads.
    
    Phase 9: Always uses ML pipeline (download_and_trigger_ml).
    
    This task runs every 10 seconds to check for pending parse triggers
    set by the Bun API when files are uploaded.
    
    Args:
        ctx: Worker context (contains Redis connection)
        
    Returns:
        Dict with results if triggers were processed, else None
    """
    from uuid import uuid4
    
    redis: Optional[ArqRedis] = ctx.get("redis")
    if not redis:
        return None
    
    # Get pending triggers
    triggers = await get_pending_parse_triggers(redis, max_count=10)
    
    if not triggers:
        return None
    
    logger.info(
        "parse_triggers_found",
        count=len(triggers),
    )
    
    results = []
    
    for trigger in triggers:
        task_id = trigger.get("task_id", f"parse-trigger-{int(time.time())}")
        source_type = trigger.get("parser_type", "csv")  # Legacy field name
        supplier_name = trigger.get("supplier_name", "unknown")
        supplier_id = trigger.get("supplier_id")
        source_config = trigger.get("source_config", {})
        
        # Extract source URL from config
        source_url = source_config.get("sheet_url") or source_config.get("file_path")
        
        logger.info(
            "processing_parse_trigger",
            task_id=task_id,
            source_type=source_type,
            supplier_name=supplier_name,
        )
        
        try:
            # Phase 9: Use ML pipeline
            job_id = str(uuid4())
            
            # Determine original filename
            original_filename = source_config.get("original_filename")
            if not original_filename:
                ext = ".xlsx" if source_type == "google_sheets" else f".{source_type}"
                original_filename = f"{supplier_name}_export{ext}"
            
            # Get sheet name for Google Sheets
            sheet_name = source_config.get("sheet_name") if source_type == "google_sheets" else None
            
            await redis.enqueue_job(
                "download_and_trigger_ml",
                task_id=task_id,
                job_id=job_id,
                supplier_id=supplier_id or str(uuid4()),
                supplier_name=supplier_name,
                source_type=source_type,
                source_url=source_url,
                original_filename=original_filename,
                sheet_name=sheet_name,
                use_ml_processing=True,
            )
            
            results.append({
                "task_id": task_id,
                "job_id": job_id,
                "status": "enqueued",
            })
            
        except Exception as e:
            logger.error(
                "parse_trigger_enqueue_failed",
                task_id=task_id,
                error=str(e),
            )
            results.append({
                "task_id": task_id,
                "status": "error",
                "error": str(e),
            })
    
    return {
        "processed": len(results),
        "results": results,
    }

