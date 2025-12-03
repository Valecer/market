"""
Parser Factory - Strategy Selection
====================================

Factory for instantiating the correct parsing strategy based on file type.
Implements the Factory Pattern for clean strategy selection.

Follows Open/Closed Principle: Add new strategies without modifying this file.
"""

from pathlib import Path
from typing import Literal

from src.ingest.excel_strategy import ExcelStrategy
from src.ingest.pdf_strategy import PdfStrategy
from src.ingest.table_normalizer import TableNormalizer
from src.utils.errors import ParsingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Type alias for supported file types
FileType = Literal["pdf", "excel", "xlsx", "xls", "xlsm"]

# Registry of available strategies
_STRATEGY_REGISTRY: dict[str, type[TableNormalizer]] = {
    "pdf": PdfStrategy,
    "excel": ExcelStrategy,
    "xlsx": ExcelStrategy,
    "xls": ExcelStrategy,
    "xlsm": ExcelStrategy,
}


class ParserFactory:
    """
    Factory for creating file parsing strategies.

    Usage:
        # By file type
        parser = ParserFactory.create("excel")

        # By file path (auto-detect)
        parser = ParserFactory.from_file_path("/path/to/file.xlsx")

        # With configuration
        parser = ParserFactory.create("pdf", pages=[0, 1, 2])
    """

    @staticmethod
    def create(
        file_type: FileType,
        **kwargs,
    ) -> TableNormalizer:
        """
        Create a parser strategy for the given file type.

        Args:
            file_type: Type of file to parse ('pdf', 'excel', 'xlsx', etc.)
            **kwargs: Additional arguments passed to strategy constructor

        Returns:
            TableNormalizer implementation for the file type

        Raises:
            ParsingError: If file type is not supported

        Example:
            >>> parser = ParserFactory.create("excel", header_row=2)
            >>> rows = await parser.parse("file.xlsx")
        """
        file_type_lower = file_type.lower()

        strategy_class = _STRATEGY_REGISTRY.get(file_type_lower)
        if not strategy_class:
            supported = list(_STRATEGY_REGISTRY.keys())
            raise ParsingError(
                message=f"Unsupported file type: {file_type}",
                details={
                    "file_type": file_type,
                    "supported_types": supported,
                },
            )

        logger.debug(
            "Creating parser strategy",
            file_type=file_type,
            strategy=strategy_class.__name__,
            kwargs=kwargs,
        )

        return strategy_class(**kwargs)

    @staticmethod
    def from_file_path(
        file_path: str | Path,
        **kwargs,
    ) -> TableNormalizer:
        """
        Create a parser strategy based on file extension.

        Args:
            file_path: Path to file (uses extension to determine type)
            **kwargs: Additional arguments passed to strategy constructor

        Returns:
            TableNormalizer implementation for the file

        Raises:
            ParsingError: If file extension is not supported

        Example:
            >>> parser = ParserFactory.from_file_path("prices.pdf")
            >>> rows = await parser.parse("prices.pdf")
        """
        path = Path(file_path) if isinstance(file_path, str) else file_path
        extension = path.suffix.lower().lstrip(".")

        if not extension:
            raise ParsingError(
                message="Cannot determine file type: no extension",
                details={"file_path": str(file_path)},
            )

        return ParserFactory.create(extension, **kwargs)

    @staticmethod
    def get_supported_types() -> list[str]:
        """
        Get list of supported file types.

        Returns:
            List of supported file type strings
        """
        return list(_STRATEGY_REGISTRY.keys())

    @staticmethod
    def is_supported(file_type: str) -> bool:
        """
        Check if a file type is supported.

        Args:
            file_type: File type to check

        Returns:
            True if file type is supported
        """
        return file_type.lower() in _STRATEGY_REGISTRY

    @staticmethod
    def register_strategy(
        file_type: str,
        strategy_class: type[TableNormalizer],
    ) -> None:
        """
        Register a new parsing strategy.

        Allows extending the factory with custom strategies.

        Args:
            file_type: File type identifier (e.g., 'csv')
            strategy_class: TableNormalizer subclass

        Example:
            >>> ParserFactory.register_strategy("csv", CsvStrategy)
        """
        _STRATEGY_REGISTRY[file_type.lower()] = strategy_class
        logger.info(
            "Parser strategy registered",
            file_type=file_type,
            strategy=strategy_class.__name__,
        )


def get_parser(file_type: str, **kwargs) -> TableNormalizer:
    """
    Convenience function to get a parser for a file type.

    Args:
        file_type: Type of file to parse
        **kwargs: Arguments for the strategy

    Returns:
        TableNormalizer implementation
    """
    return ParserFactory.create(file_type, **kwargs)


def get_parser_for_file(file_path: str | Path, **kwargs) -> TableNormalizer:
    """
    Convenience function to get a parser based on file extension.

    Args:
        file_path: Path to file
        **kwargs: Arguments for the strategy

    Returns:
        TableNormalizer implementation
    """
    return ParserFactory.from_file_path(file_path, **kwargs)

