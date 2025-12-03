"""
Retry Tasks for Failed ML Ingestion Jobs

Task functions for retrying failed ingestion jobs.
Implements retry logic with max retry validation and file reuse.

@see /specs/008-ml-ingestion-integration/spec.md - User Story 3
"""

import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from arq.connections import ArqRedis

from src.config import settings
from src.db.operations import log_parsing_event
from src.services.job_state import (
    get_job,
    update_job,
    update_job_phase,
)
from src.services.sync_state import get_pending_retry_triggers
from src.tasks.download_tasks import download_and_trigger_ml

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

SHARED_UPLOADS_DIR = Path("/shared/uploads")
MAX_RETRIES = 3


# =============================================================================
# Helper Functions
# =============================================================================


def _find_existing_file(job_id: str) -> Optional[Path]:
    """
    Find existing file in shared uploads directory.

    Searches for files matching the job_id prefix.

    Args:
        job_id: Job identifier

    Returns:
        Path to existing file if found, None otherwise
    """
    try:
        for path in SHARED_UPLOADS_DIR.glob(f"{job_id}_*"):
            # Skip metadata sidecar files
            if path.suffix == ".json" or ".meta.json" in str(path):
                continue
            if path.is_file():
                logger.debug("existing_file_found", path=str(path))
                return path
    except Exception as e:
        logger.warning("file_search_failed", job_id=job_id, error=str(e))
    
    return None


# =============================================================================
# Main Task Function
# =============================================================================


async def retry_job_task(
    ctx: dict[str, Any],
    job_id: str,
) -> dict[str, Any]:
    """
    Retry a failed ingestion job.

    Validates retry count, reuses existing file if available,
    or re-downloads the file and triggers ML analysis.

    Args:
        ctx: Worker context with Redis connection
        job_id: Job ID to retry

    Returns:
        Dict with retry results:
            - job_id: Job identifier
            - status: success/error
            - retry_count: Current retry count
            - message: Result message
    """
    redis = ctx.get("redis")
    log = logger.bind(job_id=job_id)

    log.info("retry_job_started")

    try:
        # Get job from Redis
        job = await get_job(redis, job_id)

        if not job:
            log.error("job_not_found")
            return {
                "job_id": job_id,
                "status": "error",
                "message": "Job not found",
            }

        # Validate job is in failed state
        if job.get("phase") != "failed":
            log.warning(
                "job_not_in_failed_state",
                current_phase=job.get("phase"),
            )
            return {
                "job_id": job_id,
                "status": "error",
                "message": f"Job is not in failed state (current: {job.get('phase')})",
            }

        # Check retry count
        retry_count = int(job.get("retry_count", 0))
        max_retries = int(job.get("max_retries", MAX_RETRIES))

        if retry_count >= max_retries:
            log.error(
                "max_retries_exceeded",
                retry_count=retry_count,
                max_retries=max_retries,
            )
            return {
                "job_id": job_id,
                "status": "error",
                "retry_count": retry_count,
                "message": f"Maximum retries ({max_retries}) exceeded",
            }

        # Increment retry count
        new_retry_count = retry_count + 1

        # Update job state to indicate retry in progress
        await update_job(
            redis,
            job_id,
            retry_count=new_retry_count,
            phase="downloading",
            status="pending",
            error="",
            error_details=[],
            can_retry=True,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at="",
        )

        # Extract job parameters
        supplier_id = job.get("supplier_id", "")
        supplier_name = job.get("supplier_name", "Unknown")
        source_url = job.get("source_url", "")
        file_type = job.get("file_type", "excel")

        # Generate task ID for retry
        task_id = f"retry-{job_id}-{int(datetime.now(timezone.utc).timestamp())}"

        log.info(
            "retry_starting",
            retry_count=new_retry_count,
            max_retries=max_retries,
            supplier_name=supplier_name,
        )

        # Log retry event
        await log_parsing_event(
            task_id=task_id,
            supplier_id=UUID(supplier_id) if supplier_id else None,
            error_type="INFO",
            message=f"Retrying job for {supplier_name} (attempt {new_retry_count}/{max_retries})",
        )

        # Check if existing file is available
        existing_file = _find_existing_file(job_id)

        if existing_file and existing_file.exists():
            log.info(
                "reusing_existing_file",
                file_path=str(existing_file),
            )
            
            # Log file reuse
            await log_parsing_event(
                task_id=task_id,
                supplier_id=UUID(supplier_id) if supplier_id else None,
                error_type="INFO",
                message=f"Reusing existing file: {existing_file.name}",
            )

            # Skip download, go directly to ML trigger
            # We still call download_and_trigger_ml but it should detect the file exists
            # and skip the download phase
            
        # Call download_and_trigger_ml which will handle the rest
        # It will detect if file exists and skip download if so
        result = await download_and_trigger_ml(
            ctx=ctx,
            task_id=task_id,
            job_id=job_id,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            source_type="excel",  # Default, will be detected from URL
            source_url=source_url,
            original_filename=None,  # Will be derived from URL
            sheet_name=None,
            use_ml_processing=True,
            max_file_size_mb=50,
        )

        if result.get("status") == "success":
            log.info(
                "retry_successful",
                retry_count=new_retry_count,
                ml_job_id=result.get("ml_job_id"),
            )
            
            await log_parsing_event(
                task_id=task_id,
                supplier_id=UUID(supplier_id) if supplier_id else None,
                error_type="SUCCESS",
                message=f"Retry successful for {supplier_name}",
            )

            return {
                "job_id": job_id,
                "status": "success",
                "retry_count": new_retry_count,
                "message": f"Retry successful (attempt {new_retry_count})",
                "ml_job_id": result.get("ml_job_id"),
            }
        else:
            error_msg = result.get("error", "Unknown error")
            log.error(
                "retry_failed",
                retry_count=new_retry_count,
                error=error_msg,
            )

            # Update can_retry based on remaining retries
            can_retry = new_retry_count < max_retries

            await update_job_phase(
                redis,
                job_id,
                phase="failed",
                status="failed",
                error=error_msg,
                can_retry=can_retry,
            )

            await log_parsing_event(
                task_id=task_id,
                supplier_id=UUID(supplier_id) if supplier_id else None,
                error_type="ERROR",
                message=f"Retry failed for {supplier_name}: {error_msg}",
            )

            return {
                "job_id": job_id,
                "status": "error",
                "retry_count": new_retry_count,
                "message": f"Retry failed: {error_msg}",
                "can_retry": can_retry,
            }

    except Exception as e:
        log.error(
            "retry_task_error",
            error=str(e),
            error_type=type(e).__name__,
        )

        # Try to update job state to failed
        if redis:
            try:
                await update_job_phase(
                    redis,
                    job_id,
                    phase="failed",
                    status="failed",
                    error=str(e),
                    error_details=[f"{type(e).__name__}: {e}"],
                )
            except Exception:
                pass

        return {
            "job_id": job_id,
            "status": "error",
            "message": f"Retry error: {type(e).__name__}: {e}",
        }


# =============================================================================
# Cron Task: Poll for Retry Triggers
# =============================================================================


async def poll_retry_triggers(
    ctx: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Poll for retry triggers from Bun API.

    This cron task runs periodically to check for pending retry triggers
    set by the Bun API when a user requests to retry a failed job.

    Args:
        ctx: Worker context (contains Redis connection)

    Returns:
        Dict with results if triggers were processed, else None
    """
    redis: Optional[ArqRedis] = ctx.get("redis")
    if not redis:
        logger.error("poll_retry_triggers_no_redis")
        return None

    try:
        triggers = await get_pending_retry_triggers(redis, max_count=10)

        if not triggers:
            return None

        logger.info(
            "retry_triggers_found",
            count=len(triggers),
        )

        results = []
        for trigger in triggers:
            job_id = trigger.get("job_id")
            if not job_id:
                logger.warning("retry_trigger_missing_job_id", trigger=trigger)
                results.append({
                    "status": "error",
                    "error": "Missing job_id in trigger",
                })
                continue

            try:
                # Enqueue the retry task
                await redis.enqueue_job(
                    "retry_job_task",
                    job_id,
                )
                results.append({
                    "job_id": job_id,
                    "status": "enqueued",
                })
                logger.info("retry_job_enqueued", job_id=job_id)
            except Exception as e:
                logger.error(
                    "failed_to_enqueue_retry_job",
                    job_id=job_id,
                    error=str(e),
                )
                results.append({
                    "job_id": job_id,
                    "status": "error",
                    "error": str(e),
                })

        return {"processed_triggers": results}

    except Exception as e:
        logger.error(
            "poll_retry_triggers_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return None

