"""
Ingestion Orchestrator
======================

Orchestrates the post-ingestion workflow including:
- Variant detection for newly created products
- Cross-batch variant grouping within categories
- Product variant record creation

Phase 11: Pipeline Stabilization - US4 Variant Detection Integration

Tasks: T113-T123
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.services.variant_detection_service import (
    VariantDetectionService,
    VariantGroup,
    VariantCandidate,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VariantDetectionStats:
    """Statistics from variant detection operations."""
    
    products_analyzed: int = 0
    variant_groups_created: int = 0
    products_grouped: int = 0
    variants_created: int = 0
    errors: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "products_analyzed": self.products_analyzed,
            "variant_groups_created": self.variant_groups_created,
            "products_grouped": self.products_grouped,
            "variants_created": self.variants_created,
            "errors": self.errors,
        }


@dataclass
class ProductData:
    """Internal representation of a product for variant detection."""
    
    id: UUID
    name: str
    price: float
    category_id: Optional[UUID]
    variant_attributes: dict = field(default_factory=dict)
    has_variants: bool = False


class IngestionOrchestrator:
    """
    Orchestrates post-ingestion workflows including variant detection.
    
    After products are auto-created, this orchestrator:
    1. Detects which products should be grouped as variants
    2. Creates product_variants records linking them
    3. Updates parent products with has_variants=true and variant_schema
    
    Usage:
        async with get_session() as session:
            orchestrator = IngestionOrchestrator(session)
            stats = await orchestrator.on_batch_complete(
                batch_id="job-123",
                created_product_ids=[uuid1, uuid2, ...],
            )
            print(f"Created {stats.variant_groups_created} variant groups")
    """
    
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize IngestionOrchestrator.
        
        Args:
            session: SQLAlchemy async session
            settings: Application settings (optional)
        """
        self._session = session
        self._settings = settings or get_settings()
        
        # T114: Import existing VariantDetectionService
        self._variant_service = VariantDetectionService(session)
        
        # T123: Metrics tracking
        self._stats = VariantDetectionStats()
        
        # Feature flag check
        self._enabled = self._settings.variant_detection_enabled
        
        logger.debug(
            "ingestion_orchestrator.initialized",
            variant_detection_enabled=self._enabled,
        )
    
    def get_stats(self) -> VariantDetectionStats:
        """Get current variant detection statistics."""
        return self._stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = VariantDetectionStats()
    
    async def on_batch_complete(
        self,
        batch_id: str,
        created_product_ids: list[UUID],
    ) -> VariantDetectionStats:
        """
        T115: Hook called after a batch of products is created.
        
        Runs variant detection for newly created products and groups
        them with existing products in the same categories.
        
        Args:
            batch_id: Identifier for the current batch/job
            created_product_ids: List of product IDs created in this batch
        
        Returns:
            VariantDetectionStats with metrics about the operation
        """
        if not self._enabled:
            logger.info(
                "ingestion_orchestrator.variant_detection_disabled",
                batch_id=batch_id,
            )
            return self._stats
        
        if not created_product_ids:
            logger.info(
                "ingestion_orchestrator.no_products_to_process",
                batch_id=batch_id,
            )
            return self._stats
        
        logger.info(
            "ingestion_orchestrator.starting_variant_detection",
            batch_id=batch_id,
            product_count=len(created_product_ids),
        )
        
        try:
            # T116: Query categories of newly created products
            category_ids = await self._get_categories_for_products(created_product_ids)
            
            if not category_ids:
                logger.info(
                    "ingestion_orchestrator.no_categories_found",
                    batch_id=batch_id,
                )
                return self._stats
            
            # T117: Query all products in same categories for cross-batch detection
            all_products = await self._get_products_in_categories(category_ids)
            
            self._stats.products_analyzed = len(all_products)
            
            if len(all_products) < 2:
                logger.info(
                    "ingestion_orchestrator.insufficient_products_for_variants",
                    batch_id=batch_id,
                    product_count=len(all_products),
                )
                return self._stats
            
            # Convert products to VariantCandidates
            candidates = self._build_candidates(all_products)
            
            # T118: Call variant detection service
            groups = self._variant_service.group_variants(candidates)
            
            logger.info(
                "ingestion_orchestrator.variant_groups_detected",
                batch_id=batch_id,
                group_count=len(groups),
            )
            
            # T119-T120: Store variant groups and update products
            for group in groups:
                await self._store_variant_group(group, all_products)
            
            # Commit all changes
            await self._session.commit()
            
            logger.info(
                "ingestion_orchestrator.variant_detection_complete",
                batch_id=batch_id,
                stats=self._stats.to_dict(),
            )
            
        except Exception as e:
            await self._session.rollback()
            self._stats.errors += 1
            
            logger.error(
                "ingestion_orchestrator.variant_detection_failed",
                batch_id=batch_id,
                error=str(e),
            )
            raise
        
        return self._stats
    
    async def _get_categories_for_products(
        self,
        product_ids: list[UUID],
    ) -> list[UUID]:
        """
        T116: Query categories of the specified products.
        
        Args:
            product_ids: List of product IDs to query
        
        Returns:
            List of unique category IDs (excluding NULL)
        """
        query = text("""
            SELECT DISTINCT category_id
            FROM products
            WHERE id = ANY(:product_ids)
              AND category_id IS NOT NULL
        """)
        
        result = await self._session.execute(
            query,
            {"product_ids": [str(pid) for pid in product_ids]},
        )
        
        rows = result.fetchall()
        return [UUID(str(row[0])) for row in rows if row[0]]
    
    async def _get_products_in_categories(
        self,
        category_ids: list[UUID],
    ) -> list[ProductData]:
        """
        T117: Query all products in the specified categories.
        
        Returns products for cross-batch variant detection.
        Excludes products that already have variants (to avoid re-grouping).
        
        Args:
            category_ids: List of category IDs to query
        
        Returns:
            List of ProductData for variant detection
        """
        query = text("""
            SELECT 
                p.id,
                p.name,
                p.category_id,
                p.has_variants,
                p.variant_schema,
                COALESCE(
                    (
                        SELECT AVG(si.current_price::numeric)
                        FROM supplier_items si
                        WHERE si.product_id = p.id
                    ),
                    0
                ) as avg_price
            FROM products p
            WHERE p.category_id = ANY(:category_ids)
              AND p.status = 'active'
              AND p.has_variants = false
            ORDER BY p.name
        """)
        
        result = await self._session.execute(
            query,
            {"category_ids": [str(cid) for cid in category_ids]},
        )
        
        products = []
        for row in result.fetchall():
            products.append(ProductData(
                id=UUID(str(row[0])),
                name=row[1],
                category_id=UUID(str(row[2])) if row[2] else None,
                has_variants=row[3] or False,
                price=float(row[5]) if row[5] else 0.0,
            ))
        
        return products
    
    def _build_candidates(
        self,
        products: list[ProductData],
    ) -> list[VariantCandidate]:
        """
        Convert ProductData to VariantCandidate for variant detection.
        
        Extracts variant attributes from product names using the
        VariantDetectionService's regex patterns.
        
        Args:
            products: List of products to convert
        
        Returns:
            List of VariantCandidates for grouping
        """
        candidates = []
        for product in products:
            # Extract variant attributes from product name
            attrs = self._variant_service.extract_variant_attributes_from_name(
                product.name
            )
            
            candidates.append(VariantCandidate(
                supplier_item_id=product.id,  # Using product.id here
                name=product.name,
                price=product.price,
                variant_attributes=attrs,
            ))
        
        return candidates
    
    async def _store_variant_group(
        self,
        group: VariantGroup,
        all_products: list[ProductData],
    ) -> None:
        """
        T119-T120: Store a variant group in the database.
        
        Creates product_variants records and updates the parent product
        with has_variants=true and variant_schema.
        
        Strategy:
        - First product in group becomes the "parent" (has_variants=true)
        - All variants (including first) get entries in product_variants
        - supplier_items get linked to their variant record
        
        Args:
            group: VariantGroup from detection service
            all_products: Full list of products for ID lookup
        """
        if len(group.variants) < 2:
            return
        
        # Build a map from name to product_id for quick lookup
        product_map = {p.name: p.id for p in all_products}
        
        # Get product IDs for this group
        variant_product_ids = []
        for variant in group.variants:
            product_id = product_map.get(variant["name"])
            if product_id:
                variant_product_ids.append((product_id, variant))
        
        if len(variant_product_ids) < 2:
            # Not enough products found - skip
            return
        
        # First product becomes the parent
        parent_product_id = variant_product_ids[0][0]
        
        # T120: Update parent product with has_variants=true and variant_schema
        await self._update_parent_product(
            parent_product_id,
            group.variant_schema,
        )
        
        # T119: Create product_variants records for each variant
        for display_order, (product_id, variant_data) in enumerate(variant_product_ids):
            await self._create_product_variant(
                parent_product_id=parent_product_id,
                variant_key=variant_data["key"],
                variant_attributes=variant_data["attributes"],
                display_order=display_order,
                linked_product_id=product_id,
            )
        
        # Update stats
        self._stats.variant_groups_created += 1
        self._stats.products_grouped += len(variant_product_ids)
        self._stats.variants_created += len(variant_product_ids)
        
        logger.info(
            "ingestion_orchestrator.variant_group_stored",
            parent_product_id=str(parent_product_id),
            variant_count=len(variant_product_ids),
            variant_schema=group.variant_schema,
        )
    
    async def _update_parent_product(
        self,
        product_id: UUID,
        variant_schema: list[str],
    ) -> None:
        """
        T120: Update parent product with variant information.
        
        Sets has_variants=true and variant_schema JSONB column.
        
        Args:
            product_id: Product to update
            variant_schema: List of attribute keys (e.g., ["voltage", "capacity"])
        """
        import json
        
        query = text("""
            UPDATE products
            SET 
                has_variants = true,
                variant_schema = :variant_schema::jsonb,
                updated_at = NOW()
            WHERE id = :product_id
        """)
        
        await self._session.execute(
            query,
            {
                "product_id": str(product_id),
                "variant_schema": json.dumps(variant_schema),
            },
        )
    
    async def _create_product_variant(
        self,
        parent_product_id: UUID,
        variant_key: str,
        variant_attributes: dict,
        display_order: int,
        linked_product_id: UUID,
    ) -> UUID:
        """
        T119: Create a product_variants record.
        
        Links a variant to its parent product with attributes.
        
        Args:
            parent_product_id: The parent product (has_variants=true)
            variant_key: Variant identifier (e.g., "48V/20Ah")
            variant_attributes: Structured attributes dict
            display_order: Order for display (0-indexed)
            linked_product_id: The product this variant represents
        
        Returns:
            UUID of the created variant record
        """
        import json
        from uuid import uuid4
        
        variant_id = uuid4()
        
        query = text("""
            INSERT INTO product_variants (
                id,
                product_id,
                variant_key,
                variant_attributes,
                display_order,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :product_id,
                :variant_key,
                :variant_attributes::jsonb,
                :display_order,
                NOW(),
                NOW()
            )
            ON CONFLICT (product_id, variant_key) DO UPDATE
            SET 
                variant_attributes = EXCLUDED.variant_attributes,
                display_order = EXCLUDED.display_order,
                updated_at = NOW()
            RETURNING id
        """)
        
        result = await self._session.execute(
            query,
            {
                "id": str(variant_id),
                "product_id": str(parent_product_id),
                "variant_key": variant_key,
                "variant_attributes": json.dumps(variant_attributes),
                "display_order": display_order,
            },
        )
        
        row = result.fetchone()
        return UUID(str(row[0])) if row else variant_id
    
    async def link_supplier_item_to_variant(
        self,
        supplier_item_id: UUID,
        variant_id: UUID,
    ) -> None:
        """
        Link a supplier_item to its variant record.
        
        Called after variant detection to connect source items
        with their variant records.
        
        Args:
            supplier_item_id: SupplierItem to link
            variant_id: ProductVariant to link to
        """
        query = text("""
            UPDATE supplier_items
            SET 
                variant_id = :variant_id,
                updated_at = NOW()
            WHERE id = :supplier_item_id
        """)
        
        await self._session.execute(
            query,
            {
                "supplier_item_id": str(supplier_item_id),
                "variant_id": str(variant_id),
            },
        )


# Convenience function for direct usage
async def run_variant_detection(
    session: AsyncSession,
    batch_id: str,
    created_product_ids: list[UUID],
    settings: Settings | None = None,
) -> VariantDetectionStats:
    """
    Convenience function to run variant detection for a batch.
    
    Args:
        session: Database session
        batch_id: Batch/job identifier
        created_product_ids: List of newly created product IDs
        settings: Optional settings override
    
    Returns:
        VariantDetectionStats with results
    """
    orchestrator = IngestionOrchestrator(session, settings)
    return await orchestrator.on_batch_complete(batch_id, created_product_ids)
