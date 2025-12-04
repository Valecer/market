"""
Pydantic Response Models
========================

API response schemas for ml-analyze service endpoints.
Ensures consistent response structure across all endpoints.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileAnalysisResponse(BaseModel):
    """
    Response for POST /analyze/file endpoint.

    Returns job ID for tracking analysis progress.

    Attributes:
        job_id: Unique identifier for tracking the job
        status: Initial status (always 'pending')
        message: Human-readable status message
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "File analysis job enqueued successfully",
            }
        }
    )

    job_id: Annotated[
        UUID,
        Field(description="Unique job identifier for status tracking"),
    ]
    status: Annotated[
        Literal["pending", "processing", "completed", "failed"],
        Field(description="Current job status"),
    ]
    message: Annotated[
        str,
        Field(description="Human-readable status message"),
    ]


class JobStatusResponse(BaseModel):
    """
    Response for GET /analyze/status/:job_id endpoint.

    Provides detailed job progress information with semantic ETL metrics.

    Attributes:
        job_id: Job identifier
        status: Current status
        phase: Current processing phase (semantic ETL)
        progress_percentage: Completion percentage (0-100)
        items_processed: Number of items processed so far
        items_total: Total number of items to process
        successful_extractions: Successfully extracted products (semantic ETL)
        failed_extractions: Failed extractions (semantic ETL)
        duplicates_removed: Duplicates removed (semantic ETL)
        errors: List of error messages encountered
        retry_count: Number of retry attempts made (T84)
        max_retries: Maximum allowed retries (T84)
        retry_summary: Human-readable retry status (T84)
        created_at: Job creation timestamp
        started_at: Processing start timestamp (null if pending)
        completed_at: Completion timestamp (null if not done)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "phase": "extracting",
                "progress_percentage": 45,
                "items_processed": 45,
                "items_total": 100,
                "successful_extractions": 42,
                "failed_extractions": 3,
                "duplicates_removed": 0,
                "errors": [],
                "retry_count": 0,
                "max_retries": 3,
                "retry_summary": None,
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:05Z",
                "completed_at": None,
            }
        }
    )

    job_id: Annotated[
        UUID,
        Field(description="Unique job identifier"),
    ]
    status: Annotated[
        Literal["pending", "processing", "completed", "failed", "completed_with_errors"],
        Field(description="Current job status"),
    ]
    phase: Annotated[
        Literal[
            "pending", "downloading", "analyzing", "extracting", 
            "normalizing", "complete", "completed_with_errors", "failed"
        ] | None,
        Field(default=None, description="Current processing phase (semantic ETL)"),
    ]
    progress_percentage: Annotated[
        int,
        Field(ge=0, le=100, description="Job completion percentage"),
    ]
    items_processed: Annotated[
        int,
        Field(ge=0, description="Number of items processed"),
    ]
    items_total: Annotated[
        int,
        Field(ge=0, description="Total items to process"),
    ]
    successful_extractions: Annotated[
        int,
        Field(default=0, ge=0, description="Successfully extracted products (semantic ETL)"),
    ]
    failed_extractions: Annotated[
        int,
        Field(default=0, ge=0, description="Failed extractions (semantic ETL)"),
    ]
    duplicates_removed: Annotated[
        int,
        Field(default=0, ge=0, description="Duplicates removed (semantic ETL)"),
    ]
    errors: Annotated[
        list[str],
        Field(default_factory=list, description="Error messages encountered"),
    ]
    # T84: Retry summary fields
    retry_count: Annotated[
        int,
        Field(default=0, ge=0, description="Number of retry attempts made"),
    ]
    max_retries: Annotated[
        int,
        Field(default=3, ge=0, description="Maximum allowed retry attempts"),
    ]
    retry_summary: Annotated[
        str | None,
        Field(default=None, description="Human-readable retry status (e.g., 'Retried 2/3 times')"),
    ]
    created_at: Annotated[
        datetime,
        Field(description="Job creation timestamp"),
    ]
    started_at: Annotated[
        datetime | None,
        Field(default=None, description="Processing start timestamp"),
    ]
    completed_at: Annotated[
        datetime | None,
        Field(default=None, description="Job completion timestamp"),
    ]


class HealthCheckResponse(BaseModel):
    """
    Response for GET /health endpoint.

    Provides service health status and dependency checks.

    Attributes:
        status: Overall health status
        version: Service version
        service: Service name
        checks: Individual component health checks
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "service": "ml-analyze",
                "checks": {
                    "database": {"status": "healthy", "latency_ms": 5.2},
                    "ollama": {"status": "healthy", "url": "http://localhost:11434"},
                    "redis": {"status": "healthy", "latency_ms": 1.5},
                },
            }
        }
    )

    status: Annotated[
        Literal["healthy", "unhealthy", "degraded"],
        Field(description="Overall service health status"),
    ]
    version: Annotated[
        str,
        Field(description="Service version"),
    ]
    service: Annotated[
        str,
        Field(default="ml-analyze", description="Service name"),
    ]
    checks: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Individual health checks"),
    ]


class BatchMatchResponse(BaseModel):
    """
    Response for POST /analyze/merge endpoint.

    Returns job ID and summary of batch matching job.

    Attributes:
        job_id: Unique job identifier
        status: Initial status
        items_queued: Number of items queued for matching
        message: Human-readable status message
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "items_queued": 150,
                "message": "Batch matching job enqueued successfully",
            }
        }
    )

    job_id: Annotated[
        UUID,
        Field(description="Unique job identifier"),
    ]
    status: Annotated[
        Literal["pending", "processing", "completed", "failed"],
        Field(description="Current job status"),
    ]
    items_queued: Annotated[
        int,
        Field(ge=0, description="Number of items queued for matching"),
    ]
    message: Annotated[
        str,
        Field(description="Human-readable status message"),
    ]


class VisionAnalysisResponse(BaseModel):
    """
    Response for POST /analyze/vision endpoint (stub).

    Returns 501 Not Implemented status.

    Attributes:
        status: Always 'not_implemented'
        message: Explanation message
        planned_features: List of planned vision capabilities
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "not_implemented",
                "message": "Vision analysis is not yet implemented",
                "planned_features": [
                    "Price tag OCR",
                    "Product image analysis",
                    "Document layout detection",
                ],
            }
        }
    )

    status: Annotated[
        Literal["not_implemented"],
        Field(description="Feature status"),
    ]
    message: Annotated[
        str,
        Field(description="Status message"),
    ]
    planned_features: Annotated[
        list[str],
        Field(default_factory=list, description="Planned vision capabilities"),
    ]


class ErrorResponse(BaseModel):
    """
    Standard error response format.

    Consistent error structure across all endpoints.

    Attributes:
        error: Error type/name
        message: Human-readable error message
        details: Additional error context
        request_id: Request tracking ID (if available)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid file type",
                "details": {"file_type": "docx", "allowed": ["pdf", "excel", "csv"]},
                "request_id": "req-123456",
            }
        }
    )

    error: Annotated[
        str,
        Field(description="Error type/name"),
    ]
    message: Annotated[
        str,
        Field(description="Human-readable error message"),
    ]
    details: Annotated[
        dict[str, Any],
        Field(default_factory=dict, description="Additional error context"),
    ]
    request_id: Annotated[
        str | None,
        Field(default=None, description="Request tracking ID"),
    ]

