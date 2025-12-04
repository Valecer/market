"""
Job Service
============

Redis-based job status management for async file analysis tasks.

Provides:
- Job creation and status tracking
- Progress updates with percentage and item counts
- Error logging and status persistence
- Job status retrieval for API endpoints
- Parsing metrics storage and retrieval (Phase 10)

Follows:
- Single Responsibility: Only handles job status management
- DRY: Centralizes job key patterns and serialization
- Strong Typing: Full Pydantic validation
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from pydantic import BaseModel, Field

from src.config.settings import Settings, get_settings
from src.schemas.domain import ParsingMetrics
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Redis key patterns
JOB_PREFIX = "ml-analyze:job:"
JOB_TTL_SECONDS = 86400 * 7  # 7 days


class JobStatus(str, Enum):
    """Job processing states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Job type identifiers."""

    FILE_ANALYSIS = "file_analysis"
    BATCH_MATCH = "batch_match"
    VISION = "vision"


class JobData(BaseModel):
    """
    Job data model stored in Redis.

    Phase 10: Added metrics field for parsing quality metrics.

    Attributes:
        job_id: Unique job identifier
        job_type: Type of job
        status: Current status
        progress_percentage: Completion percentage
        items_processed: Items processed so far
        items_total: Total items to process
        errors: List of error messages
        file_url: Source file URL (for file analysis jobs)
        supplier_id: Supplier ID
        created_at: Job creation time
        started_at: Processing start time
        completed_at: Completion time
        metadata: Additional job-specific data
        metrics: Parsing quality metrics (populated when job completes)
    """

    job_id: UUID
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    progress_percentage: int = Field(default=0, ge=0, le=100)
    items_processed: int = Field(default=0, ge=0)
    items_total: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    file_url: str | None = None
    file_type: str | None = None
    supplier_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: ParsingMetrics | None = Field(default=None, description="Parsing quality metrics")

    def to_json(self) -> str:
        """Serialize to JSON string for Redis storage."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "JobData":
        """Deserialize from JSON string."""
        return cls.model_validate_json(data)


@dataclass
class JobUpdateResult:
    """Result of a job update operation."""

    success: bool
    job_id: UUID
    message: str = ""
    error: str | None = None


class JobService:
    """
    Service for managing job status in Redis.

    Provides async methods for:
    - Creating new jobs
    - Updating job progress
    - Retrieving job status
    - Marking jobs as complete/failed

    Usage:
        async with job_service_factory() as service:
            job_id = await service.create_job(
                job_type=JobType.FILE_ANALYSIS,
                file_url="/path/to/file.xlsx",
                supplier_id=uuid,
            )

            # Update progress
            await service.update_progress(job_id, items_processed=50, items_total=100)

            # Get status
            job = await service.get_job(job_id)
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize JobService.

        Args:
            redis_client: Async Redis client instance
            settings: Application settings
        """
        self._redis = redis_client
        self._settings = settings or get_settings()
        logger.debug("JobService initialized")

    @staticmethod
    def _job_key(job_id: UUID) -> str:
        """Generate Redis key for a job."""
        return f"{JOB_PREFIX}{job_id}"

    async def create_job(
        self,
        job_type: JobType,
        supplier_id: UUID | None = None,
        file_url: str | None = None,
        file_type: str | None = None,
        items_total: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """
        Create a new job and store in Redis.

        Args:
            job_type: Type of job
            supplier_id: Supplier ID
            file_url: Source file URL
            file_type: File type (pdf, excel, csv)
            items_total: Expected total items
            metadata: Additional metadata

        Returns:
            UUID of created job
        """
        job_id = uuid4()

        job_data = JobData(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            supplier_id=supplier_id,
            file_url=file_url,
            file_type=file_type,
            items_total=items_total,
            metadata=metadata or {},
        )

        key = self._job_key(job_id)
        await self._redis.setex(
            key,
            JOB_TTL_SECONDS,
            job_data.to_json(),
        )

        logger.info(
            "Job created",
            job_id=str(job_id),
            job_type=job_type.value,
            supplier_id=str(supplier_id) if supplier_id else None,
        )

        return job_id

    async def get_job(self, job_id: UUID) -> JobData | None:
        """
        Retrieve job data from Redis.

        Args:
            job_id: Job UUID

        Returns:
            JobData if found, None otherwise
        """
        key = self._job_key(job_id)
        data = await self._redis.get(key)

        if not data:
            logger.debug("Job not found", job_id=str(job_id))
            return None

        return JobData.from_json(data)

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        error: str | None = None,
    ) -> JobUpdateResult:
        """
        Update job status.

        Args:
            job_id: Job UUID
            status: New status
            error: Error message (for failed status)

        Returns:
            JobUpdateResult
        """
        job = await self.get_job(job_id)
        if not job:
            return JobUpdateResult(
                success=False,
                job_id=job_id,
                error="Job not found",
            )

        job.status = status

        # Set timestamps
        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now(timezone.utc)
            if status == JobStatus.COMPLETED:
                job.progress_percentage = 100

        # Add error if provided
        if error:
            job.errors.append(error)

        # Save back to Redis
        key = self._job_key(job_id)
        await self._redis.setex(key, JOB_TTL_SECONDS, job.to_json())

        logger.info(
            "Job status updated",
            job_id=str(job_id),
            status=status.value,
            has_error=error is not None,
        )

        return JobUpdateResult(
            success=True,
            job_id=job_id,
            message=f"Status updated to {status.value}",
        )

    async def update_progress(
        self,
        job_id: UUID,
        items_processed: int,
        items_total: int | None = None,
        errors: list[str] | None = None,
    ) -> JobUpdateResult:
        """
        Update job progress.

        Args:
            job_id: Job UUID
            items_processed: Number of items processed
            items_total: Total items (updates if provided)
            errors: New errors to append

        Returns:
            JobUpdateResult
        """
        job = await self.get_job(job_id)
        if not job:
            return JobUpdateResult(
                success=False,
                job_id=job_id,
                error="Job not found",
            )

        job.items_processed = items_processed
        if items_total is not None:
            job.items_total = items_total

        # Calculate percentage
        if job.items_total > 0:
            job.progress_percentage = min(
                100,
                int((items_processed / job.items_total) * 100),
            )

        # Append errors
        if errors:
            job.errors.extend(errors)

        # Save back to Redis
        key = self._job_key(job_id)
        await self._redis.setex(key, JOB_TTL_SECONDS, job.to_json())

        logger.debug(
            "Job progress updated",
            job_id=str(job_id),
            progress=job.progress_percentage,
            items_processed=items_processed,
            items_total=job.items_total,
        )

        return JobUpdateResult(
            success=True,
            job_id=job_id,
            message=f"Progress: {job.progress_percentage}%",
        )

    async def mark_started(self, job_id: UUID) -> JobUpdateResult:
        """
        Mark job as started (processing).

        Args:
            job_id: Job UUID

        Returns:
            JobUpdateResult
        """
        return await self.update_status(job_id, JobStatus.PROCESSING)

    async def mark_completed(
        self,
        job_id: UUID,
        items_processed: int | None = None,
        metrics: ParsingMetrics | None = None,
    ) -> JobUpdateResult:
        """
        Mark job as completed.

        Phase 10: Added metrics parameter for parsing quality metrics.

        Args:
            job_id: Job UUID
            items_processed: Final processed count
            metrics: Parsing quality metrics (Phase 10)

        Returns:
            JobUpdateResult
        """
        job = await self.get_job(job_id)
        if not job:
            return JobUpdateResult(
                success=False,
                job_id=job_id,
                error="Job not found",
            )

        if items_processed is not None:
            job.items_processed = items_processed

        if metrics is not None:
            job.metrics = metrics

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.progress_percentage = 100

        key = self._job_key(job_id)
        await self._redis.setex(key, JOB_TTL_SECONDS, job.to_json())

        logger.info(
            "Job completed",
            job_id=str(job_id),
            items_processed=job.items_processed,
            items_total=job.items_total,
            has_metrics=metrics is not None,
        )

        return JobUpdateResult(
            success=True,
            job_id=job_id,
            message="Job completed successfully",
        )

    async def update_metrics(
        self,
        job_id: UUID,
        metrics: ParsingMetrics,
    ) -> JobUpdateResult:
        """
        Update job with parsing metrics.

        Phase 10: New method for updating parsing quality metrics.

        Args:
            job_id: Job UUID
            metrics: Parsing quality metrics

        Returns:
            JobUpdateResult
        """
        job = await self.get_job(job_id)
        if not job:
            return JobUpdateResult(
                success=False,
                job_id=job_id,
                error="Job not found",
            )

        job.metrics = metrics

        key = self._job_key(job_id)
        await self._redis.setex(key, JOB_TTL_SECONDS, job.to_json())

        logger.info(
            "Job metrics updated",
            job_id=str(job_id),
            total_rows=metrics.total_rows,
            parsed_rows=metrics.parsed_rows,
            success_rate=f"{metrics.success_rate:.2%}",
        )

        return JobUpdateResult(
            success=True,
            job_id=job_id,
            message="Metrics updated successfully",
        )

    async def mark_failed(
        self,
        job_id: UUID,
        error: str,
    ) -> JobUpdateResult:
        """
        Mark job as failed.

        Args:
            job_id: Job UUID
            error: Error message

        Returns:
            JobUpdateResult
        """
        return await self.update_status(job_id, JobStatus.FAILED, error=error)

    async def delete_job(self, job_id: UUID) -> bool:
        """
        Delete a job from Redis.

        Args:
            job_id: Job UUID

        Returns:
            True if deleted, False if not found
        """
        key = self._job_key(job_id)
        result = await self._redis.delete(key)
        return result > 0


# Global Redis client (initialized in lifespan)
_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """
    Get or create Redis client.

    Returns:
        Async Redis client
    """
    global _redis_client

    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    return _redis_client


async def get_job_service() -> JobService:
    """
    Get JobService instance.

    Factory function for dependency injection.

    Returns:
        JobService instance
    """
    redis = await get_redis_client()
    return JobService(redis)


async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None

