"""
Analyze Routes
===============

API endpoints for file analysis and batch matching.

Endpoints:
- POST /analyze/file - Trigger file analysis job
- POST /analyze/merge - Trigger batch matching job
- POST /analyze/vision - Vision analysis stub (501)

All endpoints return job IDs for async status tracking.

Phase 10 Updates:
- /analyze/file now accepts file_path parameter for shared volume access
- Path traversal prevention via secure file reader
- New parameters: default_currency, composite_delimiter
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from src.schemas.requests import (
    BatchMatchRequest,
    FileAnalysisRequest,
    VisionAnalysisRequest,
)
from src.schemas.responses import (
    BatchMatchResponse,
    FileAnalysisResponse,
    VisionAnalysisResponse,
)
from src.services.job_service import (
    JobService,
    JobType,
    get_job_service,
)
from src.utils.errors import (
    FileNotFoundError as MLFileNotFoundError,
    FileSizeError,
    SecurityError,
)
from src.utils.file_reader import validate_and_read_file
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/file",
    response_model=FileAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger file analysis",
    description=(
        "Submit a file for analysis. The file will be parsed, items extracted, "
        "embeddings generated, and products matched asynchronously. "
        "Returns a job_id for tracking progress via GET /analyze/status/{job_id}.\n\n"
        "**Preferred:** Use `file_path` for files already in shared volume.\n"
        "**Deprecated:** `file_url` still supported for backward compatibility."
    ),
    responses={
        202: {"description": "Job accepted and enqueued"},
        400: {"description": "Invalid request - validation error or path traversal"},
        404: {"description": "File not found at specified path"},
        413: {"description": "File exceeds maximum size limit"},
        500: {"description": "Internal server error"},
    },
)
async def analyze_file(
    request: FileAnalysisRequest,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> FileAnalysisResponse:
    """
    Trigger file analysis job.

    Validates the request, performs security checks on file_path (if provided),
    creates a job in Redis, and enqueues the file processing task for
    background execution.

    Phase 10 Updates:
    - Accepts file_path for shared volume access (preferred)
    - Path traversal prevention for file_path parameter
    - New parameters: default_currency, composite_delimiter

    Args:
        request: File analysis request with file_path/file_url, supplier_id, file_type
        job_service: Job service dependency

    Returns:
        FileAnalysisResponse with job_id for status tracking

    Raises:
        HTTPException: 400 on validation/security errors, 404 file not found, 413 file too large
    """
    # Determine file source (prefer file_path over file_url)
    file_source = request.effective_file_source
    is_local_path = request.file_path is not None

    logger.info(
        "File analysis requested",
        file_source=file_source,
        is_local_path=is_local_path,
        supplier_id=str(request.supplier_id),
        file_type=request.file_type,
        default_currency=request.default_currency,
        composite_delimiter=request.composite_delimiter,
    )

    # Phase 10: Validate file_path if provided (security check)
    validated_file_size: int | None = None
    if is_local_path:
        try:
            validated_path, validated_file_size = validate_and_read_file(
                file_path=request.file_path,  # type: ignore[arg-type]
            )
            logger.info(
                "File path validated",
                file_path=str(validated_path),
                file_size_bytes=validated_file_size,
            )
        except SecurityError as e:
            logger.warning(
                "Security error: path traversal blocked",
                file_path=request.file_path,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "SecurityError",
                    "message": e.message,
                },
            ) from e
        except MLFileNotFoundError as e:
            logger.warning(
                "File not found",
                file_path=request.file_path,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "FileNotFoundError",
                    "message": e.message,
                },
            ) from e
        except FileSizeError as e:
            logger.warning(
                "File too large",
                file_path=request.file_path,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": "FileSizeError",
                    "message": e.message,
                    "details": e.details,
                },
            ) from e

    try:
        # Create job in Redis with extended metadata
        job_id = await job_service.create_job(
            job_type=JobType.FILE_ANALYSIS,
            supplier_id=request.supplier_id,
            file_url=file_source,
            file_type=request.file_type,
            metadata={
                "source": "api",
                "file_type": request.file_type,
                "is_local_path": is_local_path,
                "default_currency": request.default_currency,
                "composite_delimiter": request.composite_delimiter,
                "file_size_bytes": validated_file_size,
            },
        )

        # Enqueue background task
        # Note: In production, this would use arq to enqueue the task
        # For now, we import and call the enqueue function if available
        try:
            from src.tasks.file_analysis_task import enqueue_file_analysis

            # Phase 10: Enable ML parsing by default for file_path requests
            use_ml_parsing = is_local_path  # Use ML parsing when file is local

            await enqueue_file_analysis(
                job_id=job_id,
                file_url=file_source,
                supplier_id=request.supplier_id,
                file_type=request.file_type,
                use_ml_parsing=use_ml_parsing,
                default_currency=request.default_currency,
                composite_delimiter=request.composite_delimiter,
            )
            logger.info(
                "File analysis task enqueued",
                job_id=str(job_id),
                use_ml_parsing=use_ml_parsing,
            )
        except ImportError:
            # Task module not yet implemented - job created but not processed
            logger.warning(
                "Task module not available, job created but not enqueued",
                job_id=str(job_id),
            )
        except Exception as e:
            logger.error(
                "Failed to enqueue task",
                job_id=str(job_id),
                error=str(e),
            )
            # Job is created, task will need manual retry

        return FileAnalysisResponse(
            job_id=job_id,
            status="pending",
            message="File analysis job enqueued successfully",
        )

    except Exception as e:
        logger.exception("Failed to create file analysis job", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create analysis job: {str(e)}",
        ) from e


@router.post(
    "/merge",
    response_model=BatchMatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger batch matching",
    description=(
        "Submit a batch of supplier items for product matching. "
        "Items will be matched against existing products using vector similarity "
        "and LLM reasoning. Returns a job_id for tracking progress."
    ),
    responses={
        202: {"description": "Batch job accepted and enqueued"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def batch_match(
    request: BatchMatchRequest,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> BatchMatchResponse:
    """
    Trigger batch matching job.

    Creates a job for matching multiple supplier items to products.

    Args:
        request: Batch match request with item IDs and filters
        job_service: Job service dependency

    Returns:
        BatchMatchResponse with job_id and items queued count

    Raises:
        HTTPException: On validation or server errors
    """
    logger.info(
        "Batch matching requested",
        item_count=len(request.supplier_item_ids) if request.supplier_item_ids else 0,
        supplier_id=str(request.supplier_id) if request.supplier_id else None,
        limit=request.limit,
    )

    try:
        # Determine items count
        items_count = (
            len(request.supplier_item_ids) if request.supplier_item_ids else request.limit
        )

        # Create job in Redis
        job_id = await job_service.create_job(
            job_type=JobType.BATCH_MATCH,
            supplier_id=request.supplier_id,
            items_total=items_count,
            metadata={
                "source": "api",
                "item_ids": [str(id) for id in request.supplier_item_ids]
                if request.supplier_item_ids
                else None,
                "limit": request.limit,
            },
        )

        # Enqueue background task
        try:
            from src.tasks.file_analysis_task import enqueue_batch_match

            await enqueue_batch_match(
                job_id=job_id,
                supplier_item_ids=request.supplier_item_ids,
                supplier_id=request.supplier_id,
                limit=request.limit,
            )
            logger.info("Batch match task enqueued", job_id=str(job_id))
        except ImportError:
            logger.warning(
                "Task module not available, job created but not enqueued",
                job_id=str(job_id),
            )
        except Exception as e:
            logger.error(
                "Failed to enqueue batch match task",
                job_id=str(job_id),
                error=str(e),
            )

        return BatchMatchResponse(
            job_id=job_id,
            status="pending",
            items_queued=items_count,
            message="Batch matching job enqueued successfully",
        )

    except Exception as e:
        logger.exception("Failed to create batch match job", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch match job: {str(e)}",
        ) from e


@router.post(
    "/vision",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Vision analysis (stub)",
    description=(
        "Placeholder endpoint for future image/photo processing capabilities. "
        "Currently returns 501 Not Implemented."
    ),
    responses={
        501: {"description": "Feature not implemented"},
    },
)
async def vision_analysis(
    request: VisionAnalysisRequest,
) -> JSONResponse:
    """
    Vision analysis stub endpoint.

    Logs the request for future analysis and returns 501 Not Implemented.

    Args:
        request: Vision analysis request

    Returns:
        VisionAnalysisResponse with not_implemented status
    """
    logger.info(
        "Vision analysis requested (stub)",
        image_url=str(request.image_url),
        supplier_id=str(request.supplier_id),
    )

    # Log request metadata for future analysis
    logger.debug(
        "Vision request metadata logged for future analysis",
        image_url=str(request.image_url),
        supplier_id=str(request.supplier_id),
    )

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "status": "not_implemented",
            "message": "Vision analysis is not yet implemented. "
            "This feature is planned for a future release.",
            "planned_features": [
                "Price tag OCR extraction",
                "Product image analysis",
                "Document layout detection",
                "Multi-language text recognition",
            ],
        },
    )

