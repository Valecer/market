"""
Unit Tests for MergerAgent
===========================

Tests LLM-based product matching with mocked dependencies.
Uses patch.object() for proper test isolation.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.rag.merger_agent import LLMMatchResponse, MergerAgent
from src.schemas.domain import MatchResult, SimilarityResult
from src.utils.errors import LLMError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_llm_model = "llama3"
    settings.embedding_dimensions = 768
    settings.match_confidence_auto_threshold = 0.9
    settings.match_confidence_review_threshold = 0.7
    return settings


@pytest.fixture
def mock_session():
    """Create mock async session."""
    return AsyncMock()


@pytest.fixture
def mock_vector_service():
    """Create mock VectorService."""
    service = AsyncMock()
    service.similarity_search_text = AsyncMock(return_value=[])
    service.embed_query = AsyncMock(return_value=[0.1] * 768)
    return service


@pytest.fixture
def sample_candidates():
    """Create sample similarity results."""
    return [
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Energizer AA Battery 24-Pack",
            similarity=0.95,
            characteristics={"brand": "Energizer", "quantity": "24"},
        ),
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Duracell AA Batteries 20-Pack",
            similarity=0.88,
            characteristics={"brand": "Duracell", "quantity": "20"},
        ),
        SimilarityResult(
            supplier_item_id=uuid4(),
            product_id=uuid4(),
            name="Panasonic AAA Battery 16-Pack",
            similarity=0.75,
            characteristics={"brand": "Panasonic", "quantity": "16"},
        ),
    ]


class TestMergerAgentInit:
    """Tests for MergerAgent initialization."""

    def test_init_with_defaults(self, mock_session, mock_settings):
        """Test initialization with default settings."""
        with patch("src.rag.merger_agent.VectorService"), patch(
            "src.rag.merger_agent.ChatOllama"
        ):
            agent = MergerAgent(mock_session, mock_settings)

            assert agent._auto_threshold == 0.9
            assert agent._review_threshold == 0.7

    def test_init_with_custom_vector_service(
        self, mock_session, mock_settings, mock_vector_service
    ):
        """Test initialization with custom VectorService."""
        with patch("src.rag.merger_agent.ChatOllama"):
            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            assert agent._vector_service == mock_vector_service


class TestMergerAgentFindMatches:
    """Tests for find_matches method."""

    @pytest.mark.asyncio
    async def test_find_matches_returns_matches(
        self, mock_session, mock_settings, mock_vector_service, sample_candidates
    ):
        """Test find_matches returns correct matches."""
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        # Mock LLM response
        expected_product_id = sample_candidates[0].product_id
        llm_response = json.dumps([
            {
                "product_id": str(expected_product_id),
                "confidence": 0.95,
                "reasoning": "Both are Energizer AA battery 24-packs",
            }
        ])

        with patch("src.rag.merger_agent.ChatOllama") as mock_llm_class:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = llm_response
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            results = await agent.find_matches(
                item_name="Energizer AA Batteries 24pk",
                item_brand="Energizer",
            )

            assert len(results) == 1
            assert results[0].product_id == expected_product_id
            assert results[0].confidence == 0.95
            mock_vector_service.similarity_search_text.assert_called_once()
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_matches_no_candidates(
        self, mock_session, mock_settings, mock_vector_service
    ):
        """Test find_matches returns empty when no candidates found."""
        mock_vector_service.similarity_search_text.return_value = []

        with patch("src.rag.merger_agent.ChatOllama"):
            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            results = await agent.find_matches(item_name="Unknown Product XYZ")

            assert results == []

    @pytest.mark.asyncio
    async def test_find_matches_empty_llm_response(
        self, mock_session, mock_settings, mock_vector_service, sample_candidates
    ):
        """Test find_matches handles empty LLM response (no matches)."""
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        with patch("src.rag.merger_agent.ChatOllama") as mock_llm_class:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "[]"  # No matches
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            results = await agent.find_matches(item_name="Some Item")

            assert results == []

    @pytest.mark.asyncio
    async def test_find_matches_llm_error_raises(
        self, mock_session, mock_settings, mock_vector_service, sample_candidates
    ):
        """Test find_matches raises LLMError on LLM failure."""
        mock_vector_service.similarity_search_text.return_value = sample_candidates

        with patch("src.rag.merger_agent.ChatOllama") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(
                side_effect=ConnectionError("Ollama not reachable")
            )
            mock_llm_class.return_value = mock_llm

            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            with pytest.raises(LLMError) as exc_info:
                await agent.find_matches(item_name="Test Item")

            assert "LLM call failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_find_matches_excludes_self(
        self, mock_session, mock_settings, mock_vector_service, sample_candidates
    ):
        """Test find_matches excludes the item itself from search."""
        mock_vector_service.similarity_search_text.return_value = sample_candidates
        exclude_id = uuid4()

        with patch("src.rag.merger_agent.ChatOllama") as mock_llm_class:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "[]"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            agent = MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

            await agent.find_matches(
                item_name="Test",
                supplier_item_id=exclude_id,
            )

            # Verify exclusion was passed to vector search
            call_kwargs = mock_vector_service.similarity_search_text.call_args.kwargs
            assert call_kwargs["exclude_item_id"] == exclude_id


class TestMergerAgentParseResponse:
    """Tests for _parse_llm_response method."""

    @pytest.fixture
    def agent(self, mock_session, mock_settings, mock_vector_service):
        """Create agent for parsing tests."""
        with patch("src.rag.merger_agent.ChatOllama"):
            return MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

    def test_parse_valid_json_array(self, agent, sample_candidates):
        """Test parsing valid JSON array."""
        product_id = sample_candidates[0].product_id
        response = json.dumps([
            {
                "product_id": str(product_id),
                "confidence": 0.92,
                "reasoning": "Same product",
            }
        ])

        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        assert len(result.matches) == 1
        assert result.matches[0].product_id == product_id
        assert result.matches[0].confidence == 0.92

    def test_parse_empty_array(self, agent, sample_candidates):
        """Test parsing empty JSON array."""
        response = "[]"
        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        assert len(result.matches) == 0

    def test_parse_markdown_wrapped_json(self, agent, sample_candidates):
        """Test parsing JSON wrapped in markdown code block."""
        product_id = sample_candidates[0].product_id
        response = f"""```json
[
    {{
        "product_id": "{product_id}",
        "confidence": 0.88,
        "reasoning": "Similar product"
    }}
]
```"""

        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        assert len(result.matches) == 1

    def test_parse_invalid_json(self, agent, sample_candidates):
        """Test parsing invalid JSON returns error."""
        response = "This is not JSON"
        result = agent._parse_llm_response(response, sample_candidates)

        assert not result.parse_success
        assert "JSON decode error" in result.error_message

    def test_parse_empty_response(self, agent, sample_candidates):
        """Test parsing empty response."""
        result = agent._parse_llm_response("", sample_candidates)

        assert not result.parse_success
        assert "Empty LLM response" in result.error_message

    def test_parse_clamps_confidence(self, agent, sample_candidates):
        """Test confidence values are clamped to [0, 1]."""
        product_id = sample_candidates[0].product_id
        response = json.dumps([
            {"product_id": str(product_id), "confidence": 1.5, "reasoning": "Test"},
            {"product_id": str(sample_candidates[1].product_id), "confidence": -0.5, "reasoning": "Test"},
        ])

        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        assert result.matches[0].confidence == 1.0  # Clamped from 1.5
        assert result.matches[1].confidence == 0.0  # Clamped from -0.5

    def test_parse_skips_invalid_uuids(self, agent, sample_candidates):
        """Test parsing skips entries with invalid UUIDs."""
        valid_product_id = sample_candidates[0].product_id
        response = json.dumps([
            {"product_id": "invalid-uuid", "confidence": 0.9, "reasoning": "Test"},
            {"product_id": str(valid_product_id), "confidence": 0.85, "reasoning": "Valid"},
        ])

        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        assert len(result.matches) == 1
        assert result.matches[0].product_id == valid_product_id

    def test_parse_enriches_from_candidates(self, agent, sample_candidates):
        """Test parsed results include data from candidates."""
        product_id = sample_candidates[0].product_id
        response = json.dumps([
            {"product_id": str(product_id), "confidence": 0.9, "reasoning": "Match"},
        ])

        result = agent._parse_llm_response(response, sample_candidates)

        assert result.parse_success
        # Should have similarity score from candidate
        assert result.matches[0].similarity_score == 0.95
        assert result.matches[0].product_name == "Energizer AA Battery 24-Pack"


class TestMergerAgentClassifyMatch:
    """Tests for classify_match method."""

    @pytest.fixture
    def agent(self, mock_session, mock_settings, mock_vector_service):
        """Create agent for classification tests."""
        with patch("src.rag.merger_agent.ChatOllama"):
            return MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

    def test_classify_auto_match(self, agent):
        """Test high confidence classified as auto."""
        match = MatchResult(
            product_id=uuid4(),
            product_name="Test",
            confidence=0.95,
            reasoning="Test",
            similarity_score=0.9,
        )
        assert agent.classify_match(match) == "auto"

    def test_classify_review(self, agent):
        """Test medium confidence classified as review."""
        match = MatchResult(
            product_id=uuid4(),
            product_name="Test",
            confidence=0.85,
            reasoning="Test",
            similarity_score=0.8,
        )
        assert agent.classify_match(match) == "review"

    def test_classify_reject(self, agent):
        """Test low confidence classified as reject."""
        match = MatchResult(
            product_id=uuid4(),
            product_name="Test",
            confidence=0.65,
            reasoning="Test",
            similarity_score=0.6,
        )
        assert agent.classify_match(match) == "reject"

    def test_classify_boundary_auto(self, agent):
        """Test exact auto threshold boundary."""
        match = MatchResult(
            product_id=uuid4(),
            product_name="Test",
            confidence=0.9,  # Exactly at threshold
            reasoning="Test",
            similarity_score=0.9,
        )
        assert agent.classify_match(match) == "auto"

    def test_classify_boundary_review(self, agent):
        """Test exact review threshold boundary."""
        match = MatchResult(
            product_id=uuid4(),
            product_name="Test",
            confidence=0.7,  # Exactly at threshold
            reasoning="Test",
            similarity_score=0.7,
        )
        assert agent.classify_match(match) == "review"


class TestMergerAgentFilterByClassification:
    """Tests for filter_by_classification method."""

    @pytest.fixture
    def agent(self, mock_session, mock_settings, mock_vector_service):
        """Create agent for filter tests."""
        with patch("src.rag.merger_agent.ChatOllama"):
            return MergerAgent(
                mock_session,
                mock_settings,
                vector_service=mock_vector_service,
            )

    @pytest.fixture
    def mixed_matches(self):
        """Create matches with different confidence levels."""
        return [
            MatchResult(
                product_id=uuid4(),
                product_name="Auto Match",
                confidence=0.95,
                reasoning="Test",
                similarity_score=0.9,
            ),
            MatchResult(
                product_id=uuid4(),
                product_name="Review Match",
                confidence=0.85,
                reasoning="Test",
                similarity_score=0.8,
            ),
            MatchResult(
                product_id=uuid4(),
                product_name="Another Auto",
                confidence=0.92,
                reasoning="Test",
                similarity_score=0.9,
            ),
            MatchResult(
                product_id=uuid4(),
                product_name="Reject Match",
                confidence=0.5,
                reasoning="Test",
                similarity_score=0.5,
            ),
        ]

    def test_filter_auto_only(self, agent, mixed_matches):
        """Test filtering auto matches only."""
        auto = agent.filter_by_classification(mixed_matches, "auto")
        assert len(auto) == 2
        assert all(m.confidence >= 0.9 for m in auto)

    def test_filter_review_only(self, agent, mixed_matches):
        """Test filtering review matches only."""
        review = agent.filter_by_classification(mixed_matches, "review")
        assert len(review) == 1
        assert all(0.7 <= m.confidence < 0.9 for m in review)

    def test_filter_reject_only(self, agent, mixed_matches):
        """Test filtering rejected matches only."""
        reject = agent.filter_by_classification(mixed_matches, "reject")
        assert len(reject) == 1
        assert all(m.confidence < 0.7 for m in reject)


class TestLLMMatchResponse:
    """Tests for LLMMatchResponse class."""

    def test_has_matches_true(self):
        """Test has_matches returns True when matches exist."""
        response = LLMMatchResponse(
            matches=[MatchResult(
                product_id=uuid4(),
                product_name="Test",
                confidence=0.9,
                reasoning="Test",
                similarity_score=0.8,
            )],
            raw_response="",
        )
        assert response.has_matches

    def test_has_matches_false(self):
        """Test has_matches returns False when no matches."""
        response = LLMMatchResponse(
            matches=[],
            raw_response="",
        )
        assert not response.has_matches

    def test_best_match(self):
        """Test best_match returns highest confidence."""
        matches = [
            MatchResult(
                product_id=uuid4(),
                product_name="Low",
                confidence=0.7,
                reasoning="Test",
                similarity_score=0.7,
            ),
            MatchResult(
                product_id=uuid4(),
                product_name="High",
                confidence=0.95,
                reasoning="Test",
                similarity_score=0.9,
            ),
            MatchResult(
                product_id=uuid4(),
                product_name="Medium",
                confidence=0.85,
                reasoning="Test",
                similarity_score=0.8,
            ),
        ]
        response = LLMMatchResponse(matches=matches, raw_response="")

        assert response.best_match.confidence == 0.95
        assert response.best_match.product_name == "High"

    def test_best_match_none(self):
        """Test best_match returns None when no matches."""
        response = LLMMatchResponse(matches=[], raw_response="")
        assert response.best_match is None


