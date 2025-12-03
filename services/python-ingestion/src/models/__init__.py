"""Pydantic validation models."""
from src.models.parsed_item import ParsedSupplierItem
from src.models.queue_message import ParseTaskMessage
from src.models.google_sheets_config import GoogleSheetsConfig
from src.models.file_parser_config import (
    FileParserConfig,
    CsvParserConfig,
    ExcelParserConfig,
)

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
from src.models.extraction import (
    DimensionsCm,
    ExtractedFeatures,
    ExtractionResult,
)

# ML integration models (Phase 8)
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
    # Existing models
    "ParsedSupplierItem",
    "ParseTaskMessage",
    "GoogleSheetsConfig",
    # File parser configs
    "FileParserConfig",
    "CsvParserConfig",
    "ExcelParserConfig",
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
    # Extraction models
    "DimensionsCm",
    "ExtractedFeatures",
    "ExtractionResult",
    # ML integration models (Phase 8)
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

