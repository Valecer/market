"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import structlog


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


# Global settings instance
settings = Settings()


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

