"""
Schemas Package
===============

Pydantic models for API requests, responses, and domain objects.
"""

from src.schemas.domain import (
    ChunkData,
    FileAnalysisJob,
    MatchJob,
    MatchResult,
    NormalizedRow,
    ProductEmbeddingData,
    SimilarityResult,
)
from src.schemas.requests import (
    BatchMatchRequest,
    EmbeddingRequest,
    FileAnalysisRequest,
    SimilaritySearchRequest,
    VisionAnalysisRequest,
)
from src.schemas.responses import (
    BatchMatchResponse,
    ErrorResponse,
    FileAnalysisResponse,
    HealthCheckResponse,
    JobStatusResponse,
    VisionAnalysisResponse,
)

# Phase 9: Semantic ETL schemas
from src.schemas.extraction import (
    ChunkExtractionResult,
    ExtractedProduct,
    ExtractionError,
    ExtractionResult,
    LLMExtractionResponse,
)
from src.schemas.category import (
    CategoryApprovalRequest,
    CategoryApprovalResponse,
    CategoryDTO,
    CategoryHierarchyResult,
    CategoryMatchResult,
    CategoryNormalizationStats,
    CategoryReviewItem,
)
from src.schemas.duplicate import (
    DuplicateDetectionStats,
    PotentialDuplicateCreate,
    PotentialDuplicateResponse,
)

__all__ = [
    # Domain models
    "NormalizedRow",
    "MatchResult",
    "ProductEmbeddingData",
    "SimilarityResult",
    "ChunkData",
    "FileAnalysisJob",
    "MatchJob",
    # Request models
    "FileAnalysisRequest",
    "BatchMatchRequest",
    "VisionAnalysisRequest",
    "EmbeddingRequest",
    "SimilaritySearchRequest",
    # Response models
    "FileAnalysisResponse",
    "JobStatusResponse",
    "HealthCheckResponse",
    "BatchMatchResponse",
    "VisionAnalysisResponse",
    "ErrorResponse",
    # Phase 9: Extraction schemas
    "ExtractedProduct",
    "ExtractionError",
    "ExtractionResult",
    "ChunkExtractionResult",
    "LLMExtractionResponse",
    # Phase 9: Category schemas
    "CategoryMatchResult",
    "CategoryHierarchyResult",
    "CategoryDTO",
    "CategoryReviewItem",
    "CategoryApprovalRequest",
    "CategoryApprovalResponse",
    "CategoryNormalizationStats",
    # Phase 11: Duplicate detection schemas
    "PotentialDuplicateCreate",
    "PotentialDuplicateResponse",
    "DuplicateDetectionStats",
]
