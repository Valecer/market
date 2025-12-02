"""
Test Configuration and Fixtures
================================

Shared pytest fixtures for ml-analyze tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application."""
    from src.api.main import app

    return TestClient(app)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.redis_password = "test"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_llm_model = "llama3"
    settings.embedding_dimensions = 768
    settings.match_confidence_auto_threshold = 0.9
    settings.match_confidence_review_threshold = 0.7
    settings.is_development = True
    settings.is_production = False
    return settings


@pytest.fixture
def mock_ollama_embeddings():
    """Create mock Ollama embeddings response."""
    return [0.1] * 768  # 768-dimensional vector


@pytest.fixture
def mock_ollama_client():
    """Create mock Ollama client."""
    client = AsyncMock()
    client.embed = AsyncMock(return_value={"embedding": [0.1] * 768})
    return client


@pytest.fixture
def sample_normalized_row():
    """Create a sample normalized row for testing."""
    return {
        "name": "Energizer AA Batteries 24-Pack",
        "description": "Alkaline batteries, long-lasting power",
        "price": 19.99,
        "sku": "EN-AA-24",
        "category": "Batteries",
        "characteristics": {
            "brand": "Energizer",
            "quantity": 24,
            "type": "Alkaline",
        },
    }


@pytest.fixture
def sample_match_result():
    """Create a sample match result for testing."""
    from uuid import uuid4

    return {
        "product_id": str(uuid4()),
        "confidence": 0.95,
        "reasoning": "Both are Energizer AA 24-packs with identical specifications",
        "similarity_score": 0.92,
    }

