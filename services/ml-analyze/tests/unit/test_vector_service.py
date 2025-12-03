"""
Unit Tests for VectorService
=============================

Tests embedding generation and similarity search with mocked dependencies.
Uses patch.object() for proper test isolation.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.rag.vector_service import VectorService
from src.schemas.domain import SimilarityResult
from src.utils.errors import EmbeddingError


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.embedding_dimensions = 768
    return settings


@pytest.fixture
def mock_session():
    """Create mock async session."""
    return AsyncMock()


@pytest.fixture
def mock_embedding_768():
    """Create a valid 768-dimensional embedding."""
    return [0.1] * 768


@pytest.fixture
def mock_embeddings_repo():
    """Create mock embeddings repository."""
    repo = AsyncMock()
    repo.insert = AsyncMock(return_value=uuid4())
    repo.search_similar = AsyncMock(return_value=[])
    repo.search_by_product_id = AsyncMock(return_value=[])
    repo.exists = AsyncMock(return_value=False)
    repo.delete_by_supplier_item_id = AsyncMock(return_value=1)
    repo.count_by_model = AsyncMock(return_value=100)
    return repo


class TestVectorServiceEmbedQuery:
    """Tests for embed_query method."""

    @pytest.mark.asyncio
    async def test_embed_query_success(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test successful embedding generation."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            # Setup mock
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            service = VectorService(mock_session, mock_settings)
            result = await service.embed_query("Test product description")

            # Verify
            assert len(result) == 768
            assert result == mock_embedding_768
            mock_ollama.aembed_documents.assert_called_once_with(
                ["Test product description"]
            )

    @pytest.mark.asyncio
    async def test_embed_query_empty_text_raises_error(
        self, mock_session, mock_settings
    ):
        """Test that empty text raises EmbeddingError."""
        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            service = VectorService(mock_session, mock_settings)

            with pytest.raises(EmbeddingError) as exc_info:
                await service.embed_query("")

            assert "Cannot embed empty text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_query_whitespace_only_raises_error(
        self, mock_session, mock_settings
    ):
        """Test that whitespace-only text raises EmbeddingError."""
        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            service = VectorService(mock_session, mock_settings)

            with pytest.raises(EmbeddingError):
                await service.embed_query("   \n\t  ")

    @pytest.mark.asyncio
    async def test_embed_query_wrong_dimensions_raises_error(
        self, mock_session, mock_settings
    ):
        """Test that wrong embedding dimensions raises EmbeddingError."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            mock_ollama = MagicMock()
            # Return wrong dimensions (512 instead of 768)
            mock_ollama.aembed_documents = AsyncMock(return_value=[[0.1] * 512])
            mock_ollama_class.return_value = mock_ollama

            service = VectorService(mock_session, mock_settings)

            with pytest.raises(EmbeddingError) as exc_info:
                await service.embed_query("Test")

            assert "Unexpected embedding dimensions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_embed_query_ollama_error_wrapped(
        self, mock_session, mock_settings
    ):
        """Test that Ollama errors are wrapped in EmbeddingError."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                side_effect=ConnectionError("Ollama not reachable")
            )
            mock_ollama_class.return_value = mock_ollama

            service = VectorService(mock_session, mock_settings)

            with pytest.raises(EmbeddingError) as exc_info:
                await service.embed_query("Test")

            assert "Failed to generate embedding" in str(exc_info.value)


class TestVectorServiceEmbedBatch:
    """Tests for embed_batch method."""

    @pytest.mark.asyncio
    async def test_embed_batch_success(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test successful batch embedding generation."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            service = VectorService(mock_session, mock_settings)
            texts = ["Product A", "Product B", "Product C"]
            result = await service.embed_batch(texts)

            assert len(result) == 3
            assert all(len(e) == 768 for e in result)

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self, mock_session, mock_settings):
        """Test batch embedding with empty list."""
        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            service = VectorService(mock_session, mock_settings)
            result = await service.embed_batch([])

            assert result == []

    @pytest.mark.asyncio
    async def test_embed_batch_skips_empty_texts(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test that batch embedding skips empty texts."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ):
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            service = VectorService(mock_session, mock_settings)
            texts = ["Product A", "", "Product C"]
            result = await service.embed_batch(texts)

            # Should have 3 results, but empty text should have empty embedding
            assert len(result) == 3
            assert len(result[0]) == 768
            assert result[1] == []  # Empty text
            assert len(result[2]) == 768


class TestVectorServiceSimilaritySearch:
    """Tests for similarity_search method."""

    @pytest.mark.asyncio
    async def test_similarity_search_success(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test successful similarity search."""
        item_id = uuid4()
        expected_results = [
            SimilarityResult(
                supplier_item_id=item_id,
                product_id=uuid4(),
                name="Similar Product",
                similarity=0.92,
                characteristics={"brand": "TestBrand"},
            )
        ]

        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.search_similar = AsyncMock(return_value=expected_results)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            results = await service.similarity_search(
                query_embedding=mock_embedding_768, top_k=5
            )

            assert len(results) == 1
            assert results[0].name == "Similar Product"
            assert results[0].similarity == 0.92
            mock_repo.search_similar.assert_called_once()

    @pytest.mark.asyncio
    async def test_similarity_search_with_exclusion(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test similarity search with item exclusion."""
        exclude_id = uuid4()

        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.search_similar = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            await service.similarity_search(
                query_embedding=mock_embedding_768,
                top_k=5,
                exclude_item_id=exclude_id,
            )

            # Verify exclusion was passed
            call_kwargs = mock_repo.search_similar.call_args.kwargs
            assert call_kwargs["exclude_item_id"] == exclude_id


class TestVectorServiceSimilaritySearchText:
    """Tests for similarity_search_text method."""

    @pytest.mark.asyncio
    async def test_similarity_search_text_combines_operations(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test that similarity_search_text embeds and searches."""
        item_id = uuid4()
        expected_results = [
            SimilarityResult(
                supplier_item_id=item_id,
                product_id=None,
                name="Found Product",
                similarity=0.88,
                characteristics={},
            )
        ]

        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            mock_repo = AsyncMock()
            mock_repo.search_similar = AsyncMock(return_value=expected_results)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            results = await service.similarity_search_text(
                query_text="Search query", top_k=3
            )

            assert len(results) == 1
            assert results[0].name == "Found Product"
            # Verify both embedding and search were called
            mock_ollama.aembed_documents.assert_called_once()
            mock_repo.search_similar.assert_called_once()


class TestVectorServiceStoreEmbedding:
    """Tests for store_embedding method."""

    @pytest.mark.asyncio
    async def test_store_embedding_success(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test successful embedding storage."""
        item_id = uuid4()
        expected_embedding_id = uuid4()

        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.insert = AsyncMock(return_value=expected_embedding_id)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            result = await service.store_embedding(item_id, mock_embedding_768)

            assert result == expected_embedding_id
            mock_repo.insert.assert_called_once_with(
                supplier_item_id=item_id,
                embedding=mock_embedding_768,
                model_name="nomic-embed-text",
            )


class TestVectorServiceEmbedAndStore:
    """Tests for embed_and_store method."""

    @pytest.mark.asyncio
    async def test_embed_and_store_success(self, mock_session, mock_settings):
        """Test combined embed and store operation."""
        item_id = uuid4()
        expected_embedding_id = uuid4()
        mock_embedding = [0.1] * 768

        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(return_value=[mock_embedding])
            mock_ollama_class.return_value = mock_ollama

            mock_repo = AsyncMock()
            mock_repo.insert = AsyncMock(return_value=expected_embedding_id)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            result = await service.embed_and_store(item_id, "Product text")

            assert result == expected_embedding_id


class TestVectorServiceHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test health check when all systems healthy."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            mock_repo = AsyncMock()
            mock_repo.count_by_model = AsyncMock(return_value=50)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            health = await service.health_check()

            assert health["status"] == "healthy"
            assert health["checks"]["ollama"]["status"] == "healthy"
            assert health["checks"]["database"]["status"] == "healthy"
            assert health["checks"]["database"]["embedding_count"] == 50

    @pytest.mark.asyncio
    async def test_health_check_ollama_unhealthy(self, mock_session, mock_settings):
        """Test health check when Ollama is unhealthy."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                side_effect=ConnectionError("Ollama down")
            )
            mock_ollama_class.return_value = mock_ollama

            mock_repo = AsyncMock()
            mock_repo.count_by_model = AsyncMock(return_value=50)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            health = await service.health_check()

            assert health["status"] == "unhealthy"
            assert health["checks"]["ollama"]["status"] == "unhealthy"
            assert "error" in health["checks"]["ollama"]

    @pytest.mark.asyncio
    async def test_health_check_database_unhealthy(
        self, mock_session, mock_settings, mock_embedding_768
    ):
        """Test health check when database is unhealthy."""
        with patch(
            "src.rag.vector_service.OllamaEmbeddings"
        ) as mock_ollama_class, patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_ollama = MagicMock()
            mock_ollama.aembed_documents = AsyncMock(
                return_value=[mock_embedding_768]
            )
            mock_ollama_class.return_value = mock_ollama

            mock_repo = AsyncMock()
            mock_repo.count_by_model = AsyncMock(
                side_effect=Exception("Database error")
            )
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            health = await service.health_check()

            assert health["status"] == "unhealthy"
            assert health["checks"]["ollama"]["status"] == "healthy"
            assert health["checks"]["database"]["status"] == "unhealthy"


class TestVectorServiceUtilityMethods:
    """Tests for utility methods."""

    @pytest.mark.asyncio
    async def test_has_embedding(self, mock_session, mock_settings):
        """Test has_embedding method."""
        item_id = uuid4()

        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.exists = AsyncMock(return_value=True)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            result = await service.has_embedding(item_id)

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_embedding(self, mock_session, mock_settings):
        """Test delete_embedding method."""
        item_id = uuid4()

        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.delete_by_supplier_item_id = AsyncMock(return_value=1)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            result = await service.delete_embedding(item_id)

            assert result == 1

    @pytest.mark.asyncio
    async def test_get_embedding_count(self, mock_session, mock_settings):
        """Test get_embedding_count method."""
        with patch("src.rag.vector_service.OllamaEmbeddings"), patch(
            "src.rag.vector_service.EmbeddingsRepository"
        ) as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.count_by_model = AsyncMock(return_value=250)
            mock_repo_class.return_value = mock_repo

            service = VectorService(mock_session, mock_settings)
            result = await service.get_embedding_count()

            assert result == 250

