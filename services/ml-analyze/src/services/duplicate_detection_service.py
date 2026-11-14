"""
Duplicate Detection Service
===========================

Detects and flags potential duplicate products created by auto-creation logic.
Replaces the old "Unmatched Items" queue with a "Potential Duplicates" queue.

Phase 11: Pipeline Stabilization - US2 Auto-Creation + Duplicate Detection

Tasks: T059-T065
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from rapidfuzz import fuzz
from sqlalchemy import select, insert, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PotentialDuplicate
from src.schemas.duplicate import DuplicateDetectionStats
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Detection thresholds from spec
DUPLICATE_SIMILARITY_MIN = 85  # Minimum similarity to flag (0-100)
DUPLICATE_SIMILARITY_MAX = 90  # Maximum similarity (>=90% is auto-matched, not duplicate)
DUPLICATE_PRICE_DIFF_MAX = 0.20  # Maximum price difference (20%)


@dataclass
class DuplicateCandidate:
    """A product candidate for duplicate comparison."""
    
    id: UUID
    name: str
    category_id: Optional[UUID]
    price: Decimal
    has_variants: bool
    variant_schema: Optional[list]


class DuplicateDetectionService:
    """
    Service for detecting potential duplicate products after auto-creation.
    
    Detects duplicates based on:
    - Name similarity: 85% ≤ similarity < 90% (RapidFuzz WRatio)
    - Same category_id
    - NOT already grouped as variants
    - Price difference < 20%
    
    Features:
    - Category-scoped comparison (reduces O(n²) to O(k²) per category)
    - Ordered ID constraint to prevent (A,B) and (B,A) duplicates
    - Already-flagged pair detection to avoid duplicate entries
    
    Usage:
        async with get_session() as session:
            service = DuplicateDetectionService(session)
            stats = await service.detect_duplicates(created_product_ids)
    """
    
    def __init__(
        self,
        session: AsyncSession,
        similarity_min: float = DUPLICATE_SIMILARITY_MIN,
        similarity_max: float = DUPLICATE_SIMILARITY_MAX,
        price_diff_max: float = DUPLICATE_PRICE_DIFF_MAX,
    ) -> None:
        """
        Initialize DuplicateDetectionService.
        
        Args:
            session: SQLAlchemy async session
            similarity_min: Minimum similarity threshold (default 85)
            similarity_max: Maximum similarity threshold (default 90)
            price_diff_max: Maximum price difference ratio (default 0.20)
        """
        self._session = session
        self._similarity_min = similarity_min
        self._similarity_max = similarity_max
        self._price_diff_max = price_diff_max
    
    async def detect_duplicates(
        self,
        created_product_ids: list[UUID],
    ) -> DuplicateDetectionStats:
        """
        Detect potential duplicates among newly created products.
        
        For each created product:
        1. Get candidates in the same category
        2. Compute name similarity
        3. Check price difference
        4. Verify not already variants
        5. Flag if criteria met
        
        Args:
            created_product_ids: IDs of products to check for duplicates
        
        Returns:
            DuplicateDetectionStats with counts
        """
        import time
        start_time = time.perf_counter()
        
        logger.info(
            "duplicate_detection.starting",
            product_count=len(created_product_ids),
        )
        
        stats = DuplicateDetectionStats(
            duplicates_flagged=0,
            false_positives_estimated=0,
        )
        
        if not created_product_ids:
            return stats
        
        # Get all created products
        products = await self._get_products_by_ids(created_product_ids)
        
        if not products:
            logger.warning("duplicate_detection.no_products_found")
            return stats
        
        # Group products by category for efficient comparison
        products_by_category: dict[Optional[UUID], list[DuplicateCandidate]] = {}
        for p in products:
            cat_id = p.category_id
            if cat_id not in products_by_category:
                products_by_category[cat_id] = []
            products_by_category[cat_id].append(p)
        
        # T060: Detect duplicates within each category scope
        for category_id, category_products in products_by_category.items():
            # Get all products in this category (not just newly created)
            all_category_products = await self._get_products_in_category(category_id)
            
            # Compare each created product against all category products
            for product in category_products:
                await self._compare_product_against_category(
                    product=product,
                    category_products=all_category_products,
                    stats=stats,
                )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "duplicate_detection.complete",
            duplicates_flagged=stats.duplicates_flagged,
            products_checked=len(created_product_ids),
            duration_ms=round(duration_ms, 2),
            avg_ms_per_product=round(duration_ms / len(created_product_ids), 2) if created_product_ids else 0,
        )
        
        # T137: Performance threshold check (30 seconds = 30000ms)
        if duration_ms > 30000:
            logger.warning(
                "duplicate_detection.slow_performance",
                duration_ms=round(duration_ms, 2),
                product_count=len(created_product_ids),
                threshold_ms=30000,
            )
        
        return stats
    
    async def _get_products_by_ids(
        self,
        product_ids: list[UUID],
    ) -> list[DuplicateCandidate]:
        """
        Fetch products by IDs.
        
        Args:
            product_ids: List of product UUIDs
        
        Returns:
            List of DuplicateCandidate objects
        """
        query = text("""
            SELECT id, name, category_id, 
                   COALESCE(
                       (SELECT MIN(current_price) 
                        FROM supplier_items 
                        WHERE product_id = products.id),
                       0
                   ) as price,
                   has_variants, variant_schema
            FROM products
            WHERE id = ANY(:ids)
            AND status != 'archived'
        """)
        
        result = await self._session.execute(
            query,
            {"ids": [str(pid) for pid in product_ids]},
        )
        
        rows = result.fetchall()
        return [
            DuplicateCandidate(
                id=UUID(row.id) if isinstance(row.id, str) else row.id,
                name=row.name,
                category_id=UUID(row.category_id) if row.category_id else None,
                price=Decimal(str(row.price)) if row.price else Decimal("0"),
                has_variants=row.has_variants or False,
                variant_schema=row.variant_schema,
            )
            for row in rows
        ]
    
    async def _get_products_in_category(
        self,
        category_id: Optional[UUID],
    ) -> list[DuplicateCandidate]:
        """
        Get all products in a category for comparison.
        
        Args:
            category_id: Category UUID (None for uncategorized)
        
        Returns:
            List of DuplicateCandidate objects
        """
        if category_id is None:
            query = text("""
                SELECT id, name, category_id,
                       COALESCE(
                           (SELECT MIN(current_price) 
                            FROM supplier_items 
                            WHERE product_id = products.id),
                           0
                       ) as price,
                       has_variants, variant_schema
                FROM products
                WHERE category_id IS NULL
                AND status != 'archived'
            """)
            result = await self._session.execute(query)
        else:
            query = text("""
                SELECT id, name, category_id,
                       COALESCE(
                           (SELECT MIN(current_price) 
                            FROM supplier_items 
                            WHERE product_id = products.id),
                           0
                       ) as price,
                       has_variants, variant_schema
                FROM products
                WHERE category_id = :category_id
                AND status != 'archived'
            """)
            result = await self._session.execute(
                query,
                {"category_id": str(category_id)},
            )
        
        rows = result.fetchall()
        return [
            DuplicateCandidate(
                id=UUID(row.id) if isinstance(row.id, str) else row.id,
                name=row.name,
                category_id=UUID(row.category_id) if row.category_id else None,
                price=Decimal(str(row.price)) if row.price else Decimal("0"),
                has_variants=row.has_variants or False,
                variant_schema=row.variant_schema,
            )
            for row in rows
        ]
    
    async def _compare_product_against_category(
        self,
        product: DuplicateCandidate,
        category_products: list[DuplicateCandidate],
        stats: DuplicateDetectionStats,
    ) -> None:
        """
        Compare a product against all products in its category.
        
        Args:
            product: Product to compare
            category_products: All products in the same category
            stats: Stats object to update
        """
        for candidate in category_products:
            # Skip self-comparison
            if candidate.id == product.id:
                continue
            
            # T061: Compute similarity using RapidFuzz WRatio
            similarity = self.compute_similarity(product.name, candidate.name)
            
            # Check if within duplicate threshold (85-90%)
            if not (self._similarity_min <= similarity < self._similarity_max):
                continue
            
            # T062: Check price difference
            price_diff = self.compute_price_diff(product, candidate)
            if price_diff >= self._price_diff_max:
                continue
            
            # T063: Check if already variants
            if await self.are_variants(product.id, candidate.id):
                continue
            
            # T064: Flag as potential duplicate
            flagged = await self.flag_duplicate(
                product_id_1=product.id,
                product_id_2=candidate.id,
                similarity_score=similarity,
            )
            
            if flagged:
                stats.duplicates_flagged += 1
    
    def compute_similarity(self, name1: str, name2: str) -> float:
        """
        Compute name similarity using RapidFuzz WRatio.
        
        T061: Uses WRatio for robust substring matching.
        
        Args:
            name1: First product name
            name2: Second product name
        
        Returns:
            Similarity score (0-100)
        """
        return fuzz.WRatio(name1.lower(), name2.lower())
    
    def compute_price_diff(
        self,
        product1: DuplicateCandidate,
        product2: DuplicateCandidate,
    ) -> float:
        """
        Compute relative price difference between products.
        
        T062: Returns absolute percentage difference.
        
        Args:
            product1: First product
            product2: Second product
        
        Returns:
            Price difference as ratio (0.0 = same, 0.20 = 20% different)
        """
        p1 = float(product1.price)
        p2 = float(product2.price)
        
        # Handle zero prices
        if p1 == 0 and p2 == 0:
            return 0.0
        if p1 == 0 or p2 == 0:
            return 1.0  # Max difference
        
        # Compute relative difference
        return abs(p1 - p2) / max(p1, p2)
    
    async def are_variants(
        self,
        product_id_1: UUID,
        product_id_2: UUID,
    ) -> bool:
        """
        Check if two products are already grouped as variants.
        
        T063: Products are variants if:
        - Both have has_variants=true AND
        - They share the same variant_schema structure
        
        Args:
            product_id_1: First product ID
            product_id_2: Second product ID
        
        Returns:
            True if products are in the same variant group
        """
        query = text("""
            SELECT p1.has_variants, p1.variant_schema,
                   p2.has_variants, p2.variant_schema
            FROM products p1
            JOIN products p2 ON 1=1
            WHERE p1.id = :id1 AND p2.id = :id2
        """)
        
        result = await self._session.execute(
            query,
            {"id1": str(product_id_1), "id2": str(product_id_2)},
        )
        row = result.fetchone()
        
        if not row:
            return False
        
        p1_has_variants = row[0] or False
        p1_schema = row[1]
        p2_has_variants = row[2] or False
        p2_schema = row[3]
        
        # Both must have variants and same schema structure
        if p1_has_variants and p2_has_variants:
            # Compare schemas (JSON comparison)
            if p1_schema and p2_schema:
                return p1_schema == p2_schema
        
        return False
    
    async def flag_duplicate(
        self,
        product_id_1: UUID,
        product_id_2: UUID,
        similarity_score: float,
    ) -> bool:
        """
        Flag a product pair as potential duplicates.
        
        T064: Ensures product_id_1 < product_id_2 to prevent
        duplicate entries for (A,B) and (B,A).
        
        T065: Checks if pair is already flagged before inserting.
        
        Args:
            product_id_1: First product ID
            product_id_2: Second product ID
            similarity_score: Name similarity score
        
        Returns:
            True if newly flagged, False if already exists
        """
        # T064: Ensure ordered IDs
        if str(product_id_1) > str(product_id_2):
            product_id_1, product_id_2 = product_id_2, product_id_1
        
        # T065: Check if already flagged
        check_query = text("""
            SELECT id FROM potential_duplicates
            WHERE product_id_1 = :id1 AND product_id_2 = :id2
        """)
        
        result = await self._session.execute(
            check_query,
            {"id1": str(product_id_1), "id2": str(product_id_2)},
        )
        
        if result.fetchone():
            logger.debug(
                "duplicate_detection.already_flagged",
                product_id_1=str(product_id_1),
                product_id_2=str(product_id_2),
            )
            return False
        
        # Insert new duplicate record
        insert_query = text("""
            INSERT INTO potential_duplicates (
                id, product_id_1, product_id_2, 
                similarity_score, detection_reason, status, created_at
            )
            VALUES (
                :id, :id1, :id2, 
                :similarity, 'auto_creation_similarity', 'pending', NOW()
            )
        """)
        
        await self._session.execute(
            insert_query,
            {
                "id": str(uuid4()),
                "id1": str(product_id_1),
                "id2": str(product_id_2),
                "similarity": similarity_score,
            },
        )
        
        await self._session.commit()
        
        logger.info(
            "duplicate_detection.flagged",
            product_id_1=str(product_id_1),
            product_id_2=str(product_id_2),
            similarity_score=round(similarity_score, 2),
        )
        
        return True


# Convenience function
async def detect_duplicates(
    session: AsyncSession,
    product_ids: list[UUID],
) -> DuplicateDetectionStats:
    """
    Convenience function to detect duplicates for a list of products.
    
    Args:
        session: Database session
        product_ids: Products to check
    
    Returns:
        Detection statistics
    """
    service = DuplicateDetectionService(session)
    return await service.detect_duplicates(product_ids)
