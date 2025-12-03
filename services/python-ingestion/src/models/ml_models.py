"""
ML Integration Pydantic Models

Models for inter-service communication between python-ingestion and ml-analyze.
Used for triggering analysis, tracking job status, and file metadata.

@see /specs/008-ml-ingestion-integration/plan/data-model.md
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Enums / Type Aliases
# =============================================================================

FileType = Literal["pdf", "excel", "csv"]
SourceType = Literal["google_sheets", "csv", "excel", "url"]
JobStatus = Literal["pending", "processing", "completed", "failed"]
JobPhase = Literal["downloading", "analyzing", "matching", "complete", "failed"]


# =============================================================================
# ML Client Request/Response Models
# =============================================================================


class MLAnalyzeRequest(BaseModel):
    """
    Request body for triggering ML analysis.

    Sent from python-ingestion to ml-analyze POST /analyze/file endpoint.
    """

    file_url: str = Field(
        description="Local path on shared volume",
        examples=["/shared/uploads/uuid_1701619200_pricelist.xlsx"],
    )
    supplier_id: UUID = Field(description="UUID of supplier owning the file")
    file_type: FileType = Field(description="Type of file being analyzed")
    metadata: dict | None = Field(
        default=None,
        description="Additional metadata to pass to ML service",
    )


class MLAnalyzeResponse(BaseModel):
    """
    Response from ML service after triggering analysis.

    Returned from ml-analyze POST /analyze/file endpoint.
    """

    job_id: UUID = Field(description="ML job ID for status tracking")
    status: JobStatus = Field(description="Initial job status (usually 'pending')")
    message: str = Field(description="Human-readable status message")


class MLJobStatus(BaseModel):
    """
    Status response from ML service.

    Returned from ml-analyze GET /analyze/status/{job_id} endpoint.
    Used for polling job progress until completion.
    """

    job_id: UUID = Field(description="ML job ID")
    status: JobStatus = Field(description="Current job status")
    progress_percentage: int = Field(ge=0, le=100, description="Overall progress 0-100")
    items_processed: int = Field(ge=0, description="Number of items processed so far")
    items_total: int = Field(ge=0, description="Total items to process")
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages encountered during processing",
    )
    created_at: datetime = Field(description="Job creation timestamp")
    started_at: datetime | None = Field(
        default=None, description="Processing start timestamp"
    )
    completed_at: datetime | None = Field(
        default=None, description="Processing completion timestamp"
    )


# =============================================================================
# Job Progress Tracking Models
# =============================================================================


class JobProgressUpdate(BaseModel):
    """
    Model for updating job progress in Redis.

    Used to track multi-phase job status for UI display.
    Supports both download and analysis phase progress.
    """

    job_id: UUID = Field(description="Job ID to update")
    phase: JobPhase = Field(description="Current processing phase")

    # Download phase progress
    download_bytes: int | None = Field(
        default=None, description="Bytes downloaded so far"
    )
    download_total: int | None = Field(
        default=None, description="Total bytes to download (if known)"
    )

    # Analysis phase progress
    items_processed: int | None = Field(
        default=None, description="Items processed by ML service"
    )
    items_total: int | None = Field(
        default=None, description="Total items to process"
    )
    matches_found: int | None = Field(
        default=None, description="Number of successful product matches"
    )
    review_queue_count: int | None = Field(
        default=None, description="Items added to review queue"
    )
    error_count: int | None = Field(
        default=None, description="Number of processing errors"
    )

    # Error information
    error_message: str | None = Field(
        default=None, description="Primary error message if failed"
    )
    error_details: list[str] = Field(
        default_factory=list,
        description="Detailed error messages for debugging",
    )

    # ML correlation
    ml_job_id: UUID | None = Field(
        default=None, description="Associated ML service job ID"
    )


# =============================================================================
# File Metadata Model
# =============================================================================


class FileMetadata(BaseModel):
    """
    Metadata sidecar for downloaded files.

    Written as {filepath}.meta.json alongside each downloaded file.
    Enables integrity verification and provenance tracking.
    """

    original_filename: str = Field(
        min_length=1,
        max_length=255,
        description="Original filename from source (sanitized)",
    )
    source_url: str = Field(description="URL or path file was downloaded from")
    source_type: SourceType = Field(description="Type of source system")
    supplier_id: UUID = Field(description="UUID of supplier owning this file")
    supplier_name: str = Field(description="Supplier name for logging")
    file_type: FileType = Field(description="Detected file type for ML processing")
    mime_type: str = Field(
        description="MIME type of the file",
        examples=[
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "application/pdf",
        ],
    )
    file_size_bytes: int = Field(gt=0, description="File size in bytes")
    checksum_md5: str = Field(
        min_length=32,
        max_length=32,
        pattern=r"^[a-f0-9]{32}$",
        description="MD5 checksum for integrity verification",
    )
    downloaded_at: datetime = Field(description="Download completion timestamp")
    downloaded_by: str = Field(
        default="python-ingestion",
        description="Service that downloaded the file",
    )
    job_id: UUID = Field(description="Associated ingestion job ID")


# =============================================================================
# Queue Task Messages
# =============================================================================


class DownloadTaskMessage(BaseModel):
    """
    Queue message for download tasks.

    Sent to arq worker to download a file and trigger ML analysis.
    """

    task_id: str = Field(description="Unique task identifier")
    job_id: UUID = Field(description="Associated job ID for status tracking")
    supplier_id: UUID = Field(description="Supplier UUID")
    supplier_name: str = Field(description="Supplier name for logging")
    source_type: SourceType = Field(description="Type of source to download from")
    source_url: str = Field(description="URL or path to download from")
    use_ml_processing: bool = Field(
        default=True,
        description="Whether to use ML pipeline (vs legacy)",
    )

    # Google Sheets specific
    sheet_name: str | None = Field(
        default=None,
        description="Sheet name for Google Sheets (defaults to first sheet)",
    )

    # Options
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum file size in MB before rejection",
    )
    timeout_seconds: int = Field(
        default=300,
        description="Download timeout in seconds",
    )

