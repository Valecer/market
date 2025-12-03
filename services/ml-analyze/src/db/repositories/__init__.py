"""
Database Repositories
=====================

Data access layer following repository pattern.

Components:
    - SupplierItemsRepository: CRUD for supplier_items table
    - ParsingLogsRepository: Error logging to parsing_logs table
    - EmbeddingsRepository: CRUD for product_embeddings table
    - MatchReviewRepository: CRUD for match_review_queue table
"""

from src.db.repositories.parsing_logs_repo import ParsingLogsRepository
from src.db.repositories.supplier_items_repo import SupplierItemsRepository
from src.db.repositories.embeddings_repo import EmbeddingsRepository
from src.db.repositories.match_review_repo import MatchReviewRepository

__all__ = [
    "SupplierItemsRepository",
    "ParsingLogsRepository",
    "EmbeddingsRepository",
    "MatchReviewRepository",
]
