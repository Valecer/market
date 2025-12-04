"""Business logic services for the data ingestion pipeline.

Phase 9: Courier pattern - parsing/extraction services removed.
All parsing/extraction now handled by ml-analyze service.

Available Services:
    - matching: Product matching using fuzzy string comparison
    - master_sheet_ingestor: Master Sheet parsing and supplier sync
    - sync_state: Redis sync state management
    - job_state: Redis job state management
    - ml_client: HTTP client for ml-analyze service
    - google_sheets_client: Google Sheets export client (courier pattern)
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
