"""Pydantic validation models.

Phase 9: Courier pattern - parsing models removed.
All parsing/extraction now handled by ml-analyze service.
"""

# Master sync pipeline models
from src.models.master_sheet_config import (
    SourceFormat,
    SupplierConfigRow,
    MasterSheetConfig,
    MasterSyncResult,
)
from src.models.sync_messages import (
    SyncState,
    TriggerMasterSyncMessage,
    SyncStatusMessage,
    SyncProgressUpdate,
    SyncCompletedMessage,
)

# Matching pipeline models
from src.models.matching import (
    MatchStatusEnum,
    MatchCandidate,
    MatchResult,
    MatchItemsTaskMessage,
    EnrichItemTaskMessage,
    RecalcAggregatesTaskMessage,
    ManualMatchEventMessage,
)
from src.models.review_queue import (
    ReviewStatusEnum,
    CandidateProduct,
    ReviewQueueItem,
    ReviewAction,
    ReviewQueueStats,
    ReviewQueueFilter,
)

# ML integration models (Phase 8/9)
from src.models.ml_models import (
    FileType,
    SourceType as MLSourceType,
    JobStatus,
    JobPhase,
    MLAnalyzeRequest,
    MLAnalyzeResponse,
    MLJobStatus,
    JobProgressUpdate,
    FileMetadata,
    DownloadTaskMessage,
)

__all__ = [
    # Master sync models
    "SourceFormat",
    "SupplierConfigRow",
    "MasterSheetConfig",
    "MasterSyncResult",
    "SyncState",
    "TriggerMasterSyncMessage",
    "SyncStatusMessage",
    "SyncProgressUpdate",
    "SyncCompletedMessage",
    # Matching models
    "MatchStatusEnum",
    "MatchCandidate",
    "MatchResult",
    "MatchItemsTaskMessage",
    "EnrichItemTaskMessage",
    "RecalcAggregatesTaskMessage",
    "ManualMatchEventMessage",
    # Review queue models
    "ReviewStatusEnum",
    "CandidateProduct",
    "ReviewQueueItem",
    "ReviewAction",
    "ReviewQueueStats",
    "ReviewQueueFilter",
    # ML integration models (Phase 8/9)
    "FileType",
    "MLSourceType",
    "JobStatus",
    "JobPhase",
    "MLAnalyzeRequest",
    "MLAnalyzeResponse",
    "MLJobStatus",
    "JobProgressUpdate",
    "FileMetadata",
    "DownloadTaskMessage",
]
