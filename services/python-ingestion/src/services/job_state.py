"""
Job State Management

Redis-based job state storage for multi-phase ingestion jobs.
Tracks download progress, ML analysis status, and job lifecycle.

@see /specs/008-ml-ingestion-integration/plan/data-model.md
"""

import json
import structlog
from datetime import datetime, timezone
from typing import Optional, Any
from uuid import UUID
from arq.connections import ArqRedis

from src.models.ml_models import JobPhase, JobStatus

logger = structlog.get_logger(__name__)

# =============================================================================
# Redis Key Constants
# =============================================================================

JOB_KEY_PREFIX = "job:"
JOB_LIST_KEY = "jobs:active"
JOB_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


# =============================================================================
# Job Data Structure
# =============================================================================


def _get_job_key(job_id: str | UUID) -> str:
    """Get Redis key for a job."""
    return f"{JOB_KEY_PREFIX}{job_id}"


def _serialize_job_data(data: dict) -> dict:
    """Serialize job data for Redis storage."""
    result = {}
    for key, value in data.items():
        if value is None:
            result[key] = ""  # Redis doesn't store None well
        elif isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, (list, dict)):
            result[key] = json.dumps(value)
        else:
            result[key] = str(value)
    return result


def _deserialize_job_data(data: dict) -> dict:
    """Deserialize job data from Redis."""
    result = {}
    for key, value in data.items():
        if not value or value == "":
            result[key] = None
        elif key.endswith("_at") and value:
            try:
                result[key] = value  # Keep as ISO string
            except Exception:
                result[key] = value
        elif key in ("error_details",) and value:
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = [value] if value else []
        elif key in ("can_retry",) and value:
            result[key] = value.lower() == "true"
        elif key in ("retry_count", "max_retries", "items_processed", "items_total",
                     "download_bytes", "download_total", "matches_found",
                     "review_queue_count", "error_count"):
            try:
                result[key] = int(value)
            except (ValueError, TypeError):
                result[key] = 0
        else:
            result[key] = value
    return result


# =============================================================================
# Job State Functions
# =============================================================================


async def create_job(
    redis: ArqRedis,
    job_id: str | UUID,
    supplier_id: str | UUID,
    supplier_name: str,
    file_type: str = "excel",
    source_url: Optional[str] = None,
) -> dict:
    """
    Create a new ingestion job in Redis.

    Args:
        redis: arq Redis connection
        job_id: Unique job identifier
        supplier_id: Associated supplier UUID
        supplier_name: Supplier name for display
        file_type: Type of file (excel, csv, pdf)
        source_url: Original source URL

    Returns:
        Created job data dictionary
    """
    now = datetime.now(timezone.utc)

    job_data = {
        "job_id": str(job_id),
        "supplier_id": str(supplier_id),
        "supplier_name": supplier_name,
        "phase": "downloading",
        "status": "pending",
        "file_type": file_type,
        "source_url": source_url or "",
        # Download progress
        "download_bytes": 0,
        "download_total": 0,
        # Analysis progress
        "items_processed": 0,
        "items_total": 0,
        "matches_found": 0,
        "review_queue_count": 0,
        "error_count": 0,
        # Error handling
        "error": "",
        "error_details": "[]",
        "can_retry": "true",
        "retry_count": 0,
        "max_retries": 3,
        # ML correlation
        "ml_job_id": "",
        # Timestamps
        "created_at": now.isoformat(),
        "started_at": "",
        "completed_at": "",
    }

    serialized = _serialize_job_data(job_data)

    # Store job data as hash
    await redis.hset(_get_job_key(job_id), mapping=serialized)
    await redis.expire(_get_job_key(job_id), JOB_TTL_SECONDS)

    # Add to active jobs list
    await redis.sadd(JOB_LIST_KEY, str(job_id))

    logger.info(
        "job_created",
        job_id=str(job_id),
        supplier_id=str(supplier_id),
        supplier_name=supplier_name,
    )

    return _deserialize_job_data(job_data)


async def update_job(
    redis: ArqRedis,
    job_id: str | UUID,
    **updates: Any,
) -> Optional[dict]:
    """
    Update an existing job in Redis.

    Args:
        redis: arq Redis connection
        job_id: Job identifier
        **updates: Fields to update

    Returns:
        Updated job data dictionary, or None if job not found
    """
    key = _get_job_key(job_id)

    # Check job exists
    if not await redis.exists(key):
        logger.warning("job_not_found_for_update", job_id=str(job_id))
        return None

    # Serialize updates
    serialized = _serialize_job_data(updates)

    # Update specific fields
    if serialized:
        await redis.hset(key, mapping=serialized)

    # Refresh TTL
    await redis.expire(key, JOB_TTL_SECONDS)

    # Handle completion states
    phase = updates.get("phase")
    if phase in ("complete", "failed"):
        # Remove from active jobs
        await redis.srem(JOB_LIST_KEY, str(job_id))

        # Set completion timestamp if not provided
        if "completed_at" not in updates:
            await redis.hset(
                key,
                "completed_at",
                datetime.now(timezone.utc).isoformat(),
            )

    logger.debug("job_updated", job_id=str(job_id), updates=list(updates.keys()))

    # Return updated job
    return await get_job(redis, job_id)


async def get_job(redis: ArqRedis, job_id: str | UUID) -> Optional[dict]:
    """
    Get job data from Redis.

    Args:
        redis: arq Redis connection
        job_id: Job identifier

    Returns:
        Job data dictionary, or None if not found
    """
    key = _get_job_key(job_id)
    data = await redis.hgetall(key)

    if not data:
        return None

    # Decode bytes to strings if needed
    decoded = {}
    for k, v in data.items():
        k_str = k.decode() if isinstance(k, bytes) else k
        v_str = v.decode() if isinstance(v, bytes) else v
        decoded[k_str] = v_str

    return _deserialize_job_data(decoded)


async def get_recent_jobs(
    redis: ArqRedis,
    limit: int = 20,
    include_completed: bool = True,
) -> list[dict]:
    """
    Get recent jobs from Redis.

    Args:
        redis: arq Redis connection
        limit: Maximum number of jobs to return
        include_completed: Whether to include completed jobs

    Returns:
        List of job data dictionaries, sorted by created_at desc
    """
    jobs = []

    # Get active jobs
    active_ids = await redis.smembers(JOB_LIST_KEY)
    for job_id in active_ids:
        job_id_str = job_id.decode() if isinstance(job_id, bytes) else job_id
        job = await get_job(redis, job_id_str)
        if job:
            jobs.append(job)

    # If including completed, scan for recent job keys
    if include_completed and len(jobs) < limit:
        # Scan for job keys (limited)
        cursor = 0
        scanned_count = 0
        max_scan = limit * 3  # Scan a bit more to find enough

        while scanned_count < max_scan:
            cursor, keys = await redis.scan(
                cursor=cursor,
                match=f"{JOB_KEY_PREFIX}*",
                count=100,
            )
            
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                job_id = key_str.replace(JOB_KEY_PREFIX, "")

                # Skip if already in list
                if any(j.get("job_id") == job_id for j in jobs):
                    continue

                job = await get_job(redis, job_id)
                if job:
                    jobs.append(job)

                if len(jobs) >= limit * 2:  # Get extra for sorting
                    break

            scanned_count += len(keys)
            if cursor == 0:
                break

    # Sort by created_at descending
    def sort_key(job: dict) -> str:
        return job.get("created_at", "") or ""

    jobs.sort(key=sort_key, reverse=True)

    return jobs[:limit]


# =============================================================================
# Phase Update Helpers
# =============================================================================


async def update_job_phase(
    redis: ArqRedis,
    job_id: str | UUID,
    phase: JobPhase,
    status: Optional[JobStatus] = None,
    error: Optional[str] = None,
    error_details: Optional[list[str]] = None,
    **progress_updates: Any,
) -> Optional[dict]:
    """
    Update job phase with optional progress data.

    Convenience function for common phase transitions.

    Args:
        redis: arq Redis connection
        job_id: Job identifier
        phase: New phase
        status: Optional new status
        error: Optional error message
        error_details: Optional list of detailed error messages
        **progress_updates: Additional progress fields

    Returns:
        Updated job data
    """
    updates: dict[str, Any] = {"phase": phase}

    if status:
        updates["status"] = status

    if error:
        updates["error"] = error
        updates["can_retry"] = phase == "failed"

    if error_details:
        updates["error_details"] = error_details

    # Handle phase-specific logic
    if phase == "downloading" and "started_at" not in progress_updates:
        updates["started_at"] = datetime.now(timezone.utc).isoformat()

    if phase in ("complete", "failed"):
        updates["completed_at"] = datetime.now(timezone.utc).isoformat()

    updates.update(progress_updates)

    return await update_job(redis, job_id, **updates)


async def update_download_progress(
    redis: ArqRedis,
    job_id: str | UUID,
    bytes_downloaded: int,
    bytes_total: Optional[int] = None,
) -> Optional[dict]:
    """
    Update download progress for a job.

    Args:
        redis: arq Redis connection
        job_id: Job identifier
        bytes_downloaded: Bytes downloaded so far
        bytes_total: Total bytes (if known)

    Returns:
        Updated job data
    """
    updates = {
        "download_bytes": bytes_downloaded,
    }

    if bytes_total is not None:
        updates["download_total"] = bytes_total

    return await update_job(redis, job_id, **updates)


async def update_analysis_progress(
    redis: ArqRedis,
    job_id: str | UUID,
    items_processed: int,
    items_total: int,
    matches_found: int = 0,
    review_queue_count: int = 0,
    error_count: int = 0,
) -> Optional[dict]:
    """
    Update analysis progress for a job.

    Args:
        redis: arq Redis connection
        job_id: Job identifier
        items_processed: Items processed so far
        items_total: Total items to process
        matches_found: Successful product matches
        review_queue_count: Items added to review queue
        error_count: Processing errors

    Returns:
        Updated job data
    """
    return await update_job(
        redis,
        job_id,
        items_processed=items_processed,
        items_total=items_total,
        matches_found=matches_found,
        review_queue_count=review_queue_count,
        error_count=error_count,
    )


async def set_ml_job_id(
    redis: ArqRedis,
    job_id: str | UUID,
    ml_job_id: str | UUID,
) -> Optional[dict]:
    """
    Associate an ML job ID with an ingestion job.

    Args:
        redis: arq Redis connection
        job_id: Ingestion job identifier
        ml_job_id: ML service job identifier

    Returns:
        Updated job data
    """
    return await update_job(redis, job_id, ml_job_id=str(ml_job_id))

