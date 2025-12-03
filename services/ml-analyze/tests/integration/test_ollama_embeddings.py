"""
Integration Tests for Ollama Embeddings
========================================

Tests real Ollama API calls for embedding generation.
Requires Ollama to be running with nomic-embed-text model.

Run with: pytest tests/integration/test_ollama_embeddings.py -v
"""

import asyncio
import os

import pytest
from langchain_ollama import OllamaEmbeddings

# Skip these tests if Ollama is not available
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def check_ollama_available() -> bool:
    """Check if Ollama is available."""
    import httpx

    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


# Skip all tests if Ollama is not available
pytestmark = pytest.mark.skipif(
    not check_ollama_available(),
    reason=f"Ollama not available at {OLLAMA_BASE_URL}",
)


class TestOllamaEmbeddingsIntegration:
    """Integration tests for Ollama embedding generation."""

    @pytest.fixture
    def embeddings(self):
        """Create OllamaEmbeddings instance."""
        return OllamaEmbeddings(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

    @pytest.mark.asyncio
    async def test_embed_single_text(self, embeddings):
        """Test embedding generation for a single text."""
        text = "Батарейка AA Alkaline 1.5V"

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768  # nomic-embed-text produces 768 dimensions
        assert all(isinstance(x, float) for x in result[0])

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self, embeddings):
        """Test embedding generation for multiple texts."""
        texts = [
            "Батарейка AA Alkaline 1.5V",
            "Energizer Battery Pack 24-count",
            "Duracell Plus AA Batteries",
        ]

        result = await embeddings.aembed_documents(texts)

        assert len(result) == 3
        assert all(len(e) == 768 for e in result)

    @pytest.mark.asyncio
    async def test_embedding_similarity(self, embeddings):
        """Test that similar texts have similar embeddings."""
        import numpy as np

        texts = [
            "AA Battery Alkaline",  # Base product
            "AA Alkaline Batteries",  # Similar (same product, different words)
            "Laptop Computer 15 inch",  # Different product
        ]

        result = await embeddings.aembed_documents(texts)

        # Calculate cosine similarities
        def cosine_similarity(a, b):
            a, b = np.array(a), np.array(b)
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        # Similar products should have higher similarity
        sim_batteries = cosine_similarity(result[0], result[1])
        sim_laptop = cosine_similarity(result[0], result[2])

        assert sim_batteries > sim_laptop, (
            f"Similar products should have higher similarity: "
            f"batteries={sim_batteries:.3f}, laptop={sim_laptop:.3f}"
        )

    @pytest.mark.asyncio
    async def test_embedding_deterministic(self, embeddings):
        """Test that same text produces consistent embeddings."""
        import numpy as np

        text = "Test product description"

        result1 = await embeddings.aembed_documents([text])
        result2 = await embeddings.aembed_documents([text])

        # Embeddings should be identical (or very close)
        np.testing.assert_array_almost_equal(
            result1[0], result2[0], decimal=5,
            err_msg="Same text should produce identical embeddings"
        )

    @pytest.mark.asyncio
    async def test_embedding_unicode_text(self, embeddings):
        """Test embedding generation for Unicode text (Russian)."""
        text = "Батарейка AA щелочная алкалиновая"

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_embedding_long_text(self, embeddings):
        """Test embedding generation for longer text."""
        text = (
            "This is a long product description that contains multiple sentences. "
            "It describes a product with many features and characteristics. "
            "The product is designed for professional use in various industries. "
            "It comes with a warranty and free technical support. "
            "The dimensions are 10x20x30 cm and the weight is 500 grams."
        )

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_embedding_normalized(self, embeddings):
        """Test that embeddings are L2-normalized (unit vectors)."""
        import numpy as np

        text = "Test product"
        result = await embeddings.aembed_documents([text])

        # Calculate L2 norm
        norm = np.linalg.norm(result[0])

        # nomic-embed-text should return normalized vectors (norm ≈ 1)
        # Allow some tolerance
        assert 0.99 < norm < 1.01, f"Embedding norm should be ~1, got {norm}"


class TestOllamaEmbeddingsPerformance:
    """Performance tests for Ollama embeddings."""

    @pytest.fixture
    def embeddings(self):
        """Create OllamaEmbeddings instance."""
        return OllamaEmbeddings(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

    @pytest.mark.asyncio
    async def test_single_embedding_latency(self, embeddings):
        """Test that single embedding takes reasonable time."""
        import time

        text = "Product description for testing"

        start = time.perf_counter()
        await embeddings.aembed_documents([text])
        latency = (time.perf_counter() - start) * 1000

        # Should complete in under 5 seconds (generous for cold start)
        assert latency < 5000, f"Embedding took too long: {latency:.0f}ms"
        print(f"Single embedding latency: {latency:.0f}ms")

    @pytest.mark.asyncio
    async def test_batch_embedding_latency(self, embeddings):
        """Test batch embedding performance."""
        import time

        texts = [f"Product {i} description" for i in range(10)]

        start = time.perf_counter()
        results = await embeddings.aembed_documents(texts)
        total_time = (time.perf_counter() - start) * 1000

        assert len(results) == 10

        # 10 embeddings should complete in under 30 seconds
        assert total_time < 30000, f"Batch took too long: {total_time:.0f}ms"

        avg_time = total_time / len(texts)
        print(f"Batch of 10: total={total_time:.0f}ms, avg={avg_time:.0f}ms/item")


class TestOllamaEmbeddingsEdgeCases:
    """Edge case tests for Ollama embeddings."""

    @pytest.fixture
    def embeddings(self):
        """Create OllamaEmbeddings instance."""
        return OllamaEmbeddings(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

    @pytest.mark.asyncio
    async def test_embed_special_characters(self, embeddings):
        """Test embedding text with special characters."""
        text = "Product™ with special chars: €100, 50°C, ~2.5kg"

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_embed_numbers(self, embeddings):
        """Test embedding numeric text."""
        text = "Price: 199.99 SKU: 12345678 Qty: 24"

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_embed_mixed_language(self, embeddings):
        """Test embedding mixed language text."""
        text = "Battery батарейка Batterie pile"

        result = await embeddings.aembed_documents([text])

        assert len(result) == 1
        assert len(result[0]) == 768

