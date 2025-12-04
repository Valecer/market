"""
Job Service
============

Redis-based job status management for async file analysis tasks.

Provides:
- Job creation and status tracking
- Progress updates with percentage and item counts
- Error logging and status persistence
- Job status retrieval for API endpoints

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
    COMPLETED_WITH_ERRORS = "completed_with_errors"


class JobPhase(str, Enum):
    """
    Job processing phases for semantic ETL pipeline.
    
    Phase 9: Extended phases for extraction workflow.
    """

    PENDING = "pending"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"  # Sheet selection, structure analysis
    EXTRACTING = "extracting"  # LLM product extraction
    NORMALIZING = "normalizing"  # Category matching, deduplication
    COMPLETE = "complete"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class JobType(str, Enum):
    """Job type identifiers."""

    FILE_ANALYSIS = "file_analysis"
    BATCH_MATCH = "batch_match"
    VISION = "vision"


class JobData(BaseModel):
    """
    Job data model stored in Redis.

    Attributes:
        job_id: Unique job identifier
        job_type: Type of job
        status: Current status
        phase: Current processing phase (semantic ETL)
        progress_percentage: Completion percentage
        items_processed: Items processed so far
        items_total: Total items to process
        successful_extractions: Successfully extracted products (semantic ETL)
        failed_extractions: Failed extractions (semantic ETL)
        duplicates_removed: Duplicates removed (semantic ETL)
        errors: List of error messages
        retry_count: Number of retry attempts (T84)
        max_retries: Maximum allowed retries (T84)
        file_url: Source file URL (for file analysis jobs)
        supplier_id: Supplier ID
        created_at: Job creation time
        started_at: Processing start time
        completed_at: Completion time
        metadata: Additional job-specific data
    """

    job_id: UUID
    job_type: JobType
    status: JobStatus = JobStatus.PENDING
    phase: JobPhase = JobPhase.PENDING
    progress_percentage: int = Field(default=0, ge=0, le=100)
    items_processed: int = Field(default=0, ge=0)
    items_total: int = Field(default=0, ge=0)
    # Semantic ETL metrics (Phase 9)
    successful_extractions: int = Field(default=0, ge=0)
    failed_extractions: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    # T84: Retry tracking
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    file_url: str | None = None
    file_type: str | None = None
    supplier_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

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
    ) -> JobUpdateResult:
        """
        Mark job as completed.

        Args:
            job_id: Job UUID
            items_processed: Final processed count

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
        )

        return JobUpdateResult(
            success=True,
            job_id=job_id,
            message="Job completed successfully",
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

    async def update_job_status(
        self,
        job_id: str,
        phase: str,
        progress_percent: int,
        total_rows: int | None = None,
        successful_extractions: int | None = None,
        failed_extractions: int | None = None,
        duplicates_removed: int | None = None,
        error_message: str | None = None,
    ) -> JobUpdateResult:
        """
        Update job status for semantic ETL pipeline.
        
        Phase 9: Extended status tracking for extraction workflow.
        
        Args:
            job_id: Job identifier (string or UUID)
            phase: Current phase name
            progress_percent: Progress percentage (0-100)
            total_rows: Total rows processed
            successful_extractions: Successful product count
            failed_extractions: Failed extraction count
            duplicates_removed: Duplicate count removed
            error_message: Error message if failed
        
        Returns:
            JobUpdateResult
        """
        # Convert string job_id to UUID if needed
        if isinstance(job_id, str):
            try:
                job_uuid = UUID(job_id)
            except ValueError:
                return JobUpdateResult(
                    success=False,
                    job_id=UUID("00000000-0000-0000-0000-000000000000"),
                    error=f"Invalid job_id format: {job_id}",
                )
        else:
            job_uuid = job_id
        
        job = await self.get_job(job_uuid)
        if not job:
            return JobUpdateResult(
                success=False,
                job_id=job_uuid,
                error="Job not found",
            )
        
        # Update phase
        try:
            job.phase = JobPhase(phase)
        except ValueError:
            logger.warning(f"Unknown phase: {phase}, using as-is in metadata")
            job.metadata["phase"] = phase
        
        # Update progress
        job.progress_percentage = min(100, max(0, progress_percent))
        
        # Update semantic ETL metrics
        if total_rows is not None:
            job.items_total = total_rows
        if successful_extractions is not None:
            job.successful_extractions = successful_extractions
            job.items_processed = successful_extractions
        if failed_extractions is not None:
            job.failed_extractions = failed_extractions
        if duplicates_removed is not None:
            job.duplicates_removed = duplicates_removed
        
        # Update status based on phase
        if phase in ("complete", "success"):
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
        elif phase == "completed_with_errors":
            job.status = JobStatus.COMPLETED_WITH_ERRORS
            job.completed_at = datetime.now(timezone.utc)
        elif phase == "failed":
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            if error_message:
                job.errors.append(error_message)
        elif phase in ("analyzing", "extracting", "normalizing", "downloading"):
            job.status = JobStatus.PROCESSING
            if not job.started_at:
                job.started_at = datetime.now(timezone.utc)
        
        # Add error message if provided
        if error_message and phase == "failed":
            # Already handled above
            pass
        
        # Save back to Redis
        key = self._job_key(job_uuid)
        await self._redis.setex(key, JOB_TTL_SECONDS, job.to_json())
        
        logger.debug(
            "Job status updated (semantic ETL)",
            job_id=str(job_uuid),
            phase=phase,
            progress=progress_percent,
            successful_extractions=successful_extractions,
        )
        
        return JobUpdateResult(
            success=True,
            job_id=job_uuid,
            message=f"Phase: {phase}, Progress: {progress_percent}%",
        )


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

