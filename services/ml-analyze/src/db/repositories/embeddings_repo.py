"""
Embeddings Repository
======================

Data access layer for the product_embeddings table.
Provides CRUD operations and similarity search using pgvector.

Follows Repository Pattern: Abstracts database operations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ProductEmbedding
from src.schemas.domain import ProductEmbeddingData, SimilarityResult
from src.utils.errors import DatabaseError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingsRepository:
    """
    Repository for product_embeddings table operations.

    Handles vector storage and similarity search using pgvector.
    Uses cosine similarity (<=> operator) for semantic search.

    Table Schema:
        id: UUID (PK)
        supplier_item_id: UUID (FK → supplier_items)
        embedding: vector(768) - 768-dimensional float vector
        model_name: str (default: 'nomic-embed-text')
        created_at: datetime
        updated_at: datetime

    Constraints:
        - Unique constraint on (supplier_item_id, model_name)
        - IVFFLAT index for fast cosine similarity search
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def insert(
        self,
        supplier_item_id: UUID,
        embedding: list[float],
        model_name: str = "nomic-embed-text",
    ) -> UUID:
        """
        Insert a new embedding or update if exists (ON CONFLICT DO UPDATE).

        Uses PostgreSQL's INSERT ... ON CONFLICT for upsert behavior.
        If an embedding already exists for the (supplier_item_id, model_name) pair,
        it updates the embedding and updated_at timestamp.

        Args:
            supplier_item_id: Reference to supplier_items table
            embedding: 768-dimensional vector embedding
            model_name: Embedding model identifier

        Returns:
            Created or updated embedding's UUID

        Raises:
            DatabaseError: If insert/update fails
        """
        try:
            # Validate embedding dimensions
            if len(embedding) != 768:
                raise ValueError(
                    f"Embedding must be 768 dimensions, got {len(embedding)}"
                )

            # Use raw SQL for ON CONFLICT DO UPDATE with pgvector
            query = text("""
                INSERT INTO product_embeddings (
                    supplier_item_id, embedding, model_name, created_at, updated_at
                ) VALUES (
                    :supplier_item_id, CAST(:embedding AS vector), :model_name, NOW(), NOW()
                )
                ON CONFLICT (supplier_item_id, model_name)
                DO UPDATE SET
                    embedding = CAST(:embedding AS vector),
                    updated_at = NOW()
                RETURNING id
            """)

            # Convert embedding list to PostgreSQL vector format
            embedding_str = f"[{','.join(str(x) for x in embedding)}]"

            result = await self._session.execute(
                query,
                {
                    "supplier_item_id": str(supplier_item_id),
                    "embedding": embedding_str,
                    "model_name": model_name,
                },
            )

            embedding_id = result.scalar_one()
            logger.debug(
                "Embedding upserted",
                embedding_id=str(embedding_id),
                supplier_item_id=str(supplier_item_id),
            )
            return embedding_id

        except Exception as e:
            logger.error(
                "Failed to insert embedding",
                supplier_item_id=str(supplier_item_id),
                error=str(e),
            )
            raise DatabaseError(
                message="Failed to insert embedding",
                details={"supplier_item_id": str(supplier_item_id), "error": str(e)},
            ) from e

    async def insert_batch(
        self,
        embeddings: list[tuple[UUID, list[float]]],
        model_name: str = "nomic-embed-text",
    ) -> list[UUID]:
        """
        Insert multiple embeddings in a batch.

        Uses PostgreSQL's multi-value INSERT with ON CONFLICT.

        Args:
            embeddings: List of (supplier_item_id, embedding) tuples
            model_name: Embedding model identifier

        Returns:
            List of created/updated embedding UUIDs
        """
        if not embeddings:
            return []

        ids = []
        for supplier_item_id, embedding in embeddings:
            embedding_id = await self.insert(supplier_item_id, embedding, model_name)
            ids.append(embedding_id)

        logger.info("Batch embeddings inserted", count=len(ids))
        return ids

    async def get_by_supplier_item_id(
        self,
        supplier_item_id: UUID,
        model_name: str = "nomic-embed-text",
    ) -> ProductEmbeddingData | None:
        """
        Get embedding by supplier item ID.

        Args:
            supplier_item_id: Supplier item UUID
            model_name: Embedding model name

        Returns:
            ProductEmbeddingData or None if not found
        """
        query = text("""
            SELECT id, supplier_item_id, embedding::text, model_name, created_at, updated_at
            FROM product_embeddings
            WHERE supplier_item_id = :supplier_item_id
              AND model_name = :model_name
        """)

        result = await self._session.execute(
            query,
            {
                "supplier_item_id": str(supplier_item_id),
                "model_name": model_name,
            },
        )
        row = result.mappings().fetchone()

        if not row:
            return None

        # Parse embedding string back to list
        embedding_str = row["embedding"]
        embedding = self._parse_embedding_string(embedding_str)

        return ProductEmbeddingData(
            id=row["id"],
            supplier_item_id=row["supplier_item_id"],
            embedding=embedding,
            model_name=row["model_name"],
            created_at=row["created_at"],
        )

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        model_name: str = "nomic-embed-text",
        exclude_item_id: UUID | None = None,
    ) -> list[SimilarityResult]:
        """
        Search for similar items using cosine similarity.

        Uses pgvector's cosine distance operator (<=>).
        Lower distance = more similar.

        Cosine distance = 1 - cosine_similarity
        So similarity = 1 - distance

        Args:
            query_embedding: 768-dimensional query vector
            top_k: Number of results to return (default: 5)
            model_name: Filter by embedding model
            exclude_item_id: Optional item ID to exclude from results

        Returns:
            List of SimilarityResult objects sorted by similarity (highest first)
        """
        if len(query_embedding) != 768:
            raise ValueError(
                f"Query embedding must be 768 dimensions, got {len(query_embedding)}"
            )

        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Build query with optional exclusion
        if exclude_item_id:
            query = text("""
                SELECT
                    pe.supplier_item_id,
                    si.product_id,
                    si.name,
                    si.characteristics,
                    (1 - (pe.embedding <=> CAST(:query_embedding AS vector))) AS similarity
                FROM product_embeddings pe
                JOIN supplier_items si ON pe.supplier_item_id = si.id
                WHERE pe.model_name = :model_name
                  AND pe.supplier_item_id != :exclude_item_id
                ORDER BY pe.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :top_k
            """)
            params = {
                "query_embedding": embedding_str,
                "model_name": model_name,
                "exclude_item_id": str(exclude_item_id),
                "top_k": top_k,
            }
        else:
            query = text("""
                SELECT
                    pe.supplier_item_id,
                    si.product_id,
                    si.name,
                    si.characteristics,
                    (1 - (pe.embedding <=> CAST(:query_embedding AS vector))) AS similarity
                FROM product_embeddings pe
                JOIN supplier_items si ON pe.supplier_item_id = si.id
                WHERE pe.model_name = :model_name
                ORDER BY pe.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :top_k
            """)
            params = {
                "query_embedding": embedding_str,
                "model_name": model_name,
                "top_k": top_k,
            }

        result = await self._session.execute(query, params)
        rows = result.mappings().fetchall()

        results = []
        for row in rows:
            results.append(
                SimilarityResult(
                    supplier_item_id=row["supplier_item_id"],
                    product_id=row["product_id"],
                    name=row["name"],
                    similarity=float(row["similarity"]),
                    characteristics=row["characteristics"] or {},
                )
            )

        logger.debug(
            "Similarity search completed",
            results_count=len(results),
            top_k=top_k,
        )
        return results

    async def search_by_product_id(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        model_name: str = "nomic-embed-text",
    ) -> list[dict[str, Any]]:
        """
        Search for matched products (items with product_id set).

        Returns products that have already been matched, useful for
        finding candidate matches for new items.

        Args:
            query_embedding: 768-dimensional query vector
            top_k: Number of results to return
            model_name: Filter by embedding model

        Returns:
            List of dicts with product_id, product_name, similarity
        """
        if len(query_embedding) != 768:
            raise ValueError(
                f"Query embedding must be 768 dimensions, got {len(query_embedding)}"
            )

        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        query = text("""
            SELECT DISTINCT ON (si.product_id)
                si.product_id,
                p.name AS product_name,
                (1 - (pe.embedding <=> CAST(:query_embedding AS vector))) AS similarity
            FROM product_embeddings pe
            JOIN supplier_items si ON pe.supplier_item_id = si.id
            JOIN products p ON si.product_id = p.id
            WHERE pe.model_name = :model_name
              AND si.product_id IS NOT NULL
              AND p.status = 'active'
            ORDER BY si.product_id, pe.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """)

        result = await self._session.execute(
            query,
            {
                "query_embedding": embedding_str,
                "model_name": model_name,
                "top_k": top_k,
            },
        )

        return [dict(row) for row in result.mappings().fetchall()]

    async def delete_by_supplier_item_id(
        self,
        supplier_item_id: UUID,
        model_name: str | None = None,
    ) -> int:
        """
        Delete embedding(s) by supplier item ID.

        Args:
            supplier_item_id: Supplier item UUID
            model_name: Optional model name filter

        Returns:
            Number of deleted rows
        """
        if model_name:
            query = text("""
                DELETE FROM product_embeddings
                WHERE supplier_item_id = :supplier_item_id
                  AND model_name = :model_name
            """)
            params = {
                "supplier_item_id": str(supplier_item_id),
                "model_name": model_name,
            }
        else:
            query = text("""
                DELETE FROM product_embeddings
                WHERE supplier_item_id = :supplier_item_id
            """)
            params = {"supplier_item_id": str(supplier_item_id)}

        result = await self._session.execute(query, params)
        deleted = result.rowcount

        logger.debug(
            "Embeddings deleted",
            supplier_item_id=str(supplier_item_id),
            deleted_count=deleted,
        )
        return deleted

    async def count_by_model(self, model_name: str = "nomic-embed-text") -> int:
        """
        Count embeddings by model name.

        Args:
            model_name: Embedding model name

        Returns:
            Number of embeddings
        """
        query = text("""
            SELECT COUNT(*) as count
            FROM product_embeddings
            WHERE model_name = :model_name
        """)

        result = await self._session.execute(query, {"model_name": model_name})
        return result.scalar_one()

    async def exists(
        self,
        supplier_item_id: UUID,
        model_name: str = "nomic-embed-text",
    ) -> bool:
        """
        Check if embedding exists for supplier item.

        Args:
            supplier_item_id: Supplier item UUID
            model_name: Embedding model name

        Returns:
            True if embedding exists
        """
        query = text("""
            SELECT EXISTS(
                SELECT 1 FROM product_embeddings
                WHERE supplier_item_id = :supplier_item_id
                  AND model_name = :model_name
            )
        """)

        result = await self._session.execute(
            query,
            {
                "supplier_item_id": str(supplier_item_id),
                "model_name": model_name,
            },
        )
        return result.scalar_one()

    @staticmethod
    def _parse_embedding_string(embedding_str: str) -> list[float]:
        """
        Parse PostgreSQL vector string to Python list.

        Args:
            embedding_str: String like "[0.1,0.2,0.3]"

        Returns:
            List of floats
        """
        if not embedding_str:
            return []

        # Remove brackets and split
        clean = embedding_str.strip("[]")
        if not clean:
            return []

        return [float(x) for x in clean.split(",")]

