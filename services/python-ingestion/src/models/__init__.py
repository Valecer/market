"""Pydantic validation models."""
from src.models.parsed_item import ParsedSupplierItem
from src.models.queue_message import ParseTaskMessage
from src.models.google_sheets_config import GoogleSheetsConfig

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

__all__ = [
    # Existing models
    "ParsedSupplierItem",
    "ParseTaskMessage",
    "GoogleSheetsConfig",
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
]

