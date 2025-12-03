"""
Ingest Package
==============

File parsing strategies and data normalization.

Components:
    - TableNormalizer: Abstract base class for parsing strategies
    - ExcelStrategy: Excel file parser with merged cell support
    - PdfStrategy: PDF table extractor using pymupdf4llm
    - ParserFactory: Factory for selecting parsing strategies
    - Chunker: Converts rows to semantic chunks for embedding
"""

from src.ingest.chunker import Chunker, create_chunk
from src.ingest.excel_strategy import ExcelStrategy
from src.ingest.parser_factory import ParserFactory, get_parser, get_parser_for_file
from src.ingest.pdf_strategy import PdfStrategy
from src.ingest.table_normalizer import (
    ParseResult,
    ParserError,
    TableNormalizer,
)

__all__ = [
    # Base classes
    "TableNormalizer",
    "ParserError",
    "ParseResult",
    # Strategies
    "ExcelStrategy",
    "PdfStrategy",
    # Factory
    "ParserFactory",
    "get_parser",
    "get_parser_for_file",
    # Chunker
    "Chunker",
    "create_chunk",
]
