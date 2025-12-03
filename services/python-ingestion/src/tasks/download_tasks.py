"""
Download Tasks for ML-Analyze Integration

Task functions for downloading files and triggering ML analysis.
Implements the "courier" pattern where python-ingestion downloads
files to shared volume and triggers ml-analyze for parsing.

@see /specs/008-ml-ingestion-integration/plan.md
"""

import hashlib
import json
import os
import shutil
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx

from src.config import settings
from src.models.ml_models import (
    FileMetadata,
    FileType,
    SourceType,
    DownloadTaskMessage,
)
from src.services.job_state import (
    create_job,
    update_job_phase,
    update_download_progress,
    set_ml_job_id,
)
from src.services.ml_client import (
    MLClient,
    MLServiceUnavailableError,
    MLClientError,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

SHARED_UPLOADS_DIR = Path("/shared/uploads")
MAX_DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT = 300  # 5 minutes


# =============================================================================
# Helper Functions
# =============================================================================


def _compute_md5(file_path: Path) -> str:
    """
    Compute MD5 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        MD5 hex digest (32 characters lowercase)
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename (alphanumeric, dash, underscore, dot only)
    """
    import re
    # Remove path separators
    filename = os.path.basename(filename)
    # Replace unsafe characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    return filename


def _detect_file_type(filename: str, mime_type: Optional[str] = None) -> FileType:
    """
    Detect file type from filename extension or MIME type.

    Args:
        filename: Filename with extension
        mime_type: Optional MIME type

    Returns:
        FileType enum value
    """
    ext = Path(filename).suffix.lower()

    if ext in ('.xlsx', '.xls'):
        return "excel"
    if ext == '.csv':
        return "csv"
    if ext == '.pdf':
        return "pdf"

    # Fallback to MIME type
    if mime_type:
        if 'spreadsheet' in mime_type or 'excel' in mime_type:
            return "excel"
        if 'csv' in mime_type:
            return "csv"
        if 'pdf' in mime_type:
            return "pdf"

    # Default to excel for unknown
    return "excel"


def _get_destination_path(
    job_id: UUID,
    original_filename: str,
) -> Path:
    """
    Generate destination path for downloaded file.

    Format: /shared/uploads/{job_id}_{timestamp}_{sanitized_filename}

    Args:
        job_id: Job identifier
        original_filename: Original filename

    Returns:
        Full path to destination file
    """
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    safe_name = _sanitize_filename(original_filename)
    filename = f"{job_id}_{timestamp}_{safe_name}"
    return SHARED_UPLOADS_DIR / filename


async def _write_metadata_sidecar(
    file_path: Path,
    metadata: FileMetadata,
) -> Path:
    """
    Write metadata sidecar JSON file.

    Creates a {filepath}.meta.json file alongside the downloaded file
    with provenance and integrity information.

    Args:
        file_path: Path to the downloaded file
        metadata: FileMetadata to write

    Returns:
        Path to the metadata file
    """
    meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

    logger.debug("metadata_sidecar_written", path=str(meta_path))
    return meta_path


async def _download_from_url(
    url: str,
    dest_path: Path,
    job_id: UUID,
    redis: Any,
) -> tuple[int, Optional[str]]:
    """
    Download file from HTTP URL.

    Args:
        url: URL to download from
        dest_path: Destination file path
        job_id: Job ID for progress updates
        redis: Redis connection for progress updates

    Returns:
        Tuple of (file_size_bytes, mime_type)
    """
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0)) or None
            mime_type = response.headers.get("content-type")

            # Ensure directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            downloaded = 0
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress every 100KB
                    if downloaded % (100 * 1024) < 8192:
                        await update_download_progress(
                            redis, job_id, downloaded, total_size
                        )

            return downloaded, mime_type


async def _download_from_local(
    source_path: str,
    dest_path: Path,
    job_id: UUID,
    redis: Any,
) -> tuple[int, Optional[str]]:
    """
    Copy file from local path (already uploaded).

    Args:
        source_path: Source file path
        dest_path: Destination file path
        job_id: Job ID for progress updates
        redis: Redis connection for progress updates

    Returns:
        Tuple of (file_size_bytes, mime_type)
    """
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    file_size = source.stat().st_size
    await update_download_progress(redis, job_id, 0, file_size)

    # Ensure directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy file
    shutil.copy2(source, dest_path)

    await update_download_progress(redis, job_id, file_size, file_size)

    # Detect MIME type from extension
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(source))

    return file_size, mime_type


async def _download_from_google_sheets(
    spreadsheet_url: str,
    dest_path: Path,
    job_id: UUID,
    redis: Any,
    sheet_name: Optional[str] = None,
) -> tuple[int, Optional[str]]:
    """
    Export Google Sheet to XLSX file.

    Args:
        spreadsheet_url: Google Sheets URL
        dest_path: Destination file path (will be .xlsx)
        job_id: Job ID for progress updates
        redis: Redis connection for progress updates
        sheet_name: Optional sheet name to export

    Returns:
        Tuple of (file_size_bytes, mime_type)
    """
    from src.parsers.google_sheets_parser import GoogleSheetsParser

    # Update phase
    await update_download_progress(redis, job_id, 0, None)

    # Create parser and export
    parser = GoogleSheetsParser()
    xlsx_bytes = await parser.export_to_xlsx(spreadsheet_url, sheet_name)

    # Ensure destination has .xlsx extension
    if dest_path.suffix.lower() != ".xlsx":
        dest_path = dest_path.with_suffix(".xlsx")

    # Write file
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(xlsx_bytes)

    file_size = len(xlsx_bytes)
    await update_download_progress(redis, job_id, file_size, file_size)

    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return file_size, mime_type


async def _download_file(
    source_type: SourceType,
    source_url: str,
    original_filename: str,
    job_id: UUID,
    redis: Any,
    sheet_name: Optional[str] = None,
) -> tuple[Path, FileMetadata]:
    """
    Download file from source and create metadata.

    Routes to appropriate download method based on source type.

    Args:
        source_type: Type of source (google_sheets, csv, excel, url)
        source_url: URL or path to download from
        original_filename: Original filename for metadata
        job_id: Job ID for progress updates
        redis: Redis connection for progress updates
        sheet_name: Optional sheet name for Google Sheets

    Returns:
        Tuple of (file_path, metadata)
    """
    # Generate destination path
    dest_path = _get_destination_path(job_id, original_filename)

    # Download based on source type
    if source_type == "google_sheets":
        file_size, mime_type = await _download_from_google_sheets(
            source_url, dest_path, job_id, redis, sheet_name
        )
        # Update dest_path if extension changed
        if dest_path.suffix.lower() != ".xlsx":
            dest_path = dest_path.with_suffix(".xlsx")
    elif source_type in ("csv", "excel"):
        # Check if source is local file or URL
        if source_url.startswith(("http://", "https://")):
            file_size, mime_type = await _download_from_url(
                source_url, dest_path, job_id, redis
            )
        else:
            file_size, mime_type = await _download_from_local(
                source_url, dest_path, job_id, redis
            )
    else:
        # URL source type or unknown
        file_size, mime_type = await _download_from_url(
            source_url, dest_path, job_id, redis
        )

    # Compute checksum
    checksum = _compute_md5(dest_path)

    # Detect file type
    file_type = _detect_file_type(dest_path.name, mime_type)

    # Create metadata
    metadata = FileMetadata(
        original_filename=original_filename,
        source_url=source_url,
        source_type=source_type,
        supplier_id=job_id,  # Will be overwritten by caller
        supplier_name="",  # Will be overwritten by caller
        file_type=file_type,
        mime_type=mime_type or "application/octet-stream",
        file_size_bytes=file_size,
        checksum_md5=checksum,
        downloaded_at=datetime.now(timezone.utc),
        downloaded_by="python-ingestion",
        job_id=job_id,
    )

    # Write metadata sidecar
    await _write_metadata_sidecar(dest_path, metadata)

    logger.info(
        "file_downloaded",
        dest_path=str(dest_path),
        file_size=file_size,
        checksum=checksum,
        file_type=file_type,
    )

    return dest_path, metadata


# =============================================================================
# Main Task Function
# =============================================================================


async def download_and_trigger_ml(
    ctx: dict[str, Any],
    task_id: str,
    job_id: str,
    supplier_id: str,
    supplier_name: str,
    source_type: str,
    source_url: str,
    original_filename: Optional[str] = None,
    sheet_name: Optional[str] = None,
    use_ml_processing: bool = True,
    max_file_size_mb: int = 50,
) -> dict[str, Any]:
    """
    Download file and trigger ML analysis.

    Main task function for the ML-integrated ingestion pipeline.
    Downloads file to shared volume, then triggers ml-analyze service.

    Args:
        ctx: Worker context with Redis connection
        task_id: Unique task identifier
        job_id: Associated job ID for status tracking
        supplier_id: Supplier UUID
        supplier_name: Supplier name for logging
        source_type: Type of source (google_sheets, csv, excel, url)
        source_url: URL or path to download from
        original_filename: Original filename (defaults to extracted from URL)
        sheet_name: Optional sheet name for Google Sheets
        use_ml_processing: Whether to trigger ML (False for legacy)
        max_file_size_mb: Maximum file size in MB

    Returns:
        Dict with task results:
            - task_id: Task identifier
            - job_id: Job identifier
            - status: success/partial_success/error
            - file_path: Path to downloaded file
            - ml_job_id: ML service job ID (if triggered)
            - error: Error message (if failed)
    """
    redis = ctx.get("redis")
    log = logger.bind(
        task_id=task_id,
        job_id=job_id,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
    )

    log.info("download_task_started", source_type=source_type)

    try:
        # Create job in Redis
        job_id_uuid = UUID(job_id)
        supplier_id_uuid = UUID(supplier_id)

        await create_job(
            redis=redis,
            job_id=job_id_uuid,
            supplier_id=supplier_id_uuid,
            supplier_name=supplier_name,
            file_type=_detect_file_type(original_filename or source_url),
            source_url=source_url,
        )

        # Update phase to downloading
        await update_job_phase(
            redis=redis,
            job_id=job_id_uuid,
            phase="downloading",
            status="processing",
        )

        # Determine original filename if not provided
        if not original_filename:
            if source_type == "google_sheets":
                original_filename = f"{supplier_name}_export.xlsx"
            else:
                original_filename = Path(source_url).name or f"{supplier_name}_file"

        # Download file
        file_path, metadata = await _download_file(
            source_type=SourceType(source_type),
            source_url=source_url,
            original_filename=original_filename,
            job_id=job_id_uuid,
            redis=redis,
            sheet_name=sheet_name,
        )

        # Update metadata with correct supplier info
        metadata.supplier_id = supplier_id_uuid
        metadata.supplier_name = supplier_name

        # Check file size
        max_size_bytes = max_file_size_mb * 1024 * 1024
        if metadata.file_size_bytes > max_size_bytes:
            await update_job_phase(
                redis=redis,
                job_id=job_id_uuid,
                phase="failed",
                status="failed",
                error=f"File too large: {metadata.file_size_bytes / (1024*1024):.1f}MB exceeds limit of {max_file_size_mb}MB",
            )
            return {
                "task_id": task_id,
                "job_id": job_id,
                "status": "error",
                "error": "File too large",
            }

        # Re-write metadata sidecar with correct info
        await _write_metadata_sidecar(file_path, metadata)

        log.info(
            "download_complete",
            file_path=str(file_path),
            file_size=metadata.file_size_bytes,
        )

        # If not using ML processing, return success here
        if not use_ml_processing:
            await update_job_phase(
                redis=redis,
                job_id=job_id_uuid,
                phase="complete",
                status="completed",
            )
            return {
                "task_id": task_id,
                "job_id": job_id,
                "status": "success",
                "file_path": str(file_path),
                "ml_job_id": None,
            }

        # Update phase to analyzing
        await update_job_phase(
            redis=redis,
            job_id=job_id_uuid,
            phase="analyzing",
            status="processing",
        )

        # Trigger ML analysis
        async with MLClient() as ml_client:
            # Check health first
            if not await ml_client.check_health():
                raise MLServiceUnavailableError("ML service health check failed")

            # Trigger analysis
            ml_response = await ml_client.trigger_analysis(
                file_url=str(file_path),
                supplier_id=supplier_id_uuid,
                file_type=metadata.file_type,
                metadata={
                    "job_id": job_id,
                    "supplier_name": supplier_name,
                    "original_filename": original_filename,
                },
            )

            # Store ML job ID
            await set_ml_job_id(
                redis=redis,
                job_id=job_id_uuid,
                ml_job_id=ml_response.job_id,
            )

            log.info(
                "ml_analysis_triggered",
                ml_job_id=str(ml_response.job_id),
                ml_status=ml_response.status,
            )

            return {
                "task_id": task_id,
                "job_id": job_id,
                "status": "success",
                "file_path": str(file_path),
                "ml_job_id": str(ml_response.job_id),
            }

    except MLServiceUnavailableError as e:
        log.error("ml_service_unavailable", error=str(e))
        await update_job_phase(
            redis=redis,
            job_id=job_id_uuid,
            phase="failed",
            status="failed",
            error=f"ML service unavailable: {e}",
            error_details=["ML service is not reachable. Will retry."],
        )
        # Re-raise to trigger retry
        raise

    except MLClientError as e:
        log.error("ml_client_error", error=str(e))
        await update_job_phase(
            redis=redis,
            job_id=job_id_uuid,
            phase="failed",
            status="failed",
            error=str(e),
        )
        return {
            "task_id": task_id,
            "job_id": job_id,
            "status": "error",
            "error": str(e),
        }

    except FileNotFoundError as e:
        log.error("file_not_found", error=str(e))
        await update_job_phase(
            redis=redis,
            job_id=job_id_uuid,
            phase="failed",
            status="failed",
            error=f"File not found: {e}",
        )
        return {
            "task_id": task_id,
            "job_id": job_id,
            "status": "error",
            "error": str(e),
        }

    except Exception as e:
        log.error("download_task_error", error=str(e), error_type=type(e).__name__)
        if redis:
            await update_job_phase(
                redis=redis,
                job_id=job_id_uuid,
                phase="failed",
                status="failed",
                error=str(e),
                error_details=[f"{type(e).__name__}: {e}"],
            )
        raise

