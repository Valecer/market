"""
Ingest Package
==============

File parsing strategies and data normalization.
"""

from src.ingest.table_normalizer import (
    ParseResult,
    ParserError,
    TableNormalizer,
)

__all__ = [
    "TableNormalizer",
    "ParserError",
    "ParseResult",
]
