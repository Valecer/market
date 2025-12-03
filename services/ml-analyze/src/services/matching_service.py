"""
Matching Service
=================

Orchestrates the product matching pipeline:
1. Retrieve supplier items pending match
2. For each item, call MergerAgent to find matches
3. Apply confidence thresholds
4. Update database based on classification

Pipeline:
    SupplierItem → VectorSearch → LLM Matching → DB Update
                                       │
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
            confidence ≥ 0.9    0.7 ≤ conf < 0.9    confidence < 0.7
                    │                  │                  │
            UPDATE supplier    INSERT INTO         Log to
            SET product_id     match_review_queue  parsing_logs

Follows:
- Single Responsibility: Orchestration only
- Dependency Inversion: Depends on abstractions (repos, services)
- Error Isolation: Per-item error handling
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.db.repositories.match_review_repo import MatchReviewRepository
from src.db.repositories.parsing_logs_repo import ParsingLogsRepository
from src.db.repositories.supplier_items_repo import SupplierItemsRepository
from src.rag.merger_agent import MergerAgent
from src.rag.vector_service import VectorService
from src.schemas.domain import MatchResult
from src.utils.errors import DatabaseError, LLMError, MLAnalyzeError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MatchingStats:
    """Statistics from a matching operation."""

    items_processed: int = 0
    auto_matched: int = 0
    sent_to_review: int = 0
    rejected: int = 0
    errors: int = 0

    @property
    def total_matches(self) -> int:
        """Total matches found (auto + review)."""
        return self.auto_matched + self.sent_to_review

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "items_processed": self.items_processed,
            "auto_matched": self.auto_matched,
            "sent_to_review": self.sent_to_review,
            "rejected": self.rejected,
            "errors": self.errors,
            "total_matches": self.total_matches,
        }


@dataclass
class ItemMatchResult:
    """Result of matching a single item."""

    supplier_item_id: UUID
    status: str  # 'auto_matched', 'review', 'rejected', 'no_match', 'error'
    match: MatchResult | None = None
    error_message: str | None = None


class MatchingService:
    """
    Service for orchestrating product matching.

    Workflow:
    1. Get items pending match from database
    2. For each item, find matches using MergerAgent
    3. Classify matches by confidence threshold
    4. Apply database updates based on classification
    5. Log results and errors

    Usage:
        async with get_session() as session:
            service = MatchingService(session)

            # Match a single item
            result = await service.match_item(supplier_item_id)

            # Match all pending items for a supplier
            stats = await service.match_supplier_items(supplier_id)
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize MatchingService.

        Args:
            session: SQLAlchemy async session
            settings: Application settings
        """
        self._session = session
        self._settings = settings or get_settings()

        # Initialize repositories
        self._supplier_items_repo = SupplierItemsRepository(session)
        self._match_review_repo = MatchReviewRepository(session)
        self._parsing_logs_repo = ParsingLogsRepository(session)

        # Initialize services
        self._vector_service = VectorService(session, settings)
        self._merger_agent = MergerAgent(
            session,
            settings,
            vector_service=self._vector_service,
        )

        # Thresholds
        self._auto_threshold = self._settings.match_confidence_auto_threshold
        self._review_threshold = self._settings.match_confidence_review_threshold

        logger.debug(
            "MatchingService initialized",
            auto_threshold=self._auto_threshold,
            review_threshold=self._review_threshold,
        )

    async def match_item(
        self,
        supplier_item_id: UUID,
        top_k: int = 5,
    ) -> ItemMatchResult:
        """
        Find and process matches for a single supplier item.

        Args:
            supplier_item_id: Item to match
            top_k: Number of candidates for vector search

        Returns:
            ItemMatchResult with match status and details
        """
        logger.info("Matching item", supplier_item_id=str(supplier_item_id))

        try:
            # Get item from database
            item = await self._supplier_items_repo.get_by_id(supplier_item_id)
            if not item:
                return ItemMatchResult(
                    supplier_item_id=supplier_item_id,
                    status="error",
                    error_message="Item not found",
                )

            # Extract item data for matching
            name = item.get("name", "")
            characteristics = item.get("characteristics", {})
            description = characteristics.get("_description")
            category = characteristics.get("_category")
            brand = characteristics.get("_brand")

            # Find matches via MergerAgent
            matches = await self._merger_agent.find_matches(
                item_name=name,
                item_description=description,
                item_sku=item.get("sku"),
                item_category=category,
                item_brand=brand,
                item_characteristics=characteristics,
                supplier_item_id=supplier_item_id,
                top_k=top_k,
            )

            if not matches:
                # No matches found - log and mark as no_match
                await self._log_no_match(supplier_item_id, name)
                return ItemMatchResult(
                    supplier_item_id=supplier_item_id,
                    status="no_match",
                )

            # Process best match
            best_match = max(matches, key=lambda m: m.confidence)
            result = await self._process_match(supplier_item_id, best_match)

            return result

        except LLMError as e:
            logger.error(
                "LLM error during matching",
                supplier_item_id=str(supplier_item_id),
                error=e.message,
            )
            await self._log_error(supplier_item_id, "llm_error", str(e))
            return ItemMatchResult(
                supplier_item_id=supplier_item_id,
                status="error",
                error_message=e.message,
            )
        except Exception as e:
            logger.exception(
                "Unexpected error during matching",
                supplier_item_id=str(supplier_item_id),
            )
            await self._log_error(supplier_item_id, "matching_error", str(e))
            return ItemMatchResult(
                supplier_item_id=supplier_item_id,
                status="error",
                error_message=str(e),
            )

    async def match_batch(
        self,
        supplier_item_ids: list[UUID],
        top_k: int = 5,
    ) -> tuple[list[ItemMatchResult], MatchingStats]:
        """
        Match multiple supplier items.

        Processes items sequentially with error isolation.

        Args:
            supplier_item_ids: Items to match
            top_k: Number of candidates for vector search

        Returns:
            Tuple of (results list, matching stats)
        """
        logger.info("Matching batch", count=len(supplier_item_ids))

        results = []
        stats = MatchingStats()

        for item_id in supplier_item_ids:
            try:
                result = await self.match_item(item_id, top_k=top_k)
                results.append(result)
                stats.items_processed += 1

                # Update stats based on result
                if result.status == "auto_matched":
                    stats.auto_matched += 1
                elif result.status == "review":
                    stats.sent_to_review += 1
                elif result.status == "rejected":
                    stats.rejected += 1
                elif result.status == "error":
                    stats.errors += 1

            except Exception as e:
                logger.error(
                    "Error matching item in batch",
                    supplier_item_id=str(item_id),
                    error=str(e),
                )
                results.append(
                    ItemMatchResult(
                        supplier_item_id=item_id,
                        status="error",
                        error_message=str(e),
                    )
                )
                stats.items_processed += 1
                stats.errors += 1

        logger.info(
            "Batch matching complete",
            stats=stats.to_dict(),
        )

        return results, stats

    async def match_pending_items(
        self,
        supplier_id: UUID | None = None,
        limit: int = 100,
        top_k: int = 5,
    ) -> tuple[list[ItemMatchResult], MatchingStats]:
        """
        Match all pending items (optionally filtered by supplier).

        Args:
            supplier_id: Optional supplier filter
            limit: Maximum items to process
            top_k: Number of candidates for vector search

        Returns:
            Tuple of (results list, matching stats)
        """
        logger.info(
            "Matching pending items",
            supplier_id=str(supplier_id) if supplier_id else "all",
            limit=limit,
        )

        # Get pending items
        pending = await self._supplier_items_repo.get_pending_match(
            supplier_id=supplier_id,
            limit=limit,
        )

        if not pending:
            logger.info("No pending items to match")
            return [], MatchingStats()

        item_ids = [item["id"] for item in pending]
        return await self.match_batch(item_ids, top_k=top_k)

    async def _process_match(
        self,
        supplier_item_id: UUID,
        match: MatchResult,
    ) -> ItemMatchResult:
        """
        Process a match based on confidence threshold.

        Args:
            supplier_item_id: Item being matched
            match: Match result from LLM

        Returns:
            ItemMatchResult with processing outcome
        """
        confidence = match.confidence

        if confidence >= self._auto_threshold:
            # High confidence: auto-match
            return await self._apply_auto_match(supplier_item_id, match)

        elif confidence >= self._review_threshold:
            # Medium confidence: send to review
            return await self._send_to_review(supplier_item_id, match)

        else:
            # Low confidence: reject
            return await self._reject_match(supplier_item_id, match)

    async def _apply_auto_match(
        self,
        supplier_item_id: UUID,
        match: MatchResult,
    ) -> ItemMatchResult:
        """
        Apply auto-match: update supplier_items.product_id.

        Args:
            supplier_item_id: Item to update
            match: Match to apply

        Returns:
            ItemMatchResult with auto_matched status
        """
        logger.info(
            "Auto-matching item",
            supplier_item_id=str(supplier_item_id),
            product_id=str(match.product_id),
            confidence=match.confidence,
        )

        try:
            await self._supplier_items_repo.update_product_id(
                item_id=supplier_item_id,
                product_id=match.product_id,
                match_status="auto_matched",
            )

            return ItemMatchResult(
                supplier_item_id=supplier_item_id,
                status="auto_matched",
                match=match,
            )

        except Exception as e:
            logger.error(
                "Failed to apply auto-match",
                supplier_item_id=str(supplier_item_id),
                error=str(e),
            )
            raise DatabaseError(
                message="Failed to apply auto-match",
                details={"supplier_item_id": str(supplier_item_id), "error": str(e)},
            ) from e

    async def _send_to_review(
        self,
        supplier_item_id: UUID,
        match: MatchResult,
    ) -> ItemMatchResult:
        """
        Send match to review queue.

        Args:
            supplier_item_id: Item to review
            match: Match suggestion

        Returns:
            ItemMatchResult with review status
        """
        logger.info(
            "Sending to review",
            supplier_item_id=str(supplier_item_id),
            product_id=str(match.product_id),
            confidence=match.confidence,
        )

        try:
            await self._match_review_repo.insert(
                supplier_item_id=supplier_item_id,
                suggested_product_id=match.product_id,
                confidence_score=match.confidence,
                reasoning=match.reasoning,
                similarity_score=match.similarity_score,
            )

            # Update item status to 'review'
            await self._update_item_status(supplier_item_id, "review")

            return ItemMatchResult(
                supplier_item_id=supplier_item_id,
                status="review",
                match=match,
            )

        except Exception as e:
            logger.error(
                "Failed to send to review",
                supplier_item_id=str(supplier_item_id),
                error=str(e),
            )
            raise DatabaseError(
                message="Failed to send to review queue",
                details={"supplier_item_id": str(supplier_item_id), "error": str(e)},
            ) from e

    async def _reject_match(
        self,
        supplier_item_id: UUID,
        match: MatchResult,
    ) -> ItemMatchResult:
        """
        Reject low-confidence match: log and skip.

        Args:
            supplier_item_id: Item
            match: Rejected match

        Returns:
            ItemMatchResult with rejected status
        """
        logger.info(
            "Rejecting low-confidence match",
            supplier_item_id=str(supplier_item_id),
            confidence=match.confidence,
        )

        # Log rejection
        await self._parsing_logs_repo.log_error(
            supplier_id=await self._get_supplier_id(supplier_item_id),
            error_type="low_confidence_match",
            message=f"Match rejected: confidence {match.confidence:.2f} < {self._review_threshold}",
            severity="info",
            context={
                "supplier_item_id": str(supplier_item_id),
                "suggested_product_id": str(match.product_id),
                "confidence": match.confidence,
                "reasoning": match.reasoning,
            },
        )

        return ItemMatchResult(
            supplier_item_id=supplier_item_id,
            status="rejected",
            match=match,
        )

    async def _log_no_match(
        self,
        supplier_item_id: UUID,
        item_name: str,
    ) -> None:
        """Log when no matches are found."""
        await self._parsing_logs_repo.log_error(
            supplier_id=await self._get_supplier_id(supplier_item_id),
            error_type="no_match_found",
            message=f"No product matches found for: {item_name[:100]}",
            severity="info",
            context={"supplier_item_id": str(supplier_item_id)},
        )

    async def _log_error(
        self,
        supplier_item_id: UUID,
        error_type: str,
        message: str,
    ) -> None:
        """Log a matching error."""
        try:
            await self._parsing_logs_repo.log_error(
                supplier_id=await self._get_supplier_id(supplier_item_id),
                error_type=error_type,
                message=message,
                severity="error",
                context={"supplier_item_id": str(supplier_item_id)},
            )
        except Exception as e:
            logger.warning("Failed to log error", error=str(e))

    async def _update_item_status(
        self,
        supplier_item_id: UUID,
        status: str,
    ) -> None:
        """Update supplier item match status."""
        from sqlalchemy import text

        query = text("""
            UPDATE supplier_items
            SET match_status = :status, updated_at = NOW()
            WHERE id = :item_id
        """)

        await self._session.execute(
            query,
            {"item_id": str(supplier_item_id), "status": status},
        )

    async def _get_supplier_id(self, supplier_item_id: UUID) -> UUID:
        """Get supplier ID for an item."""
        item = await self._supplier_items_repo.get_by_id(supplier_item_id)
        if item:
            return item.get("supplier_id")
        return supplier_item_id  # Fallback


# Convenience function
async def match_items(
    session: AsyncSession,
    supplier_item_ids: list[UUID],
    **kwargs: Any,
) -> tuple[list[ItemMatchResult], MatchingStats]:
    """
    Convenience function to match multiple items.

    Args:
        session: Database session
        supplier_item_ids: Items to match
        **kwargs: Additional arguments for MatchingService

    Returns:
        Tuple of (results, stats)
    """
    service = MatchingService(session)
    return await service.match_batch(supplier_item_ids, **kwargs)


