"""
Vector Service
===============

Service for generating embeddings and performing similarity search.
Uses Ollama for embedding generation and pgvector for vector storage/search.

Follows:
- Single Responsibility: Only handles embeddings and similarity search
- Dependency Inversion: Depends on abstractions (EmbeddingsRepository)
- Open/Closed: Can extend embedding providers without modification
"""

from typing import Any
from uuid import UUID

from langchain_ollama import OllamaEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.db.repositories.embeddings_repo import EmbeddingsRepository
from src.schemas.domain import SimilarityResult
from src.utils.errors import EmbeddingError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VectorService:
    """
    Service for vector embedding operations.

    Handles:
    - Generating embeddings using Ollama (nomic-embed-text model)
    - Storing embeddings in pgvector
    - Performing similarity search for product matching

    Architecture:
        VectorService → OllamaEmbeddings (LangChain) → Ollama API
                     → EmbeddingsRepository → PostgreSQL + pgvector

    Usage:
        async with DatabaseManager.get_session() as session:
            service = VectorService(session)
            embedding = await service.embed_query("Product name")
            similar = await service.similarity_search(embedding, top_k=5)
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize VectorService.

        Args:
            session: SQLAlchemy async session
            settings: Application settings (uses default if not provided)
        """
        self._session = session
        self._settings = settings or get_settings()
        self._embeddings_repo = EmbeddingsRepository(session)

        # Initialize LangChain Ollama Embeddings
        self._embeddings = OllamaEmbeddings(
            model=self._settings.ollama_embedding_model,
            base_url=self._settings.ollama_base_url,
        )

        self._embedding_dimensions = self._settings.embedding_dimensions
        self._model_name = self._settings.ollama_embedding_model

        logger.debug(
            "VectorService initialized",
            model=self._model_name,
            dimensions=self._embedding_dimensions,
            ollama_url=self._settings.ollama_base_url,
        )

    async def embed_query(self, text: str) -> list[float]:
        """
        Generate embedding for a single text query.

        Uses Ollama's nomic-embed-text model via LangChain.
        Returns a 768-dimensional normalized vector.

        Args:
            text: Text to embed

        Returns:
            768-dimensional float vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not text or not text.strip():
            raise EmbeddingError(
                message="Cannot embed empty text",
                details={"text": text},
            )

        try:
            logger.debug("Generating embedding", text_length=len(text))

            # LangChain OllamaEmbeddings.embed_query is synchronous
            # Run in executor to avoid blocking
            embedding = await self._embed_text_async(text)

            # Validate dimensions
            if len(embedding) != self._embedding_dimensions:
                raise EmbeddingError(
                    message=f"Unexpected embedding dimensions: {len(embedding)}",
                    details={
                        "expected": self._embedding_dimensions,
                        "actual": len(embedding),
                    },
                )

            logger.debug(
                "Embedding generated",
                dimensions=len(embedding),
                text_preview=text[:50],
            )
            return embedding

        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(
                "Embedding generation failed",
                error=str(e),
                text_preview=text[:50] if text else None,
            )
            raise EmbeddingError(
                message="Failed to generate embedding",
                details={"error": str(e), "text_preview": text[:50] if text else None},
            ) from e

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Processes texts in batch for efficiency.

        Args:
            texts: List of texts to embed

        Returns:
            List of 768-dimensional float vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not texts:
            return []

        try:
            logger.info("Generating batch embeddings", count=len(texts))

            embeddings = []
            for text in texts:
                if text and text.strip():
                    embedding = await self._embed_text_async(text)
                    embeddings.append(embedding)
                else:
                    # Skip empty texts, but track for error reporting
                    logger.warning("Skipping empty text in batch")
                    embeddings.append([])

            valid_count = sum(1 for e in embeddings if e)
            logger.info(
                "Batch embeddings generated",
                total=len(texts),
                valid=valid_count,
            )
            return embeddings

        except Exception as e:
            logger.error("Batch embedding failed", error=str(e))
            raise EmbeddingError(
                message="Failed to generate batch embeddings",
                details={"error": str(e), "batch_size": len(texts)},
            ) from e

    async def _embed_text_async(self, text: str) -> list[float]:
        """
        Async wrapper for LangChain embedding.

        LangChain's embed_query is synchronous, so we use
        aembed_query when available, or run in executor.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Use LangChain's async embed method
        embeddings = await self._embeddings.aembed_documents([text])
        return embeddings[0] if embeddings else []

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        exclude_item_id: UUID | None = None,
    ) -> list[SimilarityResult]:
        """
        Search for similar items using cosine similarity.

        Uses pgvector's cosine distance operator for efficient search.
        Results are sorted by similarity (highest first).

        Args:
            query_embedding: 768-dimensional query vector
            top_k: Number of results to return (default: 5)
            exclude_item_id: Optional item ID to exclude from results

        Returns:
            List of SimilarityResult sorted by similarity (0-1, higher = more similar)
        """
        logger.debug(
            "Performing similarity search",
            top_k=top_k,
            exclude_item=str(exclude_item_id) if exclude_item_id else None,
        )

        results = await self._embeddings_repo.search_similar(
            query_embedding=query_embedding,
            top_k=top_k,
            model_name=self._model_name,
            exclude_item_id=exclude_item_id,
        )

        logger.debug("Similarity search completed", results_count=len(results))
        return results

    async def similarity_search_text(
        self,
        query_text: str,
        top_k: int = 5,
        exclude_item_id: UUID | None = None,
    ) -> list[SimilarityResult]:
        """
        Search for similar items by text query.

        Generates embedding for query text, then performs similarity search.

        Args:
            query_text: Text to search for similar items
            top_k: Number of results to return
            exclude_item_id: Optional item ID to exclude

        Returns:
            List of SimilarityResult sorted by similarity
        """
        embedding = await self.embed_query(query_text)
        return await self.similarity_search(
            query_embedding=embedding,
            top_k=top_k,
            exclude_item_id=exclude_item_id,
        )

    async def search_matched_products(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for products that have already been matched.

        Returns products (via supplier_items.product_id) that are
        semantically similar to the query. Useful for finding
        candidate matches for new items.

        Args:
            query_embedding: 768-dimensional query vector
            top_k: Number of results to return

        Returns:
            List of dicts with product_id, product_name, similarity
        """
        return await self._embeddings_repo.search_by_product_id(
            query_embedding=query_embedding,
            top_k=top_k,
            model_name=self._model_name,
        )

    async def store_embedding(
        self,
        supplier_item_id: UUID,
        embedding: list[float],
    ) -> UUID:
        """
        Store embedding for a supplier item.

        Uses upsert (ON CONFLICT DO UPDATE) to handle existing embeddings.

        Args:
            supplier_item_id: Reference to supplier_items table
            embedding: 768-dimensional vector

        Returns:
            Created or updated embedding UUID
        """
        return await self._embeddings_repo.insert(
            supplier_item_id=supplier_item_id,
            embedding=embedding,
            model_name=self._model_name,
        )

    async def embed_and_store(
        self,
        supplier_item_id: UUID,
        text: str,
    ) -> UUID:
        """
        Generate embedding and store it in one operation.

        Convenience method that combines embed_query and store_embedding.

        Args:
            supplier_item_id: Reference to supplier_items table
            text: Text to embed

        Returns:
            Created or updated embedding UUID
        """
        embedding = await self.embed_query(text)
        return await self.store_embedding(supplier_item_id, embedding)

    async def has_embedding(self, supplier_item_id: UUID) -> bool:
        """
        Check if a supplier item has an embedding.

        Args:
            supplier_item_id: Supplier item UUID

        Returns:
            True if embedding exists
        """
        return await self._embeddings_repo.exists(
            supplier_item_id=supplier_item_id,
            model_name=self._model_name,
        )

    async def delete_embedding(self, supplier_item_id: UUID) -> int:
        """
        Delete embedding for a supplier item.

        Args:
            supplier_item_id: Supplier item UUID

        Returns:
            Number of deleted rows
        """
        return await self._embeddings_repo.delete_by_supplier_item_id(
            supplier_item_id=supplier_item_id,
            model_name=self._model_name,
        )

    async def get_embedding_count(self) -> int:
        """
        Get total number of embeddings.

        Returns:
            Total embedding count for current model
        """
        return await self._embeddings_repo.count_by_model(model_name=self._model_name)

    async def health_check(self) -> dict[str, Any]:
        """
        Check VectorService health.

        Verifies:
        - Ollama connection (can generate embedding)
        - Database connection (can count embeddings)

        Returns:
            Health check result dict
        """
        import time

        result = {
            "service": "vector_service",
            "status": "healthy",
            "model": self._model_name,
            "dimensions": self._embedding_dimensions,
            "checks": {},
        }

        # Check Ollama
        try:
            start = time.perf_counter()
            await self.embed_query("health check test")
            latency = (time.perf_counter() - start) * 1000

            result["checks"]["ollama"] = {
                "status": "healthy",
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            result["status"] = "unhealthy"
            result["checks"]["ollama"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Check database
        try:
            start = time.perf_counter()
            count = await self.get_embedding_count()
            latency = (time.perf_counter() - start) * 1000

            result["checks"]["database"] = {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "embedding_count": count,
            }
        except Exception as e:
            result["status"] = "unhealthy"
            result["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        return result

