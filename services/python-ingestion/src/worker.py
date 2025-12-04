"""arq worker configuration for processing tasks.

Phase 9: Semantic ETL - python-ingestion acts as courier only.
All parsing/extraction handled by ml-analyze service.

This module configures the arq worker with:
    - download_and_trigger_ml: Download files and trigger ML processing
    - poll_ml_job_status_task: Poll ML job status from ml-analyze
    - cleanup_shared_files_task: Clean up old shared files
    - match_items_task: Product matching pipeline
    - recalc_product_aggregates_task: Aggregate recalculation
    - enrich_item_task: Feature extraction and enrichment
    - handle_manual_match_event: Manual link/unlink operations
    - expire_review_queue_task: Cron job to expire old review items
"""
from arq.connections import RedisSettings, ArqRedis
from arq import cron
from typing import Dict, Any
import structlog
from src.config import settings, configure_logging

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
# Import ML integration tasks (Phase 8/9)
from src.tasks.download_tasks import download_and_trigger_ml
from src.tasks.ml_polling_tasks import poll_ml_job_status_task
from src.tasks.cleanup_tasks import cleanup_shared_files_task
from src.tasks.retry_tasks import retry_job_task, poll_retry_triggers

# Configure logging
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


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
    
    Phase 9: Courier pattern - no local parsing.
    
    Registered Tasks:
        - download_and_trigger_ml: Download files and trigger ML analysis
        - poll_ml_job_status_task: Poll ML job status
        - cleanup_shared_files_task: Clean up old shared files
        - match_items_task: Match supplier items to products
        - recalc_product_aggregates_task: Recalculate product min_price/availability
        - enrich_item_task: Extract features from item names
        - handle_manual_match_event: Process manual link/unlink events
        - expire_review_queue_task: Expire old review queue items (cron)
        
    Cron Jobs:
        - monitor_queue_depth: Every 5 minutes
        - expire_review_queue_task: Daily at midnight
        - poll_ml_job_status_task: Every 10 seconds
        - cleanup_shared_files_task: Every 6 hours
    """
    
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.queue_name  # Match the queue name used by Bun API
    max_jobs = settings.max_workers
    job_timeout = settings.job_timeout
    keep_result = 3600  # Keep results for 1 hour
    max_tries = 3  # Maximum retry attempts
    
    # Register all worker functions
    functions = [
        # Phase 8/9: ML integration pipeline (courier pattern)
        download_and_trigger_ml,
        poll_ml_job_status_task,
        cleanup_shared_files_task,
        retry_job_task,
        # Phase 4: Matching pipeline
        match_items_task,
        recalc_product_aggregates_task,
        enrich_item_task,
        handle_manual_match_event,
        expire_review_queue_task,
        # Phase 6: Master sync pipeline
        trigger_master_sync_task,
        scheduled_sync_task,
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
        # Bun API sets parse:triggers list, worker polls and enqueues download_and_trigger_ml
        cron(
            poll_parse_triggers,
            second={0, 10, 20, 30, 40, 50},  # Every 10 seconds
            unique=True,
        ),
        # Phase 8/9: Poll ML job status every 10 seconds
        # Syncs job progress from ml-analyze to Redis
        cron(
            poll_ml_job_status_task,
            second={5, 15, 25, 35, 45, 55},  # Every 10 seconds, offset from parse triggers
            unique=True,
        ),
        # Phase 8/9: Cleanup shared files every 6 hours
        # Removes files older than FILE_CLEANUP_TTL_HOURS (default 24)
        cron(
            cleanup_shared_files_task,
            hour={0, 6, 12, 18},  # Every 6 hours
            minute=30,  # Offset from other hourly tasks
            unique=True,
        ),
        # Phase 8/9: Poll for retry triggers every 10 seconds
        # Bun API sets retry:triggers list, worker polls and enqueues retry_job_task
        cron(
            poll_retry_triggers,
            second={2, 12, 22, 32, 42, 52},  # Every 10 seconds, offset from other tasks
            unique=True,
        ),
    ]
