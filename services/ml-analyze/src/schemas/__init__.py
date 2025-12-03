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
]
