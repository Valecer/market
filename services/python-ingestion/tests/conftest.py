"""Pytest configuration and fixtures for test suite."""
import os
import pytest
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables before any tests run."""
    # Set required environment variables for Settings
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    os.environ.setdefault("REDIS_PASSWORD", "test_password")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    
    yield
    
    # Cleanup (if needed)
    pass

