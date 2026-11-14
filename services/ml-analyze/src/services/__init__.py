"""
Business Services
=================

Service layer orchestrating business logic.

Components:
    - IngestionService: Orchestrates file parsing pipeline
    - MatchingService: Orchestrates product matching pipeline
    - AutoCreationService: Auto-creates products for low-confidence matches (Phase 11)
    - DuplicateDetectionService: Detects potential duplicate products (Phase 11)
    - CategoryHierarchyService: Enforces 3-level category hierarchy (Phase 11 US3)
    - IngestionOrchestrator: Orchestrates post-ingestion workflows (Phase 11 US4)
"""

from src.services.ingestion_service import IngestionResult, IngestionService, ingest_file
from src.services.matching_service import (
    MatchingService,
    MatchingStats,
    ItemMatchResult,
    match_items,
)
from src.services.auto_creation_service import (
    AutoCreationService,
    AutoCreationStats,
    auto_create_product,
)
from src.services.duplicate_detection_service import (
    DuplicateDetectionService,
    detect_duplicates,
)
from src.services.category_hierarchy_service import (
    CategoryHierarchyService,
    CategoryLevelResult,
    HierarchyEnforcementResult,
)
from src.services.ingestion_orchestrator import (
    IngestionOrchestrator,
    VariantDetectionStats,
    run_variant_detection,
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
    # Auto-Creation (Phase 11)
    "AutoCreationService",
    "AutoCreationStats",
    "auto_create_product",
    # Duplicate Detection (Phase 11)
    "DuplicateDetectionService",
    "detect_duplicates",
    # Category Hierarchy (Phase 11 US3)
    "CategoryHierarchyService",
    "CategoryLevelResult",
    "HierarchyEnforcementResult",
    # Ingestion Orchestrator (Phase 11 US4)
    "IngestionOrchestrator",
    "VariantDetectionStats",
    "run_variant_detection",
]
