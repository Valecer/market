"""
Status Routes
==============

API endpoints for job status tracking.

Endpoints:
- GET /status/{job_id} - Get job status and progress

Provides real-time job progress from Redis.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.schemas.responses import JobStatusResponse
from src.services.job_service import JobService, get_job_service
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description=(
        "Retrieve the current status and progress of an analysis job. "
        "Returns progress percentage, items processed, and any errors encountered."
    ),
    responses={
        200: {"description": "Job status retrieved successfully"},
        404: {"description": "Job not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_job_status(
    job_id: UUID,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobStatusResponse:
    """
    Get job status by ID.

    Retrieves job data from Redis and returns current state,
    progress, and any errors.

    Args:
        job_id: UUID of the job to check
        job_service: Job service dependency

    Returns:
        JobStatusResponse with full job details

    Raises:
        HTTPException: 404 if job not found, 500 on server error
    """
    logger.debug("Job status requested", job_id=str(job_id))

    try:
        job = await job_service.get_job(job_id)

        if not job:
            logger.warning("Job not found", job_id=str(job_id))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found. It may have expired or never existed.",
            )

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status.value,
            progress_percentage=job.progress_percentage,
            items_processed=job.items_processed,
            items_total=job.items_total,
            errors=job.errors,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error retrieving job status", job_id=str(job_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}",
        ) from e


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete job",
    description="Delete a job record from the system. This does not cancel running jobs.",
    responses={
        204: {"description": "Job deleted successfully"},
        404: {"description": "Job not found"},
    },
)
async def delete_job(
    job_id: UUID,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> None:
    """
    Delete a job record.

    Removes the job from Redis. Does not cancel running background tasks.

    Args:
        job_id: UUID of the job to delete
        job_service: Job service dependency

    Raises:
        HTTPException: 404 if job not found
    """
    logger.info("Job deletion requested", job_id=str(job_id))

    deleted = await job_service.delete_job(job_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    logger.info("Job deleted", job_id=str(job_id))

