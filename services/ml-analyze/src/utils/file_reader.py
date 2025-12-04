"""
Secure File Reader
==================

Secure file path validation and reading for shared volume access.

Implements:
- Path traversal prevention using pathlib.resolve()
- File existence and size validation
- Safe file reading within allowed directories

Security Note:
    This module is critical for preventing path traversal attacks.
    All file paths MUST be validated through validate_file_path()
    before any file operations.
"""

from pathlib import Path
from typing import Annotated

from pydantic import Field

from src.config.settings import get_settings
from src.utils.errors import FileNotFoundError, FileSizeError, SecurityError
from src.utils.logger import get_logger

logger = get_logger(__name__)


def validate_file_path(
    file_path: str,
    allowed_base_dir: str | None = None,
) -> Path:
    """
    Validate a file path is safe and within allowed directory.

    Prevents path traversal attacks by:
    1. Resolving the absolute path (handles ../, symlinks)
    2. Checking the resolved path starts with allowed base directory
    3. Verifying file exists

    Args:
        file_path: The file path to validate (absolute or relative)
        allowed_base_dir: Base directory files must be within.
                         Defaults to settings.uploads_dir (/shared/uploads)

    Returns:
        Path: Validated absolute path to the file

    Raises:
        SecurityError: If path is outside allowed directory (path traversal attempt)
        FileNotFoundError: If file doesn't exist

    Example:
        >>> path = validate_file_path("/shared/uploads/file.xlsx")
        >>> # Safe - returns Path("/shared/uploads/file.xlsx")

        >>> path = validate_file_path("/shared/uploads/../etc/passwd")
        >>> # Raises SecurityError - path traversal attempt
    """
    settings = get_settings()
    base_dir = Path(allowed_base_dir or settings.uploads_dir).resolve()

    # Resolve the input path to absolute (handles .., symlinks, etc.)
    resolved_path = Path(file_path).resolve()

    # Security check: ensure resolved path is within allowed directory
    try:
        resolved_path.relative_to(base_dir)
    except ValueError as e:
        logger.warning(
            "Path traversal attempt blocked",
            file_path=file_path,
            resolved_path=str(resolved_path),
            allowed_base=str(base_dir),
        )
        raise SecurityError(
            message="File path is outside allowed directory",
            details={
                "file_path": file_path,
                "allowed_directory": str(base_dir),
            },
        ) from e

    # Check file exists
    if not resolved_path.exists():
        logger.debug(
            "File not found",
            file_path=str(resolved_path),
        )
        raise FileNotFoundError(
            message=f"File not found: {file_path}",
            details={"file_path": file_path},
        )

    # Check it's a file (not directory)
    if not resolved_path.is_file():
        logger.debug(
            "Path is not a file",
            file_path=str(resolved_path),
        )
        raise FileNotFoundError(
            message=f"Path is not a file: {file_path}",
            details={"file_path": file_path},
        )

    logger.debug(
        "File path validated successfully",
        file_path=str(resolved_path),
    )

    return resolved_path


def validate_file_size(
    file_path: Path,
    max_size_mb: int | None = None,
) -> int:
    """
    Validate file size is within allowed limits.

    Args:
        file_path: Path to the file (should be pre-validated)
        max_size_mb: Maximum file size in MB.
                    Defaults to settings.max_file_size_mb (50MB)

    Returns:
        int: File size in bytes

    Raises:
        FileSizeError: If file exceeds maximum size

    Example:
        >>> size = validate_file_size(Path("/shared/uploads/large.xlsx"))
        >>> # Returns size in bytes or raises FileSizeError
    """
    settings = get_settings()
    max_size = max_size_mb or settings.max_file_size_mb
    max_bytes = max_size * 1024 * 1024

    file_size = file_path.stat().st_size

    if file_size > max_bytes:
        logger.warning(
            "File exceeds maximum size",
            file_path=str(file_path),
            file_size_bytes=file_size,
            max_size_bytes=max_bytes,
        )
        raise FileSizeError(
            message=f"File exceeds maximum size of {max_size}MB",
            details={
                "file_path": str(file_path),
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "max_size_mb": max_size,
            },
        )

    logger.debug(
        "File size validated",
        file_path=str(file_path),
        file_size_bytes=file_size,
    )

    return file_size


def validate_and_read_file(
    file_path: str,
    allowed_base_dir: str | None = None,
    max_size_mb: int | None = None,
) -> tuple[Path, int]:
    """
    Validate file path and size, return validated path and size.

    This is the main entry point for secure file access. It combines
    path traversal prevention and size validation in one call.

    Args:
        file_path: Path to the file to validate
        allowed_base_dir: Base directory constraint (defaults to /shared/uploads)
        max_size_mb: Maximum file size in MB (defaults to 50MB)

    Returns:
        tuple[Path, int]: Validated Path object and file size in bytes

    Raises:
        SecurityError: Path traversal attempt detected
        FileNotFoundError: File doesn't exist
        FileSizeError: File exceeds maximum size

    Example:
        >>> path, size = validate_and_read_file("/shared/uploads/price-list.xlsx")
        >>> print(f"Validated: {path}, size: {size} bytes")
    """
    # Step 1: Validate path (security check)
    validated_path = validate_file_path(file_path, allowed_base_dir)

    # Step 2: Validate size
    file_size = validate_file_size(validated_path, max_size_mb)

    logger.info(
        "File validated for processing",
        file_path=str(validated_path),
        file_size_bytes=file_size,
    )

    return validated_path, file_size


def read_file_bytes(file_path: Path) -> bytes:
    """
    Read file contents as bytes.

    This function assumes the path has already been validated
    through validate_file_path().

    Args:
        file_path: Pre-validated Path object

    Returns:
        bytes: File contents

    Raises:
        OSError: If file cannot be read

    Example:
        >>> path, _ = validate_and_read_file("/shared/uploads/data.xlsx")
        >>> content = read_file_bytes(path)
    """
    return file_path.read_bytes()


def get_file_extension(file_path: Path) -> str:
    """
    Get lowercase file extension without the leading dot.

    Args:
        file_path: Path to file

    Returns:
        str: Lowercase extension (e.g., "xlsx", "pdf", "csv")

    Example:
        >>> get_file_extension(Path("/uploads/Price-List.XLSX"))
        'xlsx'
    """
    return file_path.suffix.lower().lstrip(".")


# Type alias for file validation result
FileValidationResult = Annotated[
    tuple[Path, int],
    Field(description="Tuple of (validated_path, file_size_bytes)"),
]

