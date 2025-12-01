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

from arq.connections import ArqRedis
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import settings
from src.db.base import async_session_maker
from src.db.models import Supplier
from src.services.master_sheet_ingestor import MasterSheetIngestor
from src.services.sync_state import (
    acquire_sync_lock,
    release_sync_lock,
    set_sync_started,
    set_sync_processing_suppliers,
    set_sync_idle,
    update_sync_progress,
    record_sync_completion,
)
from src.models.sync_messages import TriggerMasterSyncMessage
from src.models.master_sheet_config import MasterSyncResult
from src.errors.exceptions import ParserError

logger = structlog.get_logger(__name__)


def get_sync_interval_hours() -> int:
    """Get sync interval from environment variable.
    
    Returns:
        Sync interval in hours (default: 8)
    """
    return int(os.getenv("SYNC_INTERVAL_HOURS", "8"))


def get_master_sheet_url() -> Optional[str]:
    """Get Master Sheet URL from environment variable.
    
    Returns:
        Master Sheet URL or None if not configured
    """
    return os.getenv("MASTER_SHEET_URL")


@dataclass
class SyncMetrics:
    """Metrics collected during sync task execution."""
    master_sheet_parsed: bool = False
    suppliers_created: int = 0
    suppliers_updated: int = 0
    suppliers_deactivated: int = 0
    suppliers_skipped: int = 0
    parse_tasks_enqueued: int = 0
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
    
    # Resolve Master Sheet URL
    sheet_url = master_sheet_url or get_master_sheet_url()
    if not sheet_url:
        log.error("no_master_sheet_url")
        return {
            "task_id": task_id,
            "status": "error",
            "error": "MASTER_SHEET_URL not configured",
            **metrics.to_dict(),
        }
    
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
            # Step 2: Update status to syncing_master
            await set_sync_started(redis, task_id)
            
            # Step 3: Parse Master Sheet
            log.info("parsing_master_sheet", sheet_url=sheet_url)
            ingestor = MasterSheetIngestor()
            
            try:
                configs = await ingestor.ingest(
                    master_sheet_url=sheet_url,
                    sheet_name="Suppliers",
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
                    await _enqueue_supplier_parse(
                        redis=redis,
                        supplier=supplier,
                        parent_task_id=task_id,
                        log=log,
                    )
                    metrics.parse_tasks_enqueued += 1
                    
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
) -> None:
    """Enqueue a parse task for a supplier.
    
    Args:
        redis: ArqRedis connection
        supplier: Supplier model with configuration
        parent_task_id: Parent sync task ID for correlation
        log: Logger instance
    """
    meta = supplier.meta or {}
    source_url = meta.get("source_url")
    
    if not source_url:
        raise ValueError(f"Supplier {supplier.name} has no source_url configured")
    
    # Generate task ID
    timestamp = int(datetime.now(timezone.utc).timestamp())
    task_id = f"parse-{supplier.name.lower().replace(' ', '-')}-{timestamp}"
    
    # Determine parser type from source_type
    parser_type = supplier.source_type
    if parser_type not in ("google_sheets", "csv", "excel"):
        # Default to google_sheets for unknown types
        parser_type = "google_sheets"
    
    # Build source config based on parser type
    source_config: Dict[str, Any] = {
        "sheet_url": source_url,
    }
    
    if parser_type == "google_sheets":
        # Use default settings for Google Sheets
        source_config.update({
            "sheet_name": "Sheet1",
            "header_row": 1,
            "data_start_row": 2,
        })
    
    # Enqueue parse_task
    await redis.enqueue_job(
        "parse_task",
        task_id=task_id,
        parser_type=parser_type,
        supplier_name=supplier.name,
        source_config=source_config,
    )
    
    log.debug(
        "parse_task_enqueued",
        task_id=task_id,
        supplier_name=supplier.name,
        parser_type=parser_type,
        parent_task_id=parent_task_id,
    )

