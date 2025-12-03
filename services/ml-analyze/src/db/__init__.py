"""
Database Package
================

Database models, connection management, and repositories.
"""

from src.db.connection import (
    DatabaseManager,
    close_database,
    get_session,
    health_check,
    init_database,
)
from src.db.models import Base, ProductEmbedding, TimestampMixin, UUIDMixin

__all__ = [
    # Models
    "Base",
    "ProductEmbedding",
    "UUIDMixin",
    "TimestampMixin",
    # Connection
    "DatabaseManager",
    "init_database",
    "close_database",
    "get_session",
    "health_check",
]
