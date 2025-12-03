"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from enum import Enum
import structlog


class LLMBackendType(str, Enum):
    """Supported LLM backends."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    MOCK = "mock"


class LLMSettings(BaseSettings):
    """LLM configuration for ML-based matching and classification.
    
    All settings prefixed with LLM_ (e.g., LLM_MODEL=llama3.2)
    
    Supported backends:
    - ollama: Local Ollama server (recommended)
    - openai: OpenAI API (requires API key)
    - mock: Mock client for testing
    """
    
    # Backend Configuration
    backend: LLMBackendType = Field(
        default=LLMBackendType.OLLAMA,
        description="LLM backend to use (ollama, openai, mock)"
    )
    
    # Model Configuration
    model: str = Field(
        default="llama3.2",
        description="Model to use. Recommended: llama3.2, qwen2.5:7b (good for Russian)"
    )
    
    # Ollama Configuration
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    
    # OpenAI Configuration (optional)
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (only for openai backend)"
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible API base URL"
    )
    
    # Request Configuration
    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts"
    )
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Model temperature (lower = more deterministic)"
    )
    max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Maximum tokens in response"
    )
    
    # Feature Flags
    enabled: bool = Field(
        default=True,
        description="Enable/disable LLM features globally"
    )
    use_for_headers: bool = Field(
        default=True,
        description="Use LLM for header detection"
    )
    use_for_classification: bool = Field(
        default=True,
        description="Use LLM for product classification"
    )
    use_for_matching: bool = Field(
        default=True,
        description="Use LLM for product matching/similarity"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class MatchingSettings(BaseSettings):
    """Matching pipeline configuration loaded from environment variables.
    
    All settings prefixed with MATCH_ (e.g., MATCH_AUTO_THRESHOLD=95.0)
    """
    
    # Matching Thresholds
    auto_threshold: float = Field(
        default=95.0,
        ge=0,
        le=100,
        description="Score >= this triggers automatic linking (default: 95%)"
    )
    potential_threshold: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Score >= this triggers review queue (default: 70%)"
    )
    
    # Processing Configuration
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of items to process per matching batch"
    )
    max_candidates: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum candidate matches to store for review"
    )
    
    # Review Queue Configuration
    review_expiration_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days until pending review items expire"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="MATCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    database_url: str

    # Redis Configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str
    redis_url: Optional[str] = None

    # Queue Configuration
    queue_name: str = "price-ingestion-queue"
    dlq_name: str = "price-ingestion-dlq"

    # Worker Configuration
    max_workers: int = 5
    job_timeout: int = 300
    log_level: str = "INFO"
    environment: str = "development"

    # Google Sheets Configuration
    google_credentials_path: str = "/app/credentials/google-credentials.json"

    # Sync Scheduler Configuration (Phase 6)
    sync_interval_hours: int = Field(
        default=8,
        ge=1,
        le=168,
        description="Interval between automatic Master Sheet syncs (default: 8 hours)"
    )
    
    # ML-Analyze Integration (Phase 8)
    ml_analyze_url: str = Field(
        default="http://ml-analyze:8001",
        description="URL of the ML-Analyze service for file processing"
    )
    use_ml_processing: bool = Field(
        default=True,
        description="Enable ML-based file processing (set to false for legacy pipeline)"
    )
    ml_poll_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Interval between ML job status polling (seconds)"
    )
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum file size allowed for upload (MB)"
    )
    file_cleanup_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours before uploaded files are cleaned up"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        """Initialize settings and build derived values."""
        super().__init__(**kwargs)
        # Build Redis URL if not provided
        if not self.redis_url:
            self.redis_url = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


# Global settings instances
settings = Settings()
matching_settings = MatchingSettings()
llm_settings = LLMSettings()


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Initialize logging on module import (after settings are loaded)
try:
    configure_logging(settings.log_level)
except Exception:
    # If settings fail to load, use default log level
    configure_logging("INFO")

