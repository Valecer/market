"""Pytest configuration and fixtures for test suite.

This is the root-level conftest.py that provides:
- Python path setup (so we can import from src)
- Basic environment variable defaults
- Shared fixtures for all tests

Integration-specific fixtures are in tests/integration/conftest.py
"""
import os
import sys
from pathlib import Path
import pytest

# Add project root to Python path so we can import from src
# This file is at: services/python-ingestion/tests/conftest.py
# Project root is: services/python-ingestion/
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up basic test environment variables before any tests run.
    
    Note: Integration tests override these with specific values in
    tests/integration/conftest.py
    """
    # Set default environment variables (can be overridden by specific test conftest)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    os.environ.setdefault("REDIS_PASSWORD", "test_password")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    
    yield
    
    # Cleanup (if needed)
    pass

