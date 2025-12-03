"""
Match Review Queue Repository
==============================

Data access layer for the match_review_queue table.
Handles insertion of medium-confidence matches for manual admin review.

Follows Repository Pattern: Abstracts database operations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.errors import DatabaseError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MatchReviewRepository:
    """
    Repository for match_review_queue table operations.

    The match_review_queue table stores matches with confidence scores
    between the review threshold (0.7) and auto-match threshold (0.9)
    for manual admin verification.

    Table Schema (from Phase 4):
        id: UUID (PK)
        supplier_item_id: UUID (FK → supplier_items)
        suggested_product_id: UUID (FK → products)
        confidence_score: Float (0.0 - 1.0)
        matching_algorithm: String (e.g., 'llm-llama3-rag')
        reasoning: Text (LLM's reasoning)
        status: String ('pending', 'approved', 'rejected')
        created_at: Timestamp
        updated_at: Timestamp

    ML-Analyze Usage:
        - Insert matches with 0.7 ≤ confidence < 0.9
        - Set matching_algorithm to 'llm-llama3-rag'
        - Include LLM reasoning text
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
        suggested_product_id: UUID,
        confidence_score: float,
        reasoning: str,
        matching_algorithm: str = "llm-llama3-rag",
        similarity_score: float | None = None,
    ) -> UUID:
        """
        Insert a match into the review queue.

        Called when confidence is between review threshold (0.7)
        and auto-match threshold (0.9).

        Args:
            supplier_item_id: Supplier item to match
            suggested_product_id: Suggested product match
            confidence_score: LLM confidence (0.0-1.0)
            reasoning: LLM's reasoning for the match
            matching_algorithm: Algorithm identifier
            similarity_score: Optional vector similarity score

        Returns:
            Created review entry UUID

        Raises:
            DatabaseError: If insert fails
        """
        try:
            # Validate confidence score
            if not (0.0 <= confidence_score <= 1.0):
                raise ValueError(f"Confidence score must be 0.0-1.0, got {confidence_score}")

            # Build metadata for additional context
            metadata = {}
            if similarity_score is not None:
                metadata["vector_similarity"] = similarity_score
            metadata["source"] = "ml-analyze"

            import json

            query = text("""
                INSERT INTO match_review_queue (
                    supplier_item_id,
                    suggested_product_id,
                    confidence_score,
                    matching_algorithm,
                    reasoning,
                    status,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (
                    :supplier_item_id,
                    :suggested_product_id,
                    :confidence_score,
                    :matching_algorithm,
                    :reasoning,
                    'pending',
                    :metadata::jsonb,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (supplier_item_id, suggested_product_id) DO UPDATE
                SET confidence_score = :confidence_score,
                    matching_algorithm = :matching_algorithm,
                    reasoning = :reasoning,
                    metadata = :metadata::jsonb,
                    updated_at = NOW()
                RETURNING id
            """)

            result = await self._session.execute(
                query,
                {
                    "supplier_item_id": str(supplier_item_id),
                    "suggested_product_id": str(suggested_product_id),
                    "confidence_score": confidence_score,
                    "matching_algorithm": matching_algorithm,
                    "reasoning": reasoning,
                    "metadata": json.dumps(metadata),
                },
            )

            review_id = result.scalar_one()
            logger.debug(
                "Match added to review queue",
                review_id=str(review_id),
                supplier_item_id=str(supplier_item_id),
                confidence=confidence_score,
            )
            return review_id

        except Exception as e:
            logger.error(
                "Failed to insert match review",
                supplier_item_id=str(supplier_item_id),
                error=str(e),
            )
            raise DatabaseError(
                message="Failed to insert match into review queue",
                details={
                    "supplier_item_id": str(supplier_item_id),
                    "error": str(e),
                },
            ) from e

    async def insert_batch(
        self,
        matches: list[dict[str, Any]],
    ) -> list[UUID]:
        """
        Insert multiple matches into review queue.

        Args:
            matches: List of dicts with:
                - supplier_item_id: UUID
                - suggested_product_id: UUID
                - confidence_score: float
                - reasoning: str
                - similarity_score: float (optional)

        Returns:
            List of created review entry UUIDs
        """
        if not matches:
            return []

        ids = []
        for match in matches:
            review_id = await self.insert(
                supplier_item_id=match["supplier_item_id"],
                suggested_product_id=match["suggested_product_id"],
                confidence_score=match["confidence_score"],
                reasoning=match.get("reasoning", ""),
                similarity_score=match.get("similarity_score"),
            )
            ids.append(review_id)

        logger.info("Batch matches added to review queue", count=len(ids))
        return ids

    async def get_pending_count(self) -> int:
        """
        Get count of pending review entries.

        Returns:
            Number of pending reviews
        """
        query = text("""
            SELECT COUNT(*) as count
            FROM match_review_queue
            WHERE status = 'pending'
        """)

        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_by_supplier_item_id(
        self,
        supplier_item_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Get all review entries for a supplier item.

        Args:
            supplier_item_id: Supplier item UUID

        Returns:
            List of review entry dicts
        """
        query = text("""
            SELECT 
                id, supplier_item_id, suggested_product_id,
                confidence_score, matching_algorithm, reasoning,
                status, metadata, created_at, updated_at
            FROM match_review_queue
            WHERE supplier_item_id = :supplier_item_id
            ORDER BY confidence_score DESC
        """)

        result = await self._session.execute(
            query,
            {"supplier_item_id": str(supplier_item_id)},
        )

        return [dict(row) for row in result.mappings().fetchall()]

    async def exists(
        self,
        supplier_item_id: UUID,
        suggested_product_id: UUID,
    ) -> bool:
        """
        Check if a match review entry already exists.

        Args:
            supplier_item_id: Supplier item UUID
            suggested_product_id: Product UUID

        Returns:
            True if entry exists
        """
        query = text("""
            SELECT EXISTS(
                SELECT 1 FROM match_review_queue
                WHERE supplier_item_id = :supplier_item_id
                  AND suggested_product_id = :suggested_product_id
            )
        """)

        result = await self._session.execute(
            query,
            {
                "supplier_item_id": str(supplier_item_id),
                "suggested_product_id": str(suggested_product_id),
            },
        )
        return result.scalar_one()

    async def delete_by_supplier_item_id(
        self,
        supplier_item_id: UUID,
    ) -> int:
        """
        Delete all review entries for a supplier item.

        Args:
            supplier_item_id: Supplier item UUID

        Returns:
            Number of deleted rows
        """
        query = text("""
            DELETE FROM match_review_queue
            WHERE supplier_item_id = :supplier_item_id
        """)

        result = await self._session.execute(
            query,
            {"supplier_item_id": str(supplier_item_id)},
        )

        deleted = result.rowcount
        if deleted > 0:
            logger.debug(
                "Review entries deleted",
                supplier_item_id=str(supplier_item_id),
                count=deleted,
            )
        return deleted

    async def count_by_algorithm(self) -> dict[str, int]:
        """
        Count pending reviews by matching algorithm.

        Returns:
            Dict mapping algorithm to count
        """
        query = text("""
            SELECT matching_algorithm, COUNT(*) as count
            FROM match_review_queue
            WHERE status = 'pending'
            GROUP BY matching_algorithm
        """)

        result = await self._session.execute(query)
        return {
            row["matching_algorithm"]: row["count"]
            for row in result.mappings().fetchall()
        }


