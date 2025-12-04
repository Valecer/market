"""
Analyze Routes
===============

API endpoints for file analysis and batch matching.

Endpoints:
- POST /analyze/file - Trigger file analysis job (semantic ETL)
- POST /analyze/merge - Trigger batch matching job
- POST /analyze/vision - Vision analysis stub (501)

All endpoints return job IDs for async status tracking.

Phase 9: Updated to use SmartParserService for semantic ETL.
"""

import asyncio
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from src.db.connection import get_session
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
from src.services.smart_parser.service import SmartParserService, SmartParserError
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _run_smart_parser(
    file_path: str,
    supplier_id: UUID,
    job_id: UUID,
    job_service: JobService,
) -> None:
    """
    Background task to run SmartParserService.
    
    Phase 9: Semantic ETL processing in background.
    
    Args:
        file_path: Path to file in shared volume
        supplier_id: Supplier UUID
        job_id: Job UUID for status tracking
        job_service: Job service for updates
    """
    try:
        async with get_session() as session:
            service = SmartParserService(
                session=session,
                job_service=job_service,
            )
            
            # Convert UUID to int for supplier_id (SmartParserService expects int)
            # Use hash of UUID for stable int conversion
            supplier_id_int = hash(str(supplier_id)) % (2**31)
            
            result = await service.parse_file(
                file_path=file_path,
                supplier_id=supplier_id_int,
                job_id=str(job_id),
            )
            
            logger.info(
                "Smart parser completed",
                job_id=str(job_id),
                status=result.status,
                products=result.successful_extractions,
            )
            
    except SmartParserError as e:
        logger.error(f"Smart parser failed: {e}", job_id=str(job_id))
        # Status already updated by SmartParserService
    except Exception as e:
        logger.exception(f"Unexpected error in smart parser: {e}", job_id=str(job_id))
        try:
            await job_service.update_job_status(
                job_id=str(job_id),
                phase="failed",
                progress_percent=0,
                error_message=str(e),
            )
        except Exception:
            pass


@router.post(
    "/file",
    response_model=FileAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger file analysis",
    description=(
        "Submit a file for semantic ETL analysis. The file will be parsed using LLM-based "
        "extraction, categories normalized with fuzzy matching, and products deduplicated. "
        "Returns a job_id for tracking progress via GET /analyze/status/{job_id}."
    ),
    responses={
        202: {"description": "Job accepted and enqueued"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def analyze_file(
    request: FileAnalysisRequest,
    background_tasks: BackgroundTasks,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> FileAnalysisResponse:
    """
    Trigger file analysis job using SmartParserService.

    Phase 9: Semantic ETL pipeline - validates the request, creates a job 
    in Redis, and starts SmartParserService in background.

    Args:
        request: File analysis request with file_url, supplier_id, file_type
        background_tasks: FastAPI background tasks
        job_service: Job service dependency

    Returns:
        FileAnalysisResponse with job_id for status tracking

    Raises:
        HTTPException: On validation or server errors
    """
    logger.info(
        "File analysis requested (semantic ETL)",
        file_url=str(request.file_url),
        supplier_id=str(request.supplier_id),
        file_type=request.file_type,
    )

    # Validate file path exists (for local files)
    file_path = str(request.file_url)
    if file_path.startswith("/") or file_path.startswith("file://"):
        # Local file path
        clean_path = file_path.replace("file://", "")
        if not Path(clean_path).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File not found: {clean_path}",
            )
        file_path = clean_path

    try:
        # Create job in Redis
        job_id = await job_service.create_job(
            job_type=JobType.FILE_ANALYSIS,
            supplier_id=request.supplier_id,
            file_url=file_path,
            file_type=request.file_type,
            metadata={
                "source": "api",
                "file_type": request.file_type,
                "semantic_etl": True,  # Flag for Phase 9
            },
        )
        
        logger.info("Job created", job_id=str(job_id))

        # Start SmartParserService in background
        background_tasks.add_task(
            _run_smart_parser,
            file_path=file_path,
            supplier_id=request.supplier_id,
            job_id=job_id,
            job_service=job_service,
        )
        
        logger.info("Semantic ETL task scheduled", job_id=str(job_id))

        return FileAnalysisResponse(
            job_id=job_id,
            status="pending",
            message="File analysis job enqueued for semantic ETL processing",
        )

    except HTTPException:
        raise
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

