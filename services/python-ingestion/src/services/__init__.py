"""Business logic services for the data ingestion pipeline.

Available Services:
    - matching: Product matching using fuzzy string comparison
    - aggregation: Product aggregate calculations (min_price, availability)
    - master_sheet_ingestor: Master Sheet parsing and supplier sync
    - sync_state: Redis sync state management
"""
from src.services.matching import (
    RapidFuzzMatcher,
    MatcherStrategy,
    MatchCandidate,
    MatchResult,
    MatchStatusEnum,
    create_matcher,
    search_match_candidates,
)
from src.services.aggregation import (
    calculate_product_aggregates,
    calculate_product_aggregates_batch,
    get_review_queue_stats,
)
from src.services.master_sheet_ingestor import MasterSheetIngestor
from src.services.sync_state import (
    acquire_sync_lock,
    release_sync_lock,
    get_sync_status,
    update_sync_status,
    update_sync_progress,
    set_sync_started,
    set_sync_processing_suppliers,
    set_sync_idle,
    record_sync_completion,
    get_last_sync_at,
    check_sync_lock,
)

__all__: list[str] = [
    # Matching
    "RapidFuzzMatcher",
    "MatcherStrategy",
    "MatchCandidate",
    "MatchResult",
    "MatchStatusEnum",
    "create_matcher",
    "search_match_candidates",
    # Aggregation
    "calculate_product_aggregates",
    "calculate_product_aggregates_batch",
    "get_review_queue_stats",
    # Master Sheet Ingestor
    "MasterSheetIngestor",
    # Sync State
    "acquire_sync_lock",
    "release_sync_lock",
    "get_sync_status",
    "update_sync_status",
    "update_sync_progress",
    "set_sync_started",
    "set_sync_processing_suppliers",
    "set_sync_idle",
    "record_sync_completion",
    "get_last_sync_at",
    "check_sync_lock",
]

