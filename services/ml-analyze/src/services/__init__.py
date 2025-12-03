"""
Business Services
=================

Service layer orchestrating business logic.

Components:
    - IngestionService: Orchestrates file parsing pipeline
    - MatchingService: Orchestrates product matching pipeline
"""

from src.services.ingestion_service import IngestionResult, IngestionService, ingest_file
from src.services.matching_service import (
    MatchingService,
    MatchingStats,
    ItemMatchResult,
    match_items,
)

__all__ = [
    # Ingestion
    "IngestionService",
    "IngestionResult",
    "ingest_file",
    # Matching
    "MatchingService",
    "MatchingStats",
    "ItemMatchResult",
    "match_items",
]
