"""
File Analysis Task
===================

arq background worker task for processing file analysis jobs.

Pipeline:
1. Parse file (PDF/Excel/CSV)
2. Generate embeddings for each item
3. Match items to products
4. Update job status throughout

Follows error isolation: per-item errors are logged, processing continues.
"""

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from arq import ArqRedis

from src.config.settings import Settings, get_settings
from src.db.connection import get_session
from src.db.repositories.embeddings_repo import EmbeddingsRepository
from src.rag.vector_service import VectorService
from src.services.ingestion_service import IngestionService
from src.services.job_service import (
    JobService,
    JobStatus,
    JobType,
    get_redis_client,
)
from src.services.matching_service import MatchingService
from src.utils.errors import ParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def process_file_analysis(
    ctx: dict[str, Any],
    job_id: UUID,
    file_url: str,
    supplier_id: UUID,
    file_type: str,
    use_ml_parsing: bool = True,
    default_currency: str | None = None,
    composite_delimiter: str = "|",
) -> dict[str, Any]:
    """
    Process a file analysis job.

    Full pipeline:
    1. Parse file to extract items (traditional or ML-based)
    2. Generate embeddings for each item
    3. Match items to existing products
    4. Update job status and return results

    Args:
        ctx: arq context with redis connection
        job_id: Job UUID
        file_url: URL or path to file
        supplier_id: Supplier UUID
        file_type: File type (pdf, excel, csv)
        use_ml_parsing: Enable ML-based parsing with TwoStageParsingService
        default_currency: Default ISO 4217 currency code for ML parsing
        composite_delimiter: Delimiter for composite names in ML parsing

    Returns:
        Dict with processing results
    """
    logger.info(
        "Starting file analysis",
        job_id=str(job_id),
        file_url=file_url,
        supplier_id=str(supplier_id),
        file_type=file_type,
    )

    # Get services
    redis: ArqRedis = ctx.get("redis") or await get_redis_client()
    job_service = JobService(redis)
    settings = get_settings()

    # Initialize result tracking
    result: dict[str, Any] = {
        "job_id": str(job_id),
        "success": False,
        "items_parsed": 0,
        "items_embedded": 0,
        "items_matched": 0,
        "errors": [],
        "parsing_mode": "ml" if use_ml_parsing else "traditional",
        "metrics": None,
    }

    try:
        # Mark job as processing
        await job_service.mark_started(job_id)

        # Resolve file path
        # Note: file_url is always an absolute path from python-ingestion
        # (e.g., /shared/uploads/job_id_timestamp_file.xlsx)
        file_path = Path(file_url)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # ===================================================================
        # Phase 1: Parse file
        # ===================================================================
        logger.info(
            "Phase 1: Parsing file",
            job_id=str(job_id),
            use_ml_parsing=use_ml_parsing,
        )

        ingestion_service = IngestionService()
        ingestion_result = await ingestion_service.ingest_file(
            file_path=file_path,
            supplier_id=supplier_id,
            job_id=job_id,
            file_type=file_type,
            use_ml_parsing=use_ml_parsing,
            default_currency=default_currency,
            composite_delimiter=composite_delimiter,
        )

        if not ingestion_result.success:
            raise ParsingError(
                message="File parsing failed",
                details={"errors": ingestion_result.errors},
            )

        result["items_parsed"] = ingestion_result.processed_rows
        result["parsing_mode"] = ingestion_result.parsing_mode
        items_total = len(ingestion_result.chunks)

        # Include parsing metrics if available (ML parsing)
        if ingestion_result.metrics:
            result["metrics"] = ingestion_result.metrics.model_dump()

        # Update job with total items
        await job_service.update_progress(
            job_id,
            items_processed=0,
            items_total=items_total,
        )

        logger.info(
            "Parsing complete",
            job_id=str(job_id),
            rows_parsed=ingestion_result.processed_rows,
            chunks=items_total,
            parsing_mode=ingestion_result.parsing_mode,
            has_metrics=ingestion_result.metrics is not None,
        )

        # ===================================================================
        # Phase 2: Generate embeddings
        # ===================================================================
        logger.info("Phase 2: Generating embeddings", job_id=str(job_id))

        async with get_session() as session:
            vector_service = VectorService(session, settings)
            embeddings_repo = EmbeddingsRepository(session)

            embedded_count = 0
            for i, chunk in enumerate(ingestion_result.chunks):
                try:
                    # Generate embedding
                    embedding = await vector_service.embed_query(chunk.text)

                    # Store embedding
                    await embeddings_repo.insert(
                        supplier_item_id=chunk.supplier_item_id,
                        embedding=embedding,
                        model_name=settings.ollama_embedding_model,
                    )

                    embedded_count += 1

                    # Update progress every 10 items
                    if (i + 1) % 10 == 0 or i == items_total - 1:
                        await job_service.update_progress(
                            job_id,
                            items_processed=embedded_count,
                            items_total=items_total,
                        )

                except Exception as e:
                    error_msg = f"Embedding failed for item {chunk.supplier_item_id}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    continue

            result["items_embedded"] = embedded_count

        logger.info(
            "Embeddings complete",
            job_id=str(job_id),
            items_embedded=embedded_count,
        )

        # ===================================================================
        # Phase 3: Match items to products
        # ===================================================================
        logger.info("Phase 3: Matching products", job_id=str(job_id))

        async with get_session() as session:
            matching_service = MatchingService(session, settings)

            # Match items created from this job
            item_ids = ingestion_result.item_ids

            if item_ids:
                match_results, match_stats = await matching_service.match_batch(
                    supplier_item_ids=item_ids,
                    top_k=5,
                )

                result["items_matched"] = match_stats.auto_matched + match_stats.sent_to_review
                result["match_stats"] = match_stats.to_dict()

                # Collect errors from matching
                for match_result in match_results:
                    if match_result.error_message:
                        result["errors"].append(match_result.error_message)

        logger.info(
            "Matching complete",
            job_id=str(job_id),
            items_matched=result["items_matched"],
        )

        # ===================================================================
        # Complete
        # ===================================================================
        result["success"] = True
        await job_service.mark_completed(
            job_id,
            items_processed=items_total,
        )

        # Add errors to job if any
        if result["errors"]:
            job = await job_service.get_job(job_id)
            if job:
                await job_service.update_progress(
                    job_id,
                    items_processed=items_total,
                    items_total=items_total,
                    errors=result["errors"][:10],  # Limit to 10 errors
                )

        logger.info(
            "File analysis complete",
            job_id=str(job_id),
            result=result,
        )

        return result

    except Exception as e:
        error_msg = str(e)
        logger.exception("File analysis failed", job_id=str(job_id), error=error_msg)
        result["errors"].append(error_msg)

        # Mark job as failed
        await job_service.mark_failed(job_id, error_msg)

        return result


async def process_batch_match(
    ctx: dict[str, Any],
    job_id: UUID,
    supplier_item_ids: list[UUID] | None,
    supplier_id: UUID | None,
    limit: int,
) -> dict[str, Any]:
    """
    Process a batch matching job.

    Matches supplier items to products using vector similarity and LLM.

    Args:
        ctx: arq context
        job_id: Job UUID
        supplier_item_ids: Specific items to match (or None for all pending)
        supplier_id: Filter by supplier
        limit: Maximum items to process

    Returns:
        Dict with matching results
    """
    logger.info(
        "Starting batch match",
        job_id=str(job_id),
        item_count=len(supplier_item_ids) if supplier_item_ids else "pending",
        supplier_id=str(supplier_id) if supplier_id else None,
        limit=limit,
    )

    redis: ArqRedis = ctx.get("redis") or await get_redis_client()
    job_service = JobService(redis)
    settings = get_settings()

    result = {
        "job_id": str(job_id),
        "success": False,
        "items_matched": 0,
        "auto_matched": 0,
        "sent_to_review": 0,
        "errors": [],
    }

    try:
        await job_service.mark_started(job_id)

        async with get_session() as session:
            matching_service = MatchingService(session, settings)

            if supplier_item_ids:
                # Match specific items
                match_results, stats = await matching_service.match_batch(
                    supplier_item_ids=supplier_item_ids,
                )
            else:
                # Match pending items
                match_results, stats = await matching_service.match_pending_items(
                    supplier_id=supplier_id,
                    limit=limit,
                )

            result["items_matched"] = stats.items_processed
            result["auto_matched"] = stats.auto_matched
            result["sent_to_review"] = stats.sent_to_review
            result["rejected"] = stats.rejected
            result["match_errors"] = stats.errors

            # Collect errors
            for match_result in match_results:
                if match_result.error_message:
                    result["errors"].append(match_result.error_message)

        result["success"] = True
        await job_service.mark_completed(job_id, items_processed=stats.items_processed)

        logger.info("Batch match complete", job_id=str(job_id), stats=stats.to_dict())

        return result

    except Exception as e:
        error_msg = str(e)
        logger.exception("Batch match failed", job_id=str(job_id), error=error_msg)
        result["errors"].append(error_msg)
        await job_service.mark_failed(job_id, error_msg)
        return result


# ============================================================================
# arq Worker Configuration
# ============================================================================


async def startup(ctx: dict[str, Any]) -> None:
    """arq worker startup hook."""
    logger.info("File analysis worker starting")
    ctx["redis"] = await get_redis_client()


async def shutdown(ctx: dict[str, Any]) -> None:
    """arq worker shutdown hook."""
    logger.info("File analysis worker shutting down")
    redis = ctx.get("redis")
    if redis:
        await redis.close()


class WorkerSettings:
    """arq worker settings."""

    # Task functions
    functions = [
        process_file_analysis,
        process_batch_match,
    ]

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Redis settings (loaded from environment)
    @staticmethod
    def redis_settings() -> dict[str, Any]:
        settings = get_settings()
        return {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "password": settings.redis_password,
            "database": settings.redis_db,
        }

    # Worker settings
    max_jobs = 5
    job_timeout = 600  # 10 minutes
    max_tries = 3
    queue_name = "ml-analyze-queue"


# ============================================================================
# Task Enqueue Functions (called from API)
# ============================================================================


async def enqueue_file_analysis(
    job_id: UUID,
    file_url: str,
    supplier_id: UUID,
    file_type: str,
    use_ml_parsing: bool = True,
    default_currency: str | None = None,
    composite_delimiter: str = "|",
) -> None:
    """
    Enqueue a file analysis task.

    Args:
        job_id: Job UUID
        file_url: File URL or path
        supplier_id: Supplier UUID
        file_type: File type
        use_ml_parsing: Enable ML-based parsing (default True)
        default_currency: Default ISO 4217 currency code
        composite_delimiter: Delimiter for composite names
    """
    redis = await get_redis_client()

    # For now, process directly (arq enqueue would be used in production)
    # In production: await redis.enqueue_job('process_file_analysis', ...)

    # Direct execution for MVP (single-process mode)
    asyncio.create_task(
        process_file_analysis(
            ctx={"redis": redis},
            job_id=job_id,
            file_url=file_url,
            supplier_id=supplier_id,
            file_type=file_type,
            use_ml_parsing=use_ml_parsing,
            default_currency=default_currency,
            composite_delimiter=composite_delimiter,
        )
    )


async def enqueue_batch_match(
    job_id: UUID,
    supplier_item_ids: list[UUID] | None,
    supplier_id: UUID | None,
    limit: int,
) -> None:
    """
    Enqueue a batch matching task.

    Args:
        job_id: Job UUID
        supplier_item_ids: Items to match
        supplier_id: Supplier filter
        limit: Max items
    """
    redis = await get_redis_client()

    # Direct execution for MVP
    asyncio.create_task(
        process_batch_match(
            ctx={"redis": redis},
            job_id=job_id,
            supplier_item_ids=supplier_item_ids,
            supplier_id=supplier_id,
            limit=limit,
        )
    )

