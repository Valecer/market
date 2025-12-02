"""Product aggregation service for calculating product metrics.

This module implements FR-3: Price & Availability Aggregation.
It calculates and maintains aggregate fields on products based on
their linked supplier items.

Key Functions:
    - calculate_product_aggregates: Calculate min_price and availability for a single product
    - calculate_product_aggregates_batch: Calculate aggregates for multiple products
    - get_review_queue_stats: Get statistics for the review queue dashboard

SOLID Compliance:
    - Single Responsibility: Only handles aggregate calculations
    - Dependency Inversion: Depends on SQLAlchemy session abstraction
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
import structlog

from sqlalchemy import select, update, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

from src.db.models import (
    Product,
    SupplierItem,
    MatchStatus,
    MatchReviewQueue,
    ReviewStatus,
)

logger = structlog.get_logger(__name__)


async def calculate_product_aggregates(
    session: AsyncSession,
    product_id: UUID,
    trigger: str = "manual",
) -> Dict[str, Any]:
    """Calculate and update aggregate fields for a single product.
    
    Calculates:
        - min_price: MIN(current_price) of linked items with AUTO_MATCHED or VERIFIED_MATCH status
        - availability: TRUE if ANY linked item has in_stock=true in characteristics
    
    Args:
        session: AsyncSession for database operations
        product_id: UUID of the product to update
        trigger: What triggered the recalculation (auto_match, manual_link, price_change)
        
    Returns:
        Dictionary with updated values and metadata:
            - product_id: UUID of the product
            - min_price: Updated min_price value (Decimal or None)
            - availability: Updated availability value (bool)
            - linked_items_count: Number of linked supplier items
            - trigger: What triggered the recalculation
            
    Note:
        Uses single UPDATE query with subquery for efficiency.
        Only considers items with match_status in (AUTO_MATCHED, VERIFIED_MATCH).
    """
    log = logger.bind(product_id=str(product_id), trigger=trigger)
    log.debug("calculating_product_aggregates")
    
    # Subquery for min_price: MIN(current_price) of linked matched items
    min_price_subq = (
        select(func.min(SupplierItem.current_price))
        .where(
            and_(
                SupplierItem.product_id == product_id,
                SupplierItem.match_status.in_([
                    MatchStatus.AUTO_MATCHED,
                    MatchStatus.VERIFIED_MATCH,
                ])
            )
        )
        .correlate(Product)
        .scalar_subquery()
    )
    
    # Subquery for availability: EXISTS any linked item with in_stock=true
    # Check for various representations of "true" in JSONB: true, 'true', 'yes', '1'
    availability_subq = (
        select(func.count(SupplierItem.id) > 0)
        .where(
            and_(
                SupplierItem.product_id == product_id,
                SupplierItem.match_status.in_([
                    MatchStatus.AUTO_MATCHED,
                    MatchStatus.VERIFIED_MATCH,
                ]),
                or_(
                    # Boolean true in JSONB
                    SupplierItem.characteristics["in_stock"].astext == "true",
                    # String variations
                    func.lower(SupplierItem.characteristics["in_stock"].astext) == "yes",
                    func.lower(SupplierItem.characteristics["in_stock"].astext) == "1",
                    # Handle JSON boolean true (cast to text)
                    SupplierItem.characteristics["in_stock"].astext == "True",
                )
            )
        )
        .correlate(Product)
        .scalar_subquery()
    )
    
    # Count linked items for metadata
    linked_count_query = (
        select(func.count(SupplierItem.id))
        .where(
            and_(
                SupplierItem.product_id == product_id,
                SupplierItem.match_status.in_([
                    MatchStatus.AUTO_MATCHED,
                    MatchStatus.VERIFIED_MATCH,
                ])
            )
        )
    )
    linked_count_result = await session.execute(linked_count_query)
    linked_items_count = linked_count_result.scalar() or 0
    
    # Execute UPDATE with subqueries
    update_stmt = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            min_price=min_price_subq,
            availability=func.coalesce(availability_subq, False),
        )
        .returning(Product.min_price, Product.availability)
    )
    
    result = await session.execute(update_stmt)
    row = result.one_or_none()
    
    if row:
        updated_min_price, updated_availability = row
        log.info(
            "product_aggregates_updated",
            min_price=str(updated_min_price) if updated_min_price else None,
            availability=updated_availability,
            linked_items_count=linked_items_count,
        )
        return {
            "product_id": product_id,
            "min_price": updated_min_price,
            "availability": updated_availability,
            "linked_items_count": linked_items_count,
            "trigger": trigger,
        }
    else:
        log.warning("product_not_found_for_aggregate_update")
        return {
            "product_id": product_id,
            "min_price": None,
            "availability": False,
            "linked_items_count": 0,
            "trigger": trigger,
            "error": "Product not found",
        }


async def calculate_product_aggregates_batch(
    session: AsyncSession,
    product_ids: List[UUID],
    trigger: str = "manual",
) -> List[Dict[str, Any]]:
    """Calculate and update aggregate fields for multiple products.
    
    Processes products in batch for efficiency, using individual
    UPDATE statements within a single transaction.
    
    Args:
        session: AsyncSession for database operations
        product_ids: List of product UUIDs to update
        trigger: What triggered the recalculation
        
    Returns:
        List of result dictionaries, one per product
        
    Note:
        All updates happen in a single transaction.
        Failed updates are logged but don't stop other updates.
    """
    log = logger.bind(product_count=len(product_ids), trigger=trigger)
    log.info("calculating_product_aggregates_batch")
    
    results = []
    for product_id in product_ids:
        try:
            result = await calculate_product_aggregates(
                session=session,
                product_id=product_id,
                trigger=trigger,
            )
            results.append(result)
        except Exception as e:
            log.error(
                "product_aggregate_calculation_failed",
                product_id=str(product_id),
                error=str(e),
                error_type=type(e).__name__,
            )
            results.append({
                "product_id": product_id,
                "error": str(e),
                "trigger": trigger,
            })
    
    # Summary log
    success_count = sum(1 for r in results if "error" not in r)
    error_count = len(results) - success_count
    
    log.info(
        "product_aggregates_batch_completed",
        success_count=success_count,
        error_count=error_count,
    )
    
    return results


async def get_review_queue_stats(
    session: AsyncSession,
    supplier_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Get statistics for the match review queue.
    
    Returns counts of review queue items grouped by status,
    optionally filtered by supplier or category.
    
    Args:
        session: AsyncSession for database operations
        supplier_id: Optional filter by supplier
        category_id: Optional filter by category (via supplier_item)
        
    Returns:
        Dictionary with stats:
            - total: Total items in queue
            - pending: Items awaiting review
            - approved: Items approved
            - rejected: Items rejected
            - expired: Items that expired
            - needs_category: Items needing category assignment
            - by_supplier: Dict[supplier_id, count] if not filtered
            - by_category: Dict[category_id, count] if not filtered
    """
    log = logger.bind(
        supplier_id=str(supplier_id) if supplier_id else None,
        category_id=str(category_id) if category_id else None,
    )
    log.debug("getting_review_queue_stats")
    
    # Base query with optional filters
    base_conditions = []
    
    if supplier_id:
        # Join through supplier_item to filter by supplier
        base_conditions.append(
            MatchReviewQueue.supplier_item_id.in_(
                select(SupplierItem.id).where(SupplierItem.supplier_id == supplier_id)
            )
        )
    
    if category_id:
        # Join through supplier_item -> product to filter by category
        base_conditions.append(
            MatchReviewQueue.supplier_item_id.in_(
                select(SupplierItem.id)
                .join(Product, SupplierItem.product_id == Product.id)
                .where(Product.category_id == category_id)
            )
        )
    
    # Count by status
    status_query = (
        select(
            MatchReviewQueue.status,
            func.count(MatchReviewQueue.id).label("count"),
        )
        .group_by(MatchReviewQueue.status)
    )
    
    if base_conditions:
        status_query = status_query.where(and_(*base_conditions))
    
    status_result = await session.execute(status_query)
    status_counts = {row.status.value: row.count for row in status_result}
    
    # Calculate total
    total = sum(status_counts.values())
    
    stats = {
        "total": total,
        "pending": status_counts.get(ReviewStatus.PENDING.value, 0),
        "approved": status_counts.get(ReviewStatus.APPROVED.value, 0),
        "rejected": status_counts.get(ReviewStatus.REJECTED.value, 0),
        "expired": status_counts.get(ReviewStatus.EXPIRED.value, 0),
        "needs_category": status_counts.get(ReviewStatus.NEEDS_CATEGORY.value, 0),
    }
    
    # Add breakdowns if not filtered
    if not supplier_id:
        # Group by supplier
        supplier_query = (
            select(
                SupplierItem.supplier_id,
                func.count(MatchReviewQueue.id).label("count"),
            )
            .join(SupplierItem, MatchReviewQueue.supplier_item_id == SupplierItem.id)
            .where(MatchReviewQueue.status == ReviewStatus.PENDING)
            .group_by(SupplierItem.supplier_id)
        )
        
        if category_id:
            supplier_query = supplier_query.join(
                Product, SupplierItem.product_id == Product.id
            ).where(Product.category_id == category_id)
        
        supplier_result = await session.execute(supplier_query)
        stats["by_supplier"] = {
            str(row.supplier_id): row.count for row in supplier_result
        }
    
    if not category_id:
        # Group by category (through product)
        category_query = (
            select(
                Product.category_id,
                func.count(MatchReviewQueue.id).label("count"),
            )
            .join(SupplierItem, MatchReviewQueue.supplier_item_id == SupplierItem.id)
            .join(Product, SupplierItem.product_id == Product.id)
            .where(
                and_(
                    MatchReviewQueue.status == ReviewStatus.PENDING,
                    Product.category_id.isnot(None),
                )
            )
            .group_by(Product.category_id)
        )
        
        if supplier_id:
            category_query = category_query.where(SupplierItem.supplier_id == supplier_id)
        
        category_result = await session.execute(category_query)
        stats["by_category"] = {
            str(row.category_id): row.count for row in category_result
        }
    
    log.debug("review_queue_stats_retrieved", stats=stats)
    return stats

