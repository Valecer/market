"""
Settings Configuration
======================

Environment variable management using pydantic-settings.
Follows the 12-factor app methodology.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Server Configuration
    # -------------------------------------------------------------------------
    fastapi_host: str = Field(default="0.0.0.0", description="Server host")
    fastapi_port: int = Field(default=8001, description="Server port")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment"
    )

    # -------------------------------------------------------------------------
    # Database Configuration
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel",
        description="PostgreSQL connection string (async driver)",
    )
    db_pool_min: int = Field(default=2, ge=1, description="Minimum connection pool size")
    db_pool_max: int = Field(default=10, ge=1, description="Maximum connection pool size")

    # -------------------------------------------------------------------------
    # Redis Configuration
    # -------------------------------------------------------------------------
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    redis_password: str = Field(default="dev_redis_password", description="Redis password")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database number")

    # -------------------------------------------------------------------------
    # Ollama Configuration (Local LLM)
    # -------------------------------------------------------------------------
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama API base URL"
    )
    ollama_embedding_model: str = Field(
        default="nomic-embed-text", description="Embedding model name"
    )
    ollama_llm_model: str = Field(default="llama3", description="LLM model name")
    embedding_dimensions: int = Field(
        default=768, ge=64, le=4096, description="Vector embedding dimensions"
    )

    # -------------------------------------------------------------------------
    # Cloud LLM Configuration (Optional Fallback)
    # -------------------------------------------------------------------------
    cloud_llm_provider: str | None = Field(
        default=None, description="Cloud LLM provider (openai, anthropic)"
    )
    cloud_llm_api_key: str | None = Field(
        default=None, description="Cloud LLM API key"
    )

    # -------------------------------------------------------------------------
    # Matching Configuration
    # -------------------------------------------------------------------------
    match_confidence_auto_threshold: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Auto-match threshold"
    )
    match_confidence_review_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Review queue threshold"
    )

    # -------------------------------------------------------------------------
    # Worker Configuration
    # -------------------------------------------------------------------------
    max_workers: int = Field(default=5, ge=1, le=50, description="Max concurrent workers")
    job_timeout: int = Field(default=600, ge=60, description="Job timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max job retry attempts")

    # -------------------------------------------------------------------------
    # File Upload Configuration
    # -------------------------------------------------------------------------
    uploads_dir: str = Field(default="/shared/uploads", description="Upload directory")
    max_file_size_mb: int = Field(default=50, ge=1, le=500, description="Max file size in MB")

    # -------------------------------------------------------------------------
    # pgvector Configuration
    # -------------------------------------------------------------------------
    vector_index_lists: int = Field(
        default=100, ge=10, description="IVFFLAT index lists parameter"
    )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses lru_cache to ensure settings are only loaded once
    and reused across the application.
    """
    return Settings()

