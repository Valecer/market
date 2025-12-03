"""
Integration Tests for LLM Matching
===================================

Tests LLM-based product matching with real Ollama API calls.
Requires Ollama to be running with llama3 model.

Run: pytest tests/integration/test_llm_matching.py -v -s
"""

import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.rag.merger_agent import MergerAgent
from src.rag.prompt_templates import MATCH_PROMPT, format_candidates_text, format_item_for_prompt
from src.schemas.domain import SimilarityResult


# Skip if Ollama is not available
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_OLLAMA_TESTS", "true").lower() == "true",
    reason="Ollama integration tests skipped. Set SKIP_OLLAMA_TESTS=false to run.",
)


@pytest.fixture
def ollama_settings():
    """Settings configured for real Ollama."""
    settings = MagicMock()
    settings.ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_llm_model = os.environ.get("OLLAMA_LLM_MODEL", "llama3")
    settings.embedding_dimensions = 768
    settings.match_confidence_auto_threshold = 0.9
    settings.match_confidence_review_threshold = 0.7
    return settings


@pytest.fixture
def mock_session():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_candidates():
    """Create realistic candidates for testing."""
    return [
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Duracell AA Batteries 24-Pack Ultra Power",
            similarity=0.95,
            characteristics={
                "brand": "Duracell",
                "quantity": "24",
                "type": "Alkaline",
                "voltage": "1.5V",
            },
        ),
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Energizer AA Battery 20-Pack Max",
            similarity=0.88,
            characteristics={
                "brand": "Energizer",
                "quantity": "20",
                "type": "Alkaline",
            },
        ),
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Panasonic AAA Batteries 16-Pack",
            similarity=0.72,
            characteristics={
                "brand": "Panasonic",
                "quantity": "16",
                "type": "Alkaline",
                "size": "AAA",
            },
        ),
    ]


class TestOllamaLLMMatching:
    """Integration tests with real Ollama LLM."""

    @pytest.mark.asyncio
    async def test_llm_returns_valid_json(self, ollama_settings, mock_session, sample_candidates):
        """Test that LLM returns valid JSON response."""
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=ollama_settings.ollama_llm_model,
            base_url=ollama_settings.ollama_base_url,
            temperature=0.1,
            format="json",
        )

        # Build prompt
        item_vars = format_item_for_prompt(
            name="Duracell AA Batteries 24 Pack",
            brand="Duracell",
            characteristics={"quantity": "24", "type": "alkaline"},
        )
        item_vars["candidates_text"] = format_candidates_text([
            {
                "product_id": str(sample_candidates[0].product_id),
                "name": sample_candidates[0].name,
                "similarity": sample_candidates[0].similarity,
                "characteristics": sample_candidates[0].characteristics,
            }
        ])
        item_vars["top_k"] = "5"

        messages = MATCH_PROMPT.format_messages(**item_vars)

        # Call LLM
        response = await llm.ainvoke(messages)

        # Verify response
        assert response.content
        assert len(response.content) > 0

        # Should be valid JSON
        import json
        try:
            data = json.loads(response.content)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"LLM response is not valid JSON: {response.content[:200]}")

    @pytest.mark.asyncio
    async def test_llm_identifies_match(self, ollama_settings, mock_session, sample_candidates):
        """Test LLM correctly identifies a matching product."""
        # Create mock vector service that returns our candidates
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = sample_candidates
        mock_vector_service.embed_query.return_value = [0.1] * 768

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        # Test with item very similar to first candidate
        results = await agent.find_matches(
            item_name="Duracell AA Batteries 24-Pack Ultra",
            item_brand="Duracell",
            item_characteristics={"quantity": "24", "type": "Alkaline", "voltage": "1.5V"},
            top_k=3,
        )

        # Should find at least one match
        assert len(results) > 0, "LLM should identify at least one match"

        # Best match should have reasonable confidence
        best = max(results, key=lambda m: m.confidence)
        assert best.confidence >= 0.7, f"Expected confidence >= 0.7, got {best.confidence}"

    @pytest.mark.asyncio
    async def test_llm_rejects_non_match(self, ollama_settings, mock_session):
        """Test LLM correctly rejects non-matching products."""
        # Create candidates that don't match the query
        non_matching_candidates = [
            SimilarityResult(
                supplier_item_id=uuid4(),
                product_id=uuid4(),
                name="Samsung Galaxy S24 Smartphone 256GB",
                similarity=0.45,  # Low similarity
                characteristics={
                    "brand": "Samsung",
                    "storage": "256GB",
                    "type": "Smartphone",
                },
            ),
            SimilarityResult(
                supplier_item_id=uuid4(),
                product_id=uuid4(),
                name="Apple iPhone 15 Pro Max 512GB",
                similarity=0.42,
                characteristics={
                    "brand": "Apple",
                    "storage": "512GB",
                    "type": "Smartphone",
                },
            ),
        ]

        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = non_matching_candidates

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        # Test with completely different item
        results = await agent.find_matches(
            item_name="Logitech MX Master 3S Wireless Mouse",
            item_category="Computer Peripherals",
            item_brand="Logitech",
            top_k=2,
        )

        # Should either return empty or low confidence
        if results:
            best = max(results, key=lambda m: m.confidence)
            assert best.confidence < 0.7, f"Expected confidence < 0.7 for non-match, got {best.confidence}"

    @pytest.mark.asyncio
    async def test_llm_provides_reasoning(self, ollama_settings, mock_session, sample_candidates):
        """Test LLM provides reasoning for matches."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = [sample_candidates[0]]

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        results = await agent.find_matches(
            item_name="Duracell AA Battery Pack 24",
            item_brand="Duracell",
            top_k=1,
        )

        if results:
            # Check that reasoning is provided
            for match in results:
                assert match.reasoning, "Match should include reasoning"
                assert len(match.reasoning) > 5, "Reasoning should be meaningful"


class TestMergerAgentIntegration:
    """Integration tests for MergerAgent with real Ollama."""

    @pytest.mark.asyncio
    async def test_full_matching_pipeline(self, ollama_settings, mock_session, sample_candidates):
        """Test complete matching pipeline end-to-end."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        # Run matching
        results = await agent.find_matches(
            item_name="AA Alkaline Battery 24-Pack",
            item_description="Premium quality alkaline batteries",
            item_category="Batteries",
            item_brand="Duracell",
            item_sku="BAT-AA-24",
            item_characteristics={
                "voltage": "1.5V",
                "quantity": 24,
                "type": "Alkaline",
            },
            top_k=3,
        )

        # Verify results structure
        for match in results:
            assert hasattr(match, "product_id")
            assert hasattr(match, "confidence")
            assert hasattr(match, "reasoning")
            assert 0 <= match.confidence <= 1

    @pytest.mark.asyncio
    async def test_classify_and_filter_matches(self, ollama_settings, mock_session, sample_candidates):
        """Test classification of matches by confidence."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        results = await agent.find_matches(
            item_name="Duracell AA 24-Pack",
            item_brand="Duracell",
            top_k=3,
        )

        # Test classification
        for match in results:
            classification = agent.classify_match(match)
            assert classification in ["auto", "review", "reject"]

        # Test filtering
        auto_matches = agent.filter_by_classification(results, "auto")
        review_matches = agent.filter_by_classification(results, "review")
        reject_matches = agent.filter_by_classification(results, "reject")

        # All matches should be in one category
        total = len(auto_matches) + len(review_matches) + len(reject_matches)
        assert total == len(results)


class TestLLMEdgeCases:
    """Test LLM handling of edge cases."""

    @pytest.mark.asyncio
    async def test_empty_candidates(self, ollama_settings, mock_session):
        """Test handling of empty candidate list."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = []

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        results = await agent.find_matches(
            item_name="Test Product",
            top_k=5,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_unicode_item_names(self, ollama_settings, mock_session, sample_candidates):
        """Test handling of unicode in item names."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        # Test with Russian text
        results = await agent.find_matches(
            item_name="Батарейки Duracell AA 24шт",
            item_brand="Duracell",
            top_k=3,
        )

        # Should not raise and should return valid results
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_long_item_description(self, ollama_settings, mock_session, sample_candidates):
        """Test handling of very long descriptions."""
        mock_vector_service = AsyncMock()
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        agent = MergerAgent(
            mock_session,
            ollama_settings,
            vector_service=mock_vector_service,
        )

        long_description = "Premium quality batteries. " * 100  # Very long

        results = await agent.find_matches(
            item_name="Duracell AA Batteries",
            item_description=long_description,
            top_k=3,
        )

        # Should handle gracefully
        assert isinstance(results, list)


