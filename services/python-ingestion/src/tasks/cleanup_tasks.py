"""
File Cleanup Tasks

Removes old uploaded files from the shared volume after TTL expiration.
Cleans both the main file and its .meta.json sidecar.

@see /specs/008-ml-ingestion-integration/plan.md
@see /specs/008-ml-ingestion-integration/tasks.md - T059-T062
"""

import os
import structlog
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings

logger = structlog.get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

SHARED_UPLOADS_DIR = Path("/shared/uploads")
META_SUFFIX = ".meta.json"


# =============================================================================
# Helper Functions
# =============================================================================


def _get_file_age_hours(file_path: Path) -> float:
    """
    Get the age of a file in hours.

    Args:
        file_path: Path to the file

    Returns:
        Age in hours (based on modification time)
    """
    try:
        mtime = file_path.stat().st_mtime
        age_seconds = datetime.now(timezone.utc).timestamp() - mtime
        return age_seconds / 3600
    except OSError:
        return 0.0


def _is_meta_file(filename: str) -> bool:
    """Check if a filename is a metadata sidecar file."""
    return filename.endswith(META_SUFFIX)


def _get_meta_path(file_path: Path) -> Path:
    """Get the metadata sidecar path for a file."""
    return file_path.with_suffix(file_path.suffix + META_SUFFIX)


def _get_main_file_from_meta(meta_path: Path) -> Path:
    """Get the main file path from a metadata sidecar path."""
    # Remove .meta.json suffix
    name = meta_path.name
    if name.endswith(META_SUFFIX):
        name = name[:-len(META_SUFFIX)]
    return meta_path.parent / name


# =============================================================================
# Cleanup Functions
# =============================================================================


def _delete_file_pair(file_path: Path, log: Any) -> bool:
    """
    Delete a file and its metadata sidecar.

    Args:
        file_path: Path to the main file
        log: Logger instance

    Returns:
        True if deletion was successful, False otherwise
    """
    deleted = False
    meta_path = _get_meta_path(file_path)

    # Delete main file
    if file_path.exists():
        try:
            file_path.unlink()
            log.debug("file_deleted", path=str(file_path))
            deleted = True
        except OSError as e:
            log.warning("file_delete_failed", path=str(file_path), error=str(e))

    # Delete metadata sidecar
    if meta_path.exists():
        try:
            meta_path.unlink()
            log.debug("meta_deleted", path=str(meta_path))
            deleted = True
        except OSError as e:
            log.warning("meta_delete_failed", path=str(meta_path), error=str(e))

    return deleted


def _find_expired_files(
    directory: Path,
    ttl_hours: int,
    log: Any,
) -> List[Path]:
    """
    Find files that have exceeded the TTL.

    Args:
        directory: Directory to scan
        ttl_hours: Time-to-live in hours
        log: Logger instance

    Returns:
        List of expired file paths (main files only, not .meta.json)
    """
    expired: List[Path] = []

    if not directory.exists():
        log.warning("cleanup_directory_not_found", path=str(directory))
        return expired

    try:
        for entry in directory.iterdir():
            if not entry.is_file():
                continue

            # Skip meta files (will be deleted with main file)
            if _is_meta_file(entry.name):
                continue

            # Check age
            age_hours = _get_file_age_hours(entry)
            if age_hours >= ttl_hours:
                expired.append(entry)
                log.debug(
                    "file_expired",
                    path=str(entry),
                    age_hours=round(age_hours, 2),
                    ttl_hours=ttl_hours,
                )

    except OSError as e:
        log.error("cleanup_scan_error", directory=str(directory), error=str(e))

    return expired


# =============================================================================
# Main Cleanup Task
# =============================================================================


async def cleanup_shared_files_task(
    ctx: Dict[str, Any],
    ttl_hours: Optional[int] = None,
    dry_run: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    Clean up expired files from the shared uploads directory.

    This task runs periodically (registered as cron every 6 hours) to:
    1. Scan the shared uploads directory
    2. Find files older than the TTL
    3. Delete both the main file and its .meta.json sidecar

    Args:
        ctx: Worker context
        ttl_hours: Override for file TTL (defaults to settings.file_cleanup_ttl_hours)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with cleanup results:
            - files_found: Number of expired files found
            - files_deleted: Number of files deleted
            - bytes_freed: Total bytes freed
            - errors: List of error messages
    """
    log = logger.bind(task="cleanup_shared_files")

    # Use configured TTL or override
    cleanup_ttl = ttl_hours or settings.file_cleanup_ttl_hours

    log.info(
        "cleanup_started",
        directory=str(SHARED_UPLOADS_DIR),
        ttl_hours=cleanup_ttl,
        dry_run=dry_run,
    )

    result = {
        "files_found": 0,
        "files_deleted": 0,
        "bytes_freed": 0,
        "errors": [],
    }

    # Find expired files
    expired_files = _find_expired_files(
        directory=SHARED_UPLOADS_DIR,
        ttl_hours=cleanup_ttl,
        log=log,
    )

    result["files_found"] = len(expired_files)

    if not expired_files:
        log.info("cleanup_no_expired_files")
        return result

    # Delete expired files
    for file_path in expired_files:
        try:
            # Get file size before deletion
            file_size = 0
            meta_size = 0

            if file_path.exists():
                file_size = file_path.stat().st_size

            meta_path = _get_meta_path(file_path)
            if meta_path.exists():
                meta_size = meta_path.stat().st_size

            if dry_run:
                log.info(
                    "would_delete_file",
                    path=str(file_path),
                    size_bytes=file_size,
                    meta_size_bytes=meta_size,
                )
            else:
                if _delete_file_pair(file_path, log):
                    result["files_deleted"] += 1
                    result["bytes_freed"] += file_size + meta_size

        except Exception as e:
            error_msg = f"Failed to process {file_path.name}: {e}"
            result["errors"].append(error_msg)
            log.warning("cleanup_file_error", path=str(file_path), error=str(e))

    log.info(
        "cleanup_complete",
        files_found=result["files_found"],
        files_deleted=result["files_deleted"],
        bytes_freed=result["bytes_freed"],
        bytes_freed_mb=round(result["bytes_freed"] / (1024 * 1024), 2),
        errors_count=len(result["errors"]),
        dry_run=dry_run,
    )

    return result


# =============================================================================
# Utility Functions
# =============================================================================


async def get_shared_directory_stats() -> Dict[str, Any]:
    """
    Get statistics about the shared uploads directory.

    Returns:
        Dict with directory stats:
            - total_files: Number of files (excluding .meta.json)
            - total_size_bytes: Total size of all files
            - oldest_file_hours: Age of oldest file in hours
            - newest_file_hours: Age of newest file in hours
    """
    stats = {
        "total_files": 0,
        "total_size_bytes": 0,
        "oldest_file_hours": 0.0,
        "newest_file_hours": float("inf"),
    }

    if not SHARED_UPLOADS_DIR.exists():
        return stats

    for entry in SHARED_UPLOADS_DIR.iterdir():
        if not entry.is_file() or _is_meta_file(entry.name):
            continue

        stats["total_files"] += 1
        stats["total_size_bytes"] += entry.stat().st_size

        age_hours = _get_file_age_hours(entry)
        if age_hours > stats["oldest_file_hours"]:
            stats["oldest_file_hours"] = age_hours
        if age_hours < stats["newest_file_hours"]:
            stats["newest_file_hours"] = age_hours

    # Handle case where no files were found
    if stats["newest_file_hours"] == float("inf"):
        stats["newest_file_hours"] = 0.0

    return stats


async def cleanup_specific_job_files(
    job_id: str,
    log: Optional[Any] = None,
) -> bool:
    """
    Clean up files associated with a specific job.

    Useful for cleaning up after a failed job or manual deletion.

    Args:
        job_id: Job ID to clean up files for
        log: Optional logger instance

    Returns:
        True if any files were deleted, False otherwise
    """
    if log is None:
        log = logger.bind(job_id=job_id)

    if not SHARED_UPLOADS_DIR.exists():
        return False

    deleted = False

    # Find files with this job_id in their name
    for entry in SHARED_UPLOADS_DIR.iterdir():
        if not entry.is_file():
            continue

        if job_id in entry.name and not _is_meta_file(entry.name):
            if _delete_file_pair(entry, log):
                deleted = True
                log.info("job_files_cleaned", file=entry.name)

    return deleted

