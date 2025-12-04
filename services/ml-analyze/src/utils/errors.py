"""
Custom Exception Classes
========================

Application-specific exceptions for proper error handling.
"""

from typing import Any


class MLAnalyzeError(Exception):
    """Base exception for ml-analyze service."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ParsingError(MLAnalyzeError):
    """Raised when file parsing fails."""

    pass


class EmbeddingError(MLAnalyzeError):
    """Raised when embedding generation fails."""

    pass


class LLMError(MLAnalyzeError):
    """Raised when LLM inference fails."""

    pass


class DatabaseError(MLAnalyzeError):
    """Raised when database operations fail."""

    pass


class ConfigurationError(MLAnalyzeError):
    """Raised when configuration is invalid."""

    pass


class JobNotFoundError(MLAnalyzeError):
    """Raised when a job is not found."""

    pass


class ValidationError(MLAnalyzeError):
    """Raised when input validation fails."""

    pass


class SecurityError(MLAnalyzeError):
    """
    Raised when a security violation is detected.

    Used for path traversal prevention, unauthorized access attempts,
    and other security-related issues.
    """

    pass


class FileNotFoundError(MLAnalyzeError):
    """Raised when a requested file cannot be found."""

    pass


class FileSizeError(MLAnalyzeError):
    """Raised when a file exceeds the maximum allowed size."""

    pass

