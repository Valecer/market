"""
ML Job Status Polling Tasks

Polls the ml-analyze service for job status updates and synchronizes
state back to Redis for frontend display.

@see /specs/008-ml-ingestion-integration/plan.md
@see /specs/008-ml-ingestion-integration/tasks.md - T055-T058
"""

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from arq.connections import ArqRedis

from src.config import settings
from src.db.operations import log_parsing_event
from src.services.ml_client import (
    MLClient,
    MLServiceUnavailableError,
    MLClientError,
)
from src.services.job_state import (
    get_recent_jobs,
    update_job_phase,
    update_analysis_progress,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Exponential backoff configuration
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 60
BACKOFF_MULTIPLIER = 2

# Job polling configuration
MAX_CONSECUTIVE_ERRORS = 5
POLL_BATCH_SIZE = 10  # Number of jobs to poll per cycle


# =============================================================================
# Parsing Log Helper
# =============================================================================


# =============================================================================
# Backoff Helper
# =============================================================================


def _calculate_backoff(retry_count: int) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        retry_count: Number of consecutive failures

    Returns:
        Delay in seconds (capped at MAX_BACKOFF_SECONDS)
    """
    delay = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** retry_count)
    return min(delay, MAX_BACKOFF_SECONDS)


# =============================================================================
# Status Sync Helper
# =============================================================================


async def _sync_ml_job_status(
    redis: ArqRedis,
    ml_client: MLClient,
    job: Dict[str, Any],
    log: Any,
) -> bool:
    """
    Sync a single job's status from ML service to Redis.

    Args:
        redis: arq Redis connection
        ml_client: ML service client
        job: Job data from Redis
        log: Logger instance

    Returns:
        True if job was updated, False otherwise
    """
    job_id = job.get("job_id")
    ml_job_id = job.get("ml_job_id")
    current_phase = job.get("phase")

    # Skip jobs without ML job ID or already completed
    if not ml_job_id or not ml_job_id.strip():
        return False

    if current_phase in ("complete", "failed"):
        return False

    try:
        # Get status from ML service
        ml_status = await ml_client.get_job_status(UUID(ml_job_id))

        log.debug(
            "ml_status_retrieved",
            job_id=job_id,
            ml_job_id=ml_job_id,
            ml_status=ml_status.status,
            progress=ml_status.progress_percentage,
        )

        # Map ML status to job phase
        supplier_id = job.get("supplier_id")
        supplier_name = job.get("supplier_name", "Unknown")
        supplier_id_uuid = UUID(supplier_id) if supplier_id else None

        if ml_status.status == "completed":
            await update_job_phase(
                redis=redis,
                job_id=job_id,
                phase="complete",
                status="completed",
            )
            # Update final analysis progress
            await update_analysis_progress(
                redis=redis,
                job_id=job_id,
                items_processed=ml_status.items_processed,
                items_total=ml_status.items_total,
                matches_found=0,  # Will be populated by ML service
                review_queue_count=0,
                error_count=len(ml_status.errors),
            )
            log.info(
                "job_completed_from_ml",
                job_id=job_id,
                items_processed=ml_status.items_processed,
            )
            # Log to parsing_logs for UI visibility
            await log_parsing_event(
                task_id=str(job_id),
                supplier_id=supplier_id_uuid,
                error_type="SUCCESS",
                message=f"ML analysis completed for {supplier_name}: {ml_status.items_processed} items processed",
            )
            return True

        elif ml_status.status == "failed":
            error_msg = "; ".join(ml_status.errors) if ml_status.errors else "ML processing failed"
            await update_job_phase(
                redis=redis,
                job_id=job_id,
                phase="failed",
                status="failed",
                error=error_msg,
                error_details=ml_status.errors,
            )
            log.warning(
                "job_failed_from_ml",
                job_id=job_id,
                errors=ml_status.errors,
            )
            # Log to parsing_logs for UI visibility
            await log_parsing_event(
                task_id=str(job_id),
                supplier_id=supplier_id_uuid,
                error_type="ERROR",
                message=f"ML analysis failed for {supplier_name}: {error_msg}",
            )
            return True

        elif ml_status.status in ("pending", "processing"):
            # Determine phase based on progress
            if ml_status.items_total > 0 and ml_status.items_processed > 0:
                new_phase = "matching"  # Has started processing items
            else:
                new_phase = "analyzing"  # Still in initial analysis

            # Update progress
            await update_analysis_progress(
                redis=redis,
                job_id=job_id,
                items_processed=ml_status.items_processed,
                items_total=ml_status.items_total,
            )

            # Update phase if changed
            if current_phase != new_phase:
                await update_job_phase(
                    redis=redis,
                    job_id=job_id,
                    phase=new_phase,
                    status="processing",
                )
                log.debug(
                    "job_phase_updated",
                    job_id=job_id,
                    old_phase=current_phase,
                    new_phase=new_phase,
                )

            return True

    except MLClientError as e:
        log.warning(
            "ml_status_fetch_failed",
            job_id=job_id,
            ml_job_id=ml_job_id,
            error=str(e),
        )
        return False

    return False


# =============================================================================
# Main Polling Task
# =============================================================================


async def poll_ml_job_status_task(
    ctx: Dict[str, Any],
    **kwargs,
) -> Dict[str, Any]:
    """
    Poll ML service for active job statuses.

    This task runs periodically (registered as cron) to:
    1. Get all active jobs with ML job IDs
    2. Poll ml-analyze for each job's status
    3. Update Redis job state with progress/completion
    4. Handle errors with exponential backoff

    Args:
        ctx: Worker context with Redis connection

    Returns:
        Dict with polling results:
            - jobs_polled: Number of jobs checked
            - jobs_updated: Number of jobs with status changes
            - errors: List of error messages
    """
    redis: Optional[ArqRedis] = ctx.get("redis")
    if not redis:
        logger.error("poll_ml_job_status_no_redis")
        return {"jobs_polled": 0, "jobs_updated": 0, "errors": ["No Redis connection"]}

    log = logger.bind(task="poll_ml_job_status")

    # Track consecutive errors for backoff
    consecutive_errors = ctx.get("_ml_poll_consecutive_errors", 0)

    try:
        # Get active jobs that need polling
        jobs = await get_recent_jobs(
            redis=redis,
            limit=POLL_BATCH_SIZE,
            include_completed=False,
        )

        # Filter to jobs with ML job IDs in active phases
        active_jobs = [
            job for job in jobs
            if job.get("ml_job_id") and job.get("phase") in ("analyzing", "matching", "downloading")
        ]

        if not active_jobs:
            log.debug("no_active_ml_jobs_to_poll")
            return {"jobs_polled": 0, "jobs_updated": 0, "errors": []}

        log.info("polling_ml_jobs", count=len(active_jobs))

        jobs_updated = 0
        errors: List[str] = []

        # Create ML client for batch polling
        async with MLClient() as ml_client:
            # Check health first
            if not await ml_client.check_health():
                # Apply backoff
                backoff = _calculate_backoff(consecutive_errors)
                ctx["_ml_poll_consecutive_errors"] = consecutive_errors + 1

                log.warning(
                    "ml_service_unhealthy_backoff",
                    consecutive_errors=consecutive_errors + 1,
                    backoff_seconds=backoff,
                )

                if consecutive_errors + 1 >= MAX_CONSECUTIVE_ERRORS:
                    # Mark all active jobs as potentially stalled
                    for job in active_jobs:
                        errors.append(f"Job {job.get('job_id')}: ML service unavailable")

                return {
                    "jobs_polled": 0,
                    "jobs_updated": 0,
                    "errors": ["ML service health check failed"],
                }

            # Reset consecutive errors on successful health check
            ctx["_ml_poll_consecutive_errors"] = 0

            # Poll each job
            for job in active_jobs:
                try:
                    updated = await _sync_ml_job_status(
                        redis=redis,
                        ml_client=ml_client,
                        job=job,
                        log=log,
                    )
                    if updated:
                        jobs_updated += 1

                except Exception as e:
                    error_msg = f"Job {job.get('job_id')}: {str(e)}"
                    errors.append(error_msg)
                    log.error(
                        "job_poll_error",
                        job_id=job.get("job_id"),
                        error=str(e),
                    )

        result = {
            "jobs_polled": len(active_jobs),
            "jobs_updated": jobs_updated,
            "errors": errors,
        }

        if jobs_updated > 0:
            log.info("ml_poll_complete", **result)
        else:
            log.debug("ml_poll_complete_no_changes", **result)

        return result

    except MLServiceUnavailableError as e:
        # Apply exponential backoff
        consecutive_errors += 1
        ctx["_ml_poll_consecutive_errors"] = consecutive_errors
        backoff = _calculate_backoff(consecutive_errors)

        log.error(
            "ml_service_unavailable",
            error=str(e),
            consecutive_errors=consecutive_errors,
            backoff_seconds=backoff,
        )

        return {
            "jobs_polled": 0,
            "jobs_updated": 0,
            "errors": [f"ML service unavailable: {e}"],
        }

    except Exception as e:
        log.error(
            "poll_ml_job_status_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "jobs_polled": 0,
            "jobs_updated": 0,
            "errors": [str(e)],
        }


# =============================================================================
# Single Job Polling (For Immediate Status Check)
# =============================================================================


async def check_single_job_status(
    redis: ArqRedis,
    job_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Check and update status for a single job.

    Useful for immediate status checks after triggering ML analysis.

    Args:
        redis: arq Redis connection
        job_id: Job ID to check

    Returns:
        Updated job data, or None if job not found
    """
    from src.services.job_state import get_job

    log = logger.bind(job_id=job_id)

    job = await get_job(redis, job_id)
    if not job:
        log.warning("job_not_found")
        return None

    ml_job_id = job.get("ml_job_id")
    if not ml_job_id:
        log.debug("job_has_no_ml_job_id")
        return job

    try:
        async with MLClient() as ml_client:
            updated = await _sync_ml_job_status(
                redis=redis,
                ml_client=ml_client,
                job=job,
                log=log,
            )

            if updated:
                return await get_job(redis, job_id)

            return job

    except MLClientError as e:
        log.error("single_job_status_check_failed", error=str(e))
        return job

