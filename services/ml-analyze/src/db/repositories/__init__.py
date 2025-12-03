"""
Database Repositories
=====================

Data access layer following repository pattern.

Components:
    - SupplierItemsRepository: CRUD for supplier_items table
    - ParsingLogsRepository: Error logging to parsing_logs table
"""

from src.db.repositories.parsing_logs_repo import ParsingLogsRepository
from src.db.repositories.supplier_items_repo import SupplierItemsRepository

__all__ = [
    "SupplierItemsRepository",
    "ParsingLogsRepository",
]
