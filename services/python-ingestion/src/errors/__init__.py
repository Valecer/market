"""Error handling module."""
from src.errors.exceptions import (
    DataIngestionError,
    ParserError,
    ValidationError,
    DatabaseError,
)

__all__ = [
    "DataIngestionError",
    "ParserError",
    "ValidationError",
    "DatabaseError",
]

