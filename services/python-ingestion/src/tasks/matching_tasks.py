"""Queue tasks for the product matching pipeline.

This module implements the core matching pipeline tasks:
    - match_items_task: Process unmatched supplier items and link to products
    - Supports category blocking for performance optimization
    - Uses SELECT FOR UPDATE SKIP LOCKED for concurrent worker safety
"""
import time
import uuid
import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Sequence
from dataclasses import dataclass

from arq.connections import ArqRedis
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from src.config import settings, matching_settings
from src.db.base import async_session_maker
from src.db.models import (
    SupplierItem,
    Product,
    ProductStatus,
    MatchStatus,
    MatchReviewQueue,
    ReviewStatus,
    Category,
)
from src.services.matching import (
    RapidFuzzMatcher,
    MatchResult,
    MatchCandidate,
    MatchStatusEnum,
    create_matcher,
)
from src.errors.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


# ============================================================================
# Observability Metrics Logging
# ============================================================================
# These functions emit structured log events that can be scraped by monitoring
# systems (e.g., Prometheus via mtail, Loki, or CloudWatch Logs Insights)

def emit_metric(metric_name: str, value: float, labels: Dict[str, str] = None) -> None:
    """Emit a metric event for observability.
    
    This function logs metrics in a structured format that can be parsed
    by log aggregation systems for monitoring dashboards.
    
    Args:
        metric_name: Name of the metric (e.g., "items_matched_total")
        value: Numeric value of the metric
        labels: Optional labels/tags for the metric
    """
    labels = labels or {}
    logger.info(
        "metric",
        metric_name=metric_name,
        metric_value=value,
        **labels,
    )


def emit_items_matched_total(count: int, match_type: str) -> None:
    """Emit metric for total items matched.
    
    Args:
        count: Number of items matched
        match_type: Type of match (auto_matched, potential_match, new_product)
    """
    emit_metric(
        "items_matched_total",
        count,
        {"match_type": match_type},
    )


def emit_matching_duration_seconds(duration: float, task_type: str) -> None:
    """Emit metric for matching task duration.
    
    Args:
        duration: Duration in seconds
        task_type: Type of task (match_items, enrich_item, recalc_aggregates)
    """
    emit_metric(
        "matching_duration_seconds",
        duration,
        {"task_type": task_type},
    )


def emit_review_queue_depth(pending_count: int) -> None:
    """Emit metric for review queue depth.
    
    Args:
        pending_count: Number of pending reviews
    """
    emit_metric(
        "review_queue_depth",
        pending_count,
    )


def emit_items_processed_total(count: int, status: str) -> None:
    """Emit metric for total items processed.
    
    Args:
        count: Number of items processed
        status: Processing status (success, error, skipped)
    """
    emit_metric(
        "items_processed_total",
        count,
        {"status": status},
    )


def generate_internal_sku() -> str:
    """Generate a unique internal SKU for a new product.
    
    Format: PROD-{timestamp}-{random}
    Example: PROD-1732623600000-A3F5
    
    Returns:
        Unique SKU string
    """
    timestamp = int(time.time() * 1000)
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"PROD-{timestamp}-{random_suffix}"


@dataclass
class MatchingMetrics:
    """Metrics collected during matching task execution."""
    items_processed: int = 0
    auto_matched: int = 0
    potential_matches: int = 0
    new_products_created: int = 0
    skipped_no_category: int = 0
    skipped_verified: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/response."""
        return {
            "items_processed": self.items_processed,
            "auto_matched": self.auto_matched,
            "potential_matches": self.potential_matches,
            "new_products_created": self.new_products_created,
            "skipped_no_category": self.skipped_no_category,
            "skipped_verified": self.skipped_verified,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
        }


async def match_items_task(
    ctx: Dict[str, Any],
    task_id: str,
    category_id: Optional[str] = None,
    batch_size: int = 100,
    retry_count: int = 0,
    max_retries: int = 3,
    **kwargs
) -> Dict[str, Any]:
    """Process a batch of unmatched supplier items and attempt to link to products.
    
    This task:
    1. Selects unmatched items using SELECT FOR UPDATE SKIP LOCKED
    2. For each item, finds candidate products (with optional category blocking)
    3. Applies threshold logic:
       - Score ≥95%: Auto-link to product
       - Score 70-94%: Add to review queue
       - Score <70%: Create new draft product
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique task identifier for logging
        category_id: Optional category UUID for blocking strategy
        batch_size: Number of items to process (1-1000)
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        
    Returns:
        Dictionary with task results and metrics
        
    Note:
        Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate processing
        when multiple workers are running concurrently.
    """
    start_time = time.time()
    metrics = MatchingMetrics()
    
    # Parse category_id if provided as string
    category_uuid: Optional[uuid.UUID] = None
    if category_id:
        try:
            category_uuid = uuid.UUID(category_id)
        except ValueError:
            logger.warning("invalid_category_id", task_id=task_id, category_id=category_id)
    
    log = logger.bind(
        task_id=task_id,
        batch_size=batch_size,
        category_id=str(category_uuid) if category_uuid else None,
    )
    
    log.info("match_items_task_started")
    
    # Load thresholds from settings
    auto_threshold = matching_settings.auto_threshold
    potential_threshold = matching_settings.potential_threshold
    max_candidates = matching_settings.max_candidates
    review_expiration_days = matching_settings.review_expiration_days
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Step 1: Select unmatched items with FOR UPDATE SKIP LOCKED
                # This prevents concurrent workers from processing the same items
                query = (
                    select(SupplierItem)
                    .where(
                        and_(
                            SupplierItem.product_id.is_(None),
                            SupplierItem.match_status == MatchStatus.UNMATCHED,
                        )
                    )
                    .order_by(SupplierItem.created_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
                
                # If category_id is provided, filter by items that have
                # supplier.category or will be matched against that category
                # For now, we'll load all unmatched and filter during matching
                
                result = await session.execute(query)
                unmatched_items = result.scalars().all()
                
                if not unmatched_items:
                    log.info("no_unmatched_items_found")
                    metrics.duration_seconds = time.time() - start_time
                    return {
                        "task_id": task_id,
                        "status": "success",
                        **metrics.to_dict(),
                    }
                
                log.info("unmatched_items_selected", count=len(unmatched_items))
                
                # Step 2: Load products for matching (with category blocking if specified)
                # Include both ACTIVE and DRAFT products to enable matching against
                # recently created products that haven't been activated yet
                products_query = (
                    select(Product)
                    .where(
                        or_(
                            Product.status == ProductStatus.ACTIVE,
                            Product.status == ProductStatus.DRAFT,
                        )
                    )
                )
                
                if category_uuid:
                    # Category blocking: only match against products in same category
                    products_query = products_query.where(
                        Product.category_id == category_uuid
                    )
                
                products_result = await session.execute(products_query)
                # Convert to list to allow appending new products during batch processing
                products: List[Product] = list(products_result.scalars().all())
                
                log.debug("products_loaded", count=len(products))
                
                # Step 3: Create matcher instance
                matcher = create_matcher("rapidfuzz")
                
                # Step 4: Process each item
                product_ids_to_recalc: List[uuid.UUID] = []
                
                for item in unmatched_items:
                    try:
                        # Skip items that are verified (protected from auto-matching)
                        if item.match_status == MatchStatus.VERIFIED_MATCH:
                            metrics.skipped_verified += 1
                            continue
                        
                        # Get products for this item (category blocking)
                        item_products = products
                        if category_uuid:
                            # Already filtered in query
                            pass
                        elif item.product_id and item.product:
                            # If item somehow has a product, use its category
                            item_products = [
                                p for p in products
                                if p.category_id == item.product.category_id
                            ]
                        
                        # If no products to match against, create a new product
                        if not item_products:
                            # No existing products to match - create new draft product
                            new_product = await _handle_no_match(
                                session=session,
                                item=item,
                                log=log,
                            )
                            metrics.new_products_created += 1
                            metrics.items_processed += 1
                            
                            # IMPORTANT: Add new product to the list so subsequent items
                            # in the same batch can match against it
                            products.append(new_product)
                            
                            # Queue recalculation for the new product
                            product_ids_to_recalc.append(new_product.id)
                            continue
                        
                        # Perform matching
                        match_result = matcher.find_matches(
                            item_name=item.name,
                            item_id=item.id,
                            products=item_products,
                            auto_threshold=auto_threshold,
                            potential_threshold=potential_threshold,
                            max_candidates=max_candidates,
                        )
                        
                        metrics.items_processed += 1
                        
                        # Step 5: Apply threshold logic
                        if match_result.match_status == MatchStatusEnum.AUTO_MATCHED:
                            # Auto-link to product
                            await _handle_auto_match(
                                session=session,
                                item=item,
                                match_result=match_result,
                                log=log,
                            )
                            metrics.auto_matched += 1
                            
                            # Queue recalculation for the linked product
                            if match_result.best_match:
                                product_ids_to_recalc.append(match_result.best_match.product_id)
                        
                        elif match_result.match_status == MatchStatusEnum.POTENTIAL_MATCH:
                            # Add to review queue
                            await _handle_potential_match(
                                session=session,
                                item=item,
                                match_result=match_result,
                                review_expiration_days=review_expiration_days,
                                log=log,
                            )
                            metrics.potential_matches += 1
                        
                        else:
                            # Create new draft product
                            new_product = await _handle_no_match(
                                session=session,
                                item=item,
                                log=log,
                            )
                            metrics.new_products_created += 1
                            
                            # IMPORTANT: Add new product to the list so subsequent items
                            # in the same batch can match against it
                            products.append(new_product)
                            
                            # Queue recalculation for the new product
                            product_ids_to_recalc.append(new_product.id)
                    
                    except Exception as e:
                        log.error(
                            "item_matching_failed",
                            item_id=str(item.id),
                            item_name=item.name,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        metrics.errors += 1
                        # Continue processing other items
                
                # Commit transaction
                await session.commit()
                
                log.info(
                    "match_items_task_batch_committed",
                    **metrics.to_dict(),
                )
                
                # Step 6: Enqueue aggregate recalculation for affected products
                if product_ids_to_recalc:
                    # Deduplicate product IDs
                    unique_product_ids = list(set(product_ids_to_recalc))
                    
                    # Enqueue recalc task (will be implemented in Phase 4)
                    redis: Optional[ArqRedis] = ctx.get("redis")
                    if redis:
                        await _enqueue_recalc_task(
                            redis=redis,
                            task_id=task_id,
                            product_ids=unique_product_ids,
                            trigger="auto_match",
                            log=log,
                        )
        
        metrics.duration_seconds = time.time() - start_time
        
        # Determine status
        if metrics.errors == 0:
            status = "success"
        elif metrics.items_processed > 0:
            status = "partial_success"
        else:
            status = "error"
        
        log.info(
            "match_items_task_completed",
            status=status,
            **metrics.to_dict(),
        )
        
        # Emit observability metrics
        emit_matching_duration_seconds(metrics.duration_seconds, "match_items")
        emit_items_matched_total(metrics.auto_matched, "auto_matched")
        emit_items_matched_total(metrics.potential_matches, "potential_match")
        emit_items_matched_total(metrics.new_products_created, "new_product")
        emit_items_processed_total(metrics.items_processed, status)
        emit_items_processed_total(metrics.errors, "error")
        
        return {
            "task_id": task_id,
            "status": status,
            **metrics.to_dict(),
        }
    
    except Exception as e:
        metrics.duration_seconds = time.time() - start_time
        log.error(
            "match_items_task_failed",
            error=str(e),
            error_type=type(e).__name__,
            **metrics.to_dict(),
        )
        raise


async def _handle_auto_match(
    session: AsyncSession,
    item: SupplierItem,
    match_result: MatchResult,
    log: Any,
) -> None:
    """Handle auto-match case (score ≥95%).
    
    Updates the supplier item:
    - Links to the matched product
    - Sets match_status to AUTO_MATCHED
    - Stores match_score
    
    Args:
        session: Database session
        item: SupplierItem to update
        match_result: Result from matcher
        log: Logger instance
    """
    if not match_result.best_match:
        log.warning("auto_match_no_best_match", item_id=str(item.id))
        return
    
    best_match = match_result.best_match
    
    # Update supplier item
    item.product_id = best_match.product_id
    item.match_status = MatchStatus.AUTO_MATCHED
    item.match_score = Decimal(str(round(best_match.score, 2)))
    item.match_candidates = [c.to_dict() for c in match_result.candidates]
    
    session.add(item)
    
    log.info(
        "item_auto_matched",
        item_id=str(item.id),
        item_name=item.name,
        product_id=str(best_match.product_id),
        product_name=best_match.product_name,
        score=best_match.score,
    )


async def _handle_potential_match(
    session: AsyncSession,
    item: SupplierItem,
    match_result: MatchResult,
    review_expiration_days: int,
    log: Any,
) -> None:
    """Handle potential match case (score 70-94%).
    
    Updates the supplier item and creates a review queue entry:
    - Sets match_status to POTENTIAL_MATCH
    - Stores candidates for review
    - Creates MatchReviewQueue entry with expiration
    
    Args:
        session: Database session
        item: SupplierItem to update
        match_result: Result from matcher
        review_expiration_days: Days until review expires
        log: Logger instance
    """
    # Update supplier item
    item.match_status = MatchStatus.POTENTIAL_MATCH
    if match_result.match_score:
        item.match_score = Decimal(str(round(match_result.match_score, 2)))
    item.match_candidates = [c.to_dict() for c in match_result.candidates]
    
    session.add(item)
    
    # Calculate expiration date
    expires_at = datetime.now(timezone.utc) + timedelta(days=review_expiration_days)
    
    # Check if review queue entry already exists
    existing_query = select(MatchReviewQueue).where(
        MatchReviewQueue.supplier_item_id == item.id
    )
    existing_result = await session.execute(existing_query)
    existing_review = existing_result.scalar_one_or_none()
    
    if existing_review:
        # Update existing review
        existing_review.candidate_products = [c.to_dict() for c in match_result.candidates]
        existing_review.status = ReviewStatus.PENDING
        existing_review.expires_at = expires_at
        session.add(existing_review)
    else:
        # Create new review queue entry
        review_entry = MatchReviewQueue(
            supplier_item_id=item.id,
            candidate_products=[c.to_dict() for c in match_result.candidates],
            status=ReviewStatus.PENDING,
            expires_at=expires_at,
        )
        session.add(review_entry)
    
    log.info(
        "item_potential_match",
        item_id=str(item.id),
        item_name=item.name,
        top_score=match_result.match_score,
        candidates_count=len(match_result.candidates),
        expires_at=expires_at.isoformat(),
    )


async def _handle_no_match(
    session: AsyncSession,
    item: SupplierItem,
    log: Any,
) -> Product:
    """Handle no match case (score <70%).
    
    Creates a new draft product and links the supplier item:
    - Creates Product with status=DRAFT
    - Links supplier item to new product
    - Sets match_status to AUTO_MATCHED (linked to new product)
    
    Args:
        session: Database session
        item: SupplierItem to update
        log: Logger instance
        
    Returns:
        Newly created Product
    """
    # Generate unique SKU
    internal_sku = generate_internal_sku()
    
    # Create new draft product
    new_product = Product(
        internal_sku=internal_sku,
        name=item.name,
        status=ProductStatus.DRAFT,
        # Copy category from supplier if available (would need supplier relationship)
        # For now, leave category_id as None
    )
    session.add(new_product)
    await session.flush()  # Get the product ID
    
    # Link supplier item to new product
    item.product_id = new_product.id
    item.match_status = MatchStatus.AUTO_MATCHED  # Linked to own product
    item.match_score = Decimal("100.00")  # Perfect match to self
    item.match_candidates = []
    
    session.add(item)
    
    log.info(
        "item_new_product_created",
        item_id=str(item.id),
        item_name=item.name,
        product_id=str(new_product.id),
        product_sku=new_product.internal_sku,
    )
    
    return new_product


async def _enqueue_recalc_task(
    redis: ArqRedis,
    task_id: str,
    product_ids: List[uuid.UUID],
    trigger: str,
    log: Any,
) -> None:
    """Enqueue aggregate recalculation task for products.
    
    Args:
        redis: ArqRedis connection
        task_id: Parent task ID for correlation
        product_ids: List of product UUIDs to recalculate
        trigger: What triggered the recalculation
        log: Logger instance
    """
    try:
        recalc_task_id = f"recalc-{task_id}-{int(time.time())}"
        
        # Enqueue the recalculation task
        await redis.enqueue_job(
            "recalc_product_aggregates_task",
            task_id=recalc_task_id,
            product_ids=[str(pid) for pid in product_ids],
            trigger=trigger,
        )
        
        log.debug(
            "recalc_task_enqueued",
            recalc_task_id=recalc_task_id,
            product_count=len(product_ids),
            trigger=trigger,
        )
    except Exception as e:
        log.warning(
            "recalc_task_enqueue_failed",
            error=str(e),
            product_count=len(product_ids),
        )
        # Don't raise - recalc failure shouldn't fail the matching task


@dataclass
class RecalcMetrics:
    """Metrics collected during aggregate recalculation task execution."""
    products_processed: int = 0
    products_updated: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/response."""
        return {
            "products_processed": self.products_processed,
            "products_updated": self.products_updated,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
        }


async def recalc_product_aggregates_task(
    ctx: Dict[str, Any],
    task_id: str,
    product_ids: List[str],
    trigger: str = "manual",
    retry_count: int = 0,
    max_retries: int = 3,
    **kwargs
) -> Dict[str, Any]:
    """Recalculate aggregate fields (min_price, availability) for products.
    
    This task is triggered by:
        - auto_match: After match_items_task auto-links items
        - manual_link: After admin manually links an item
        - price_change: After price update during parsing
    
    For each product, calculates:
        - min_price: MIN(current_price) of linked items
        - availability: TRUE if ANY linked item has stock
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique task identifier for logging
        product_ids: List of product UUID strings to recalculate
        trigger: What triggered the recalculation (for audit trail)
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        
    Returns:
        Dictionary with task results and metrics:
            - task_id: Task identifier
            - status: "success", "partial_success", or "error"
            - trigger: What triggered the recalculation
            - products_processed: Number of products processed
            - products_updated: Number of products successfully updated
            - errors: Number of errors
            - duration_seconds: Task duration
            - results: List of per-product results (if any errors)
    """
    start_time = time.time()
    metrics = RecalcMetrics()
    
    # Parse product_ids from strings to UUIDs
    parsed_product_ids: List[uuid.UUID] = []
    for pid_str in product_ids:
        try:
            parsed_product_ids.append(uuid.UUID(pid_str))
        except ValueError:
            logger.warning("invalid_product_id", task_id=task_id, product_id=pid_str)
    
    log = logger.bind(
        task_id=task_id,
        product_count=len(parsed_product_ids),
        trigger=trigger,
    )
    
    log.info("recalc_product_aggregates_task_started")
    
    if not parsed_product_ids:
        log.warning("no_valid_product_ids")
        return {
            "task_id": task_id,
            "status": "error",
            "trigger": trigger,
            "error": "No valid product IDs provided",
            **metrics.to_dict(),
        }
    
    # Import here to avoid circular imports
    from src.services.aggregation import calculate_product_aggregates_batch
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Calculate aggregates for all products in batch
                results = await calculate_product_aggregates_batch(
                    session=session,
                    product_ids=parsed_product_ids,
                    trigger=trigger,
                )
                
                # Process results
                for result in results:
                    metrics.products_processed += 1
                    if "error" not in result:
                        metrics.products_updated += 1
                    else:
                        metrics.errors += 1
                
                # Commit transaction
                await session.commit()
        
        metrics.duration_seconds = time.time() - start_time
        
        # Determine status
        if metrics.errors == 0:
            status = "success"
        elif metrics.products_updated > 0:
            status = "partial_success"
        else:
            status = "error"
        
        log.info(
            "recalc_product_aggregates_task_completed",
            status=status,
            **metrics.to_dict(),
        )
        
        # Emit observability metrics
        emit_matching_duration_seconds(metrics.duration_seconds, "recalc_aggregates")
        emit_items_processed_total(metrics.products_updated, "success")
        emit_items_processed_total(metrics.errors, "error")
        
        response = {
            "task_id": task_id,
            "status": status,
            "trigger": trigger,
            **metrics.to_dict(),
        }
        
        # Include detailed results if there were errors
        if metrics.errors > 0:
            response["results"] = results
        
        return response
    
    except Exception as e:
        metrics.duration_seconds = time.time() - start_time
        log.error(
            "recalc_product_aggregates_task_failed",
            error=str(e),
            error_type=type(e).__name__,
            **metrics.to_dict(),
        )
        raise


@dataclass
class EnrichMetrics:
    """Metrics collected during enrichment task execution."""
    features_extracted: int = 0
    characteristics_updated: bool = False
    extractors_applied: List[str] = None
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.extractors_applied is None:
            self.extractors_applied = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/response."""
        return {
            "features_extracted": self.features_extracted,
            "characteristics_updated": self.characteristics_updated,
            "extractors_applied": self.extractors_applied,
            "duration_seconds": round(self.duration_seconds, 3),
        }


async def enrich_item_task(
    ctx: Dict[str, Any],
    task_id: str,
    supplier_item_id: str,
    extractors: Optional[List[str]] = None,
    preserve_existing: bool = True,
    retry_count: int = 0,
    max_retries: int = 3,
    **kwargs
) -> Dict[str, Any]:
    """Extract and enrich characteristics for a supplier item.
    
    This task applies feature extractors to the supplier item's name
    and merges extracted features into the characteristics JSONB field.
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique task identifier for logging
        supplier_item_id: UUID string of the supplier item to enrich
        extractors: List of extractor names to apply (default: all)
        preserve_existing: If True, don't overwrite existing characteristics
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        
    Returns:
        Dictionary with task results:
            - task_id: Task identifier
            - status: "success" or "error"
            - supplier_item_id: Item that was processed
            - features_extracted: Count of features found
            - characteristics_updated: Whether DB was updated
            - extractors_applied: List of extractors that found data
    """
    start_time = time.time()
    metrics = EnrichMetrics()
    
    # Parse UUID
    try:
        item_uuid = uuid.UUID(supplier_item_id)
    except ValueError:
        logger.error("invalid_supplier_item_id", task_id=task_id, supplier_item_id=supplier_item_id)
        return {
            "task_id": task_id,
            "status": "error",
            "error": f"Invalid supplier_item_id: {supplier_item_id}",
            **metrics.to_dict(),
        }
    
    # Default to all extractors
    if extractors is None:
        extractors = ["electronics", "dimensions"]
    
    log = logger.bind(
        task_id=task_id,
        supplier_item_id=supplier_item_id,
        extractors=extractors,
    )
    
    log.info("enrich_item_task_started")
    
    # Import here to avoid circular imports
    from src.services.extraction import extract_all_features
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Fetch the supplier item
                query = (
                    select(SupplierItem)
                    .where(SupplierItem.id == item_uuid)
                    .with_for_update()
                )
                result = await session.execute(query)
                item = result.scalar_one_or_none()
                
                if not item:
                    log.warning("supplier_item_not_found")
                    return {
                        "task_id": task_id,
                        "status": "error",
                        "supplier_item_id": supplier_item_id,
                        "error": "Supplier item not found",
                        **metrics.to_dict(),
                    }
                
                # Extract features from item name
                extracted = extract_all_features(
                    text=item.name,
                    extractors=extractors,
                )
                
                if not extracted.has_any_features():
                    log.info("no_features_extracted")
                    metrics.duration_seconds = time.time() - start_time
                    return {
                        "task_id": task_id,
                        "status": "success",
                        "supplier_item_id": supplier_item_id,
                        **metrics.to_dict(),
                    }
                
                # Convert to characteristics format
                new_characteristics = extracted.to_characteristics()
                
                # Merge with existing characteristics
                current = item.characteristics or {}
                
                if preserve_existing:
                    # Only add new keys, don't overwrite existing
                    merged = {**current}
                    for key, value in new_characteristics.items():
                        if key not in merged or merged[key] is None:
                            merged[key] = value
                            metrics.features_extracted += 1
                else:
                    # New values overwrite existing
                    merged = {**current, **new_characteristics}
                    metrics.features_extracted = len(new_characteristics)
                
                # Update if there are changes
                if merged != current:
                    item.characteristics = merged
                    session.add(item)
                    metrics.characteristics_updated = True
                    
                    # Track which extractors contributed
                    if extracted.voltage is not None or extracted.power_watts is not None:
                        metrics.extractors_applied.append("electronics")
                    if extracted.weight_kg is not None or extracted.dimensions_cm is not None:
                        metrics.extractors_applied.append("dimensions")
                
                await session.commit()
        
        metrics.duration_seconds = time.time() - start_time
        
        log.info(
            "enrich_item_task_completed",
            status="success",
            **metrics.to_dict(),
        )
        
        # Emit observability metrics
        emit_matching_duration_seconds(metrics.duration_seconds, "enrich_item")
        emit_items_processed_total(1 if metrics.characteristics_updated else 0, "success")
        emit_metric("features_extracted_total", metrics.features_extracted)
        
        return {
            "task_id": task_id,
            "status": "success",
            "supplier_item_id": supplier_item_id,
            **metrics.to_dict(),
        }
    
    except Exception as e:
        metrics.duration_seconds = time.time() - start_time
        log.error(
            "enrich_item_task_failed",
            error=str(e),
            error_type=type(e).__name__,
            **metrics.to_dict(),
        )
        raise


async def handle_manual_match_event(
    ctx: Dict[str, Any],
    task_id: str,
    supplier_item_id: str,
    action: str,
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    new_product_name: Optional[str] = None,
    retry_count: int = 0,
    max_retries: int = 3,
    **kwargs
) -> Dict[str, Any]:
    """Handle manual match events from users (link, unlink, approve, reject, reset).
    
    This task processes manual operations on supplier items:
        - link: Manually link item to product (sets verified_match)
        - unlink: Manually unlink item from product (clears link)
        - reset_match: Reset verified_match back to unmatched (admin only)
        - approve_match: Approve potential match from review queue (sets verified_match)
        - reject_match: Reject potential match and create new product
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique task identifier for logging
        supplier_item_id: UUID string of the supplier item
        action: Action to perform (link, unlink, reset_match, approve_match, reject_match)
        product_id: Product UUID string (required for link/approve_match)
        user_id: User UUID string who performed the action (for audit)
        new_product_name: Product name for reject_match (optional, defaults to item name)
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts
        
    Returns:
        Dictionary with task results:
            - task_id: Task identifier
            - status: "success" or "error"
            - action: Action that was performed
            - supplier_item_id: Item that was processed
            - product_id: Linked product (if applicable)
            - previous_product_id: Previous product (for unlink)
            - user_id: User who performed the action
    """
    start_time = time.time()
    
    # Validate action
    valid_actions = {"link", "unlink", "reset_match", "approve_match", "reject_match"}
    if action not in valid_actions:
        logger.error("invalid_action", task_id=task_id, action=action)
        return {
            "task_id": task_id,
            "status": "error",
            "error": f"Invalid action: {action}. Valid: {valid_actions}",
        }
    
    # Parse UUIDs
    try:
        item_uuid = uuid.UUID(supplier_item_id)
    except ValueError:
        logger.error("invalid_supplier_item_id", task_id=task_id, supplier_item_id=supplier_item_id)
        return {
            "task_id": task_id,
            "status": "error",
            "error": f"Invalid supplier_item_id: {supplier_item_id}",
        }
    
    product_uuid: Optional[uuid.UUID] = None
    if product_id:
        try:
            product_uuid = uuid.UUID(product_id)
        except ValueError:
            logger.error("invalid_product_id", task_id=task_id, product_id=product_id)
            return {
                "task_id": task_id,
                "status": "error",
                "error": f"Invalid product_id: {product_id}",
            }
    
    user_uuid: Optional[uuid.UUID] = None
    if user_id:
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            logger.warning("invalid_user_id", task_id=task_id, user_id=user_id)
            # Don't fail - user_id is optional for audit
    
    log = logger.bind(
        task_id=task_id,
        action=action,
        supplier_item_id=supplier_item_id,
        product_id=product_id,
        user_id=user_id,
    )
    
    log.info("handle_manual_match_event_started")
    
    # Validate action-specific requirements
    if action in {"link", "approve_match"} and not product_uuid:
        log.error("product_id_required_for_action")
        return {
            "task_id": task_id,
            "status": "error",
            "error": f"product_id is required for action '{action}'",
        }
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Fetch the supplier item with lock
                query = (
                    select(SupplierItem)
                    .where(SupplierItem.id == item_uuid)
                    .with_for_update()
                )
                result = await session.execute(query)
                item = result.scalar_one_or_none()
                
                if not item:
                    log.warning("supplier_item_not_found")
                    return {
                        "task_id": task_id,
                        "status": "error",
                        "supplier_item_id": supplier_item_id,
                        "action": action,
                        "error": "Supplier item not found",
                    }
                
                # Track previous product for aggregate recalculation
                previous_product_id = item.product_id
                products_to_recalc: List[uuid.UUID] = []
                
                # Execute action
                if action == "link":
                    # Manual link: link item to product, set verified_match
                    item.product_id = product_uuid
                    item.match_status = MatchStatus.VERIFIED_MATCH
                    item.match_score = Decimal("100.00")  # Manual = perfect confidence
                    session.add(item)
                    
                    # Recalc new product
                    if product_uuid:
                        products_to_recalc.append(product_uuid)
                    # Recalc old product if it was different
                    if previous_product_id and previous_product_id != product_uuid:
                        products_to_recalc.append(previous_product_id)
                    
                    log.info(
                        "manual_link_applied",
                        previous_product_id=str(previous_product_id) if previous_product_id else None,
                        new_product_id=str(product_uuid),
                    )
                
                elif action == "unlink":
                    # Manual unlink: remove link, set to unmatched
                    item.product_id = None
                    item.match_status = MatchStatus.UNMATCHED
                    item.match_score = None
                    item.match_candidates = None
                    session.add(item)
                    
                    # Recalc old product
                    if previous_product_id:
                        products_to_recalc.append(previous_product_id)
                    
                    log.info(
                        "manual_unlink_applied",
                        previous_product_id=str(previous_product_id) if previous_product_id else None,
                    )
                
                elif action == "reset_match":
                    # Admin reset: set verified_match back to unmatched for re-matching
                    if item.match_status != MatchStatus.VERIFIED_MATCH:
                        log.warning("item_not_verified_match", current_status=item.match_status.value)
                    
                    item.match_status = MatchStatus.UNMATCHED
                    item.match_score = None
                    item.match_candidates = None
                    # Keep product_id - just reset the match status
                    session.add(item)
                    
                    log.info("match_reset_applied")
                
                elif action == "approve_match":
                    # Approve from review queue: link to selected product, set verified_match
                    item.product_id = product_uuid
                    item.match_status = MatchStatus.VERIFIED_MATCH
                    session.add(item)
                    
                    # Update review queue entry if exists
                    review_query = select(MatchReviewQueue).where(
                        MatchReviewQueue.supplier_item_id == item_uuid
                    )
                    review_result = await session.execute(review_query)
                    review_entry = review_result.scalar_one_or_none()
                    
                    if review_entry:
                        review_entry.status = ReviewStatus.APPROVED
                        review_entry.reviewed_by = user_uuid
                        review_entry.reviewed_at = datetime.now(timezone.utc)
                        session.add(review_entry)
                    
                    # Recalc new product
                    if product_uuid:
                        products_to_recalc.append(product_uuid)
                    # Recalc old product if different
                    if previous_product_id and previous_product_id != product_uuid:
                        products_to_recalc.append(previous_product_id)
                    
                    log.info(
                        "match_approved",
                        new_product_id=str(product_uuid),
                    )
                
                elif action == "reject_match":
                    # Reject from review queue: create new product and link
                    product_name = new_product_name or item.name
                    internal_sku = generate_internal_sku()
                    
                    new_product = Product(
                        internal_sku=internal_sku,
                        name=product_name,
                        status=ProductStatus.DRAFT,
                    )
                    session.add(new_product)
                    await session.flush()  # Get the product ID
                    
                    # Link item to new product
                    item.product_id = new_product.id
                    item.match_status = MatchStatus.VERIFIED_MATCH
                    item.match_score = Decimal("100.00")
                    item.match_candidates = None
                    session.add(item)
                    
                    # Update review queue entry if exists
                    review_query = select(MatchReviewQueue).where(
                        MatchReviewQueue.supplier_item_id == item_uuid
                    )
                    review_result = await session.execute(review_query)
                    review_entry = review_result.scalar_one_or_none()
                    
                    if review_entry:
                        review_entry.status = ReviewStatus.REJECTED
                        review_entry.reviewed_by = user_uuid
                        review_entry.reviewed_at = datetime.now(timezone.utc)
                        session.add(review_entry)
                    
                    # Recalc new product
                    products_to_recalc.append(new_product.id)
                    # Recalc old product if was linked
                    if previous_product_id:
                        products_to_recalc.append(previous_product_id)
                    
                    product_uuid = new_product.id  # For response
                    
                    log.info(
                        "match_rejected_new_product_created",
                        new_product_id=str(new_product.id),
                        new_product_sku=new_product.internal_sku,
                    )
                
                await session.commit()
                
                # Enqueue aggregate recalculation for affected products
                if products_to_recalc:
                    redis: Optional[ArqRedis] = ctx.get("redis")
                    if redis:
                        await _enqueue_recalc_task(
                            redis=redis,
                            task_id=task_id,
                            product_ids=list(set(products_to_recalc)),
                            trigger=f"manual_{action}",
                            log=log,
                        )
        
        duration_seconds = time.time() - start_time
        
        log.info(
            "handle_manual_match_event_completed",
            status="success",
            duration_seconds=round(duration_seconds, 3),
        )
        
        return {
            "task_id": task_id,
            "status": "success",
            "action": action,
            "supplier_item_id": supplier_item_id,
            "product_id": str(product_uuid) if product_uuid else None,
            "previous_product_id": str(previous_product_id) if previous_product_id else None,
            "user_id": user_id,
            "duration_seconds": round(duration_seconds, 3),
        }
    
    except Exception as e:
        duration_seconds = time.time() - start_time
        log.error(
            "handle_manual_match_event_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration_seconds, 3),
        )
        raise


async def expire_review_queue_task(
    ctx: Dict[str, Any],
    task_id: str,
    **kwargs
) -> Dict[str, Any]:
    """Expire old review queue items that have passed their expiration date.
    
    This task runs as a cron job to mark pending review items as expired
    when their expires_at timestamp has passed.
    
    Args:
        ctx: Worker context (contains Redis connection)
        task_id: Unique task identifier for logging
        
    Returns:
        Dictionary with task results:
            - task_id: Task identifier
            - status: "success" or "error"
            - expired_count: Number of items expired
            - duration_seconds: Task duration
    """
    start_time = time.time()
    
    log = logger.bind(task_id=task_id)
    log.info("expire_review_queue_task_started")
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                # Update all pending items that have expired
                now = datetime.now(timezone.utc)
                
                update_stmt = (
                    update(MatchReviewQueue)
                    .where(
                        and_(
                            MatchReviewQueue.status == ReviewStatus.PENDING,
                            MatchReviewQueue.expires_at < now,
                        )
                    )
                    .values(status=ReviewStatus.EXPIRED)
                )
                
                result = await session.execute(update_stmt)
                expired_count = result.rowcount
                
                await session.commit()
        
        duration_seconds = time.time() - start_time
        
        log.info(
            "expire_review_queue_task_completed",
            status="success",
            expired_count=expired_count,
            duration_seconds=round(duration_seconds, 3),
        )
        
        # Emit observability metrics
        emit_matching_duration_seconds(duration_seconds, "expire_review_queue")
        emit_metric("review_queue_expired_total", expired_count)
        
        return {
            "task_id": task_id,
            "status": "success",
            "expired_count": expired_count,
            "duration_seconds": round(duration_seconds, 3),
        }
    
    except Exception as e:
        duration_seconds = time.time() - start_time
        log.error(
            "expire_review_queue_task_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration_seconds, 3),
        )
        raise

