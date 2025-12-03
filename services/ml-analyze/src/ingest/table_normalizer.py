"""
Table Normalizer Abstract Base Class
====================================

Defines the interface for file parsing strategies.
All parsers (Excel, PDF, CSV) implement this interface.

Follows Open/Closed Principle (SOLID-O):
- Open for extension: New file types can be added by creating new strategies
- Closed for modification: Existing strategies don't need to change
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from src.schemas.domain import NormalizedRow
from src.utils.errors import ParsingError

if TYPE_CHECKING:
    from uuid import UUID


class TableNormalizer(ABC):
    """
    Abstract base class for file parsing strategies.

    Implements the Strategy pattern for handling different file formats.
    Each implementation handles a specific file type (PDF, Excel, CSV).

    Contract:
        - Input: File path (local or URL)
        - Output: List of NormalizedRow objects
        - Errors: ParsingError for recoverable issues (log and continue)

    Usage:
        parser = ExcelStrategy()
        rows = await parser.parse("/path/to/file.xlsx", supplier_id)

    Implementations:
        - ExcelStrategy: Handles .xlsx/.xls with merged cell forward-fill
        - PdfStrategy: Extracts tables from PDF using pymupdf4llm
        - CsvStrategy: Handles CSV/TSV files with encoding detection
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """
        Return list of supported file extensions.

        Returns:
            List of extensions (lowercase, without dot)
            e.g., ['xlsx', 'xls']
        """
        ...

    @abstractmethod
    async def parse(
        self,
        file_path: str | Path,
        supplier_id: "UUID | None" = None,
    ) -> list[NormalizedRow]:
        """
        Parse file and return normalized rows.

        Args:
            file_path: Path to the file (local path or URL)
            supplier_id: Optional supplier ID for context logging

        Returns:
            List of NormalizedRow objects

        Raises:
            ParsingError: If file cannot be parsed
            FileNotFoundError: If file doesn't exist

        Note:
            - Implementations should handle errors per-row, not per-file
            - Invalid rows should be logged and skipped, not raise exceptions
            - Return partial results with valid rows
        """
        ...

    @abstractmethod
    async def validate_file(self, file_path: str | Path) -> bool:
        """
        Validate that file can be parsed by this strategy.

        Args:
            file_path: Path to the file

        Returns:
            True if file can be parsed, False otherwise

        Note:
            Should check:
            - File exists
            - File extension matches supported types
            - File is readable (basic header check)
        """
        ...

    def can_handle(self, file_path: str | Path) -> bool:
        """
        Check if this strategy can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if file extension is supported
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        extension = path.suffix.lower().lstrip(".")
        return extension in self.supported_extensions

    def get_file_extension(self, file_path: str | Path) -> str:
        """
        Extract file extension from path.

        Args:
            file_path: Path to the file

        Returns:
            Lowercase extension without dot
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        return path.suffix.lower().lstrip(".")


class ParserError:
    """
    Container for parser error information.

    Used for collecting errors during parsing without stopping.
    """

    def __init__(
        self,
        row_number: int,
        error_type: str,
        message: str,
        raw_data: dict | None = None,
    ) -> None:
        """
        Initialize parser error.

        Args:
            row_number: Row number where error occurred
            error_type: Type of error (e.g., 'validation', 'format')
            message: Human-readable error message
            raw_data: Original row data for debugging
        """
        self.row_number = row_number
        self.error_type = error_type
        self.message = message
        self.raw_data = raw_data

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "row_number": self.row_number,
            "error_type": self.error_type,
            "message": self.message,
            "raw_data": self.raw_data,
        }


class ParseResult:
    """
    Result container for parsing operations.

    Contains both successfully parsed rows and errors.
    """

    def __init__(
        self,
        rows: list[NormalizedRow],
        errors: list[ParserError],
        total_rows: int,
    ) -> None:
        """
        Initialize parse result.

        Args:
            rows: Successfully parsed rows
            errors: Errors encountered during parsing
            total_rows: Total rows attempted
        """
        self.rows = rows
        self.errors = errors
        self.total_rows = total_rows

    @property
    def success_count(self) -> int:
        """Number of successfully parsed rows."""
        return len(self.rows)

    @property
    def error_count(self) -> int:
        """Number of errors encountered."""
        return len(self.errors)

    @property
    def success_rate(self) -> float:
        """Percentage of successfully parsed rows."""
        if self.total_rows == 0:
            return 0.0
        return (self.success_count / self.total_rows) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "total_rows": self.total_rows,
            "success_rate": round(self.success_rate, 2),
            "errors": [e.to_dict() for e in self.errors],
        }

