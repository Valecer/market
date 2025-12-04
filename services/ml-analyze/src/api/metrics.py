"""
Prometheus Metrics for ML-Analyze Service
==========================================

Provides metrics for monitoring semantic ETL pipeline performance.

Phase 9 T81: Metrics for extraction_success_rate, category_match_rate,
             processing_time_seconds.

Metrics are exposed via the /metrics endpoint for Prometheus scraping.

Usage:
    from src.api.metrics import (
        EXTRACTION_SUCCESS_RATE,
        CATEGORY_MATCH_RATE,
        PROCESSING_TIME,
        record_etl_metrics,
    )
    
    # Record extraction metrics
    EXTRACTION_SUCCESS_RATE.labels(supplier_id="123").set(95.5)
    
    # Time a processing phase
    with PROCESSING_TIME.labels(phase="extracting").time():
        await process()
"""

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY

# =============================================================================
# Metric Definitions
# =============================================================================

# Extraction Success Metrics
EXTRACTION_SUCCESS_RATE = Gauge(
    "semantic_etl_extraction_success_rate",
    "Extraction success rate as percentage (0-100)",
    ["supplier_id", "job_id"],
)

EXTRACTION_TOTAL = Counter(
    "semantic_etl_extractions_total",
    "Total number of extraction attempts",
    ["supplier_id", "status"],  # status: success, failed
)

EXTRACTION_PRODUCTS = Counter(
    "semantic_etl_products_extracted_total",
    "Total products extracted successfully",
    ["supplier_id"],
)

# Category Matching Metrics
CATEGORY_MATCH_RATE = Gauge(
    "semantic_etl_category_match_rate",
    "Category match rate as percentage (0-100)",
    ["supplier_id", "job_id"],
)

CATEGORY_OPERATIONS = Counter(
    "semantic_etl_category_operations_total",
    "Total category operations (match or create)",
    ["supplier_id", "operation"],  # operation: matched, created
)

# Processing Time Metrics
PROCESSING_TIME = Histogram(
    "semantic_etl_processing_seconds",
    "Processing time in seconds per phase",
    ["phase"],  # phase: analyzing, extracting, normalizing, total
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")],
)

PROCESSING_DURATION_TOTAL = Gauge(
    "semantic_etl_job_duration_seconds",
    "Total job duration in seconds",
    ["supplier_id", "job_id", "status"],
)

# Job Status Metrics
JOBS_TOTAL = Counter(
    "semantic_etl_jobs_total",
    "Total number of ETL jobs processed",
    ["status"],  # status: complete, completed_with_errors, failed
)

JOBS_IN_PROGRESS = Gauge(
    "semantic_etl_jobs_in_progress",
    "Number of ETL jobs currently in progress",
)

# Deduplication Metrics
DUPLICATES_REMOVED = Counter(
    "semantic_etl_duplicates_removed_total",
    "Total duplicate products removed",
    ["supplier_id", "dedup_type"],  # dedup_type: within_sheet, cross_sheet
)

# LLM Metrics
LLM_REQUESTS_TOTAL = Counter(
    "semantic_etl_llm_requests_total",
    "Total LLM extraction requests",
    ["model", "status"],  # status: success, failed, timeout
)

LLM_REQUEST_DURATION = Histogram(
    "semantic_etl_llm_request_seconds",
    "LLM request duration in seconds",
    ["model"],
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf")],
)

LLM_TOKENS_PROCESSED = Counter(
    "semantic_etl_llm_tokens_total",
    "Total tokens processed by LLM (estimated)",
    ["model", "direction"],  # direction: input, output
)

# Error Metrics
ERRORS_TOTAL = Counter(
    "semantic_etl_errors_total",
    "Total errors by type and phase",
    ["error_type", "phase"],  # error_type: validation, parsing, llm_error, timeout
)

# File Processing Metrics
FILES_PROCESSED = Counter(
    "semantic_etl_files_processed_total",
    "Total files processed",
    ["file_type", "status"],  # file_type: excel, csv; status: success, failed
)

ROWS_PROCESSED = Counter(
    "semantic_etl_rows_processed_total",
    "Total rows processed from source files",
    ["supplier_id"],
)

SHEETS_PROCESSED = Counter(
    "semantic_etl_sheets_processed_total",
    "Total sheets processed from Excel files",
    ["selection_type"],  # selection_type: priority, fallback, skipped
)


# =============================================================================
# Helper Functions
# =============================================================================

def record_etl_metrics(
    job_id: str,
    supplier_id: str,
    status: str,
    duration_seconds: float,
    extraction_success_rate: float,
    category_match_rate: float,
    products_extracted: int,
    products_failed: int,
    duplicates_removed: int,
    categories_matched: int,
    categories_created: int,
    total_rows: int,
) -> None:
    """
    Record comprehensive ETL metrics for a completed job.
    
    T81: Helper function to update all relevant metrics atomically.
    
    Args:
        job_id: Job identifier
        supplier_id: Supplier identifier
        status: Final status (complete, completed_with_errors, failed)
        duration_seconds: Total processing duration
        extraction_success_rate: Success rate percentage (0-100)
        category_match_rate: Category match rate percentage (0-100)
        products_extracted: Number of successfully extracted products
        products_failed: Number of failed extractions
        duplicates_removed: Number of duplicates removed
        categories_matched: Number of categories matched to existing
        categories_created: Number of new categories created
        total_rows: Total rows processed from source
    """
    # Update gauges with job-specific values
    EXTRACTION_SUCCESS_RATE.labels(
        supplier_id=supplier_id,
        job_id=job_id,
    ).set(extraction_success_rate)
    
    CATEGORY_MATCH_RATE.labels(
        supplier_id=supplier_id,
        job_id=job_id,
    ).set(category_match_rate)
    
    PROCESSING_DURATION_TOTAL.labels(
        supplier_id=supplier_id,
        job_id=job_id,
        status=status,
    ).set(duration_seconds)
    
    # Update counters
    JOBS_TOTAL.labels(status=status).inc()
    
    EXTRACTION_TOTAL.labels(supplier_id=supplier_id, status="success").inc(products_extracted)
    EXTRACTION_TOTAL.labels(supplier_id=supplier_id, status="failed").inc(products_failed)
    
    EXTRACTION_PRODUCTS.labels(supplier_id=supplier_id).inc(products_extracted)
    
    CATEGORY_OPERATIONS.labels(supplier_id=supplier_id, operation="matched").inc(categories_matched)
    CATEGORY_OPERATIONS.labels(supplier_id=supplier_id, operation="created").inc(categories_created)
    
    ROWS_PROCESSED.labels(supplier_id=supplier_id).inc(total_rows)
    
    if duplicates_removed > 0:
        DUPLICATES_REMOVED.labels(
            supplier_id=supplier_id,
            dedup_type="combined",
        ).inc(duplicates_removed)
    
    # Record duration in histogram
    PROCESSING_TIME.labels(phase="total").observe(duration_seconds)


def record_phase_duration(phase: str, duration_seconds: float) -> None:
    """
    Record duration for a specific processing phase.
    
    Args:
        phase: Phase name (analyzing, extracting, normalizing)
        duration_seconds: Duration in seconds
    """
    PROCESSING_TIME.labels(phase=phase).observe(duration_seconds)


def record_llm_request(
    model: str,
    status: str,
    duration_seconds: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """
    Record LLM request metrics.
    
    Args:
        model: Model name (e.g., llama3)
        status: Request status (success, failed, timeout)
        duration_seconds: Request duration
        input_tokens: Estimated input tokens
        output_tokens: Estimated output tokens
    """
    LLM_REQUESTS_TOTAL.labels(model=model, status=status).inc()
    LLM_REQUEST_DURATION.labels(model=model).observe(duration_seconds)
    
    if input_tokens > 0:
        LLM_TOKENS_PROCESSED.labels(model=model, direction="input").inc(input_tokens)
    if output_tokens > 0:
        LLM_TOKENS_PROCESSED.labels(model=model, direction="output").inc(output_tokens)


def record_error(error_type: str, phase: str) -> None:
    """
    Record an error occurrence.
    
    Args:
        error_type: Type of error (validation, parsing, llm_error, timeout)
        phase: Phase where error occurred
    """
    ERRORS_TOTAL.labels(error_type=error_type, phase=phase).inc()


def increment_jobs_in_progress() -> None:
    """Increment jobs in progress gauge."""
    JOBS_IN_PROGRESS.inc()


def decrement_jobs_in_progress() -> None:
    """Decrement jobs in progress gauge."""
    JOBS_IN_PROGRESS.dec()


# =============================================================================
# Metric Endpoint Setup
# =============================================================================

def get_metrics_app():
    """
    Get ASGI app for /metrics endpoint.
    
    Returns:
        ASGI application that serves Prometheus metrics
    """
    from prometheus_client import make_asgi_app
    return make_asgi_app()

