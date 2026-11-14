"""
Auto-Creation Service
=====================

Automatically creates products for low-confidence matches (<90%).
Uses ML-cleaned names from extraction phase.

Phase 11: Pipeline Stabilization - US2 Auto-Creation + Duplicate Detection

Tasks: T048-T053, T121-T123 (variant detection integration)
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, insert, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.schemas.extraction import ExtractedProduct
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.services.ingestion_orchestrator import IngestionOrchestrator, VariantDetectionStats

logger = get_logger(__name__)


@dataclass
class AutoCreationStats:
    """Statistics from auto-creation operations."""
    
    products_created: int = 0
    supplier_items_linked: int = 0
    errors: int = 0
    # T123: Variant detection metrics
    variant_groups_created: int = 0
    products_grouped: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "products_created": self.products_created,
            "supplier_items_linked": self.supplier_items_linked,
            "errors": self.errors,
            "variant_groups_created": self.variant_groups_created,
            "products_grouped": self.products_grouped,
        }


class AutoCreationService:
    """
    Service for automatically creating products from low-confidence matches.
    
    When the matching service cannot find a high-confidence match (≥90%),
    this service creates a new Product using the ML-cleaned extraction data.
    
    Features:
    - Auto-generates internal_sku with format: AUTO-{uuid4().hex[:8].upper()}
    - Sets product status='active' for immediate catalog visibility
    - Links supplier_item with match_status='auto_created'
    - Audit logging for all auto-creation events
    - T121-T123: Automatic variant detection after batch creation
    
    Usage:
        async with get_session() as session:
            service = AutoCreationService(session)
            product = await service.create_product_from_extraction(
                extraction=ExtractedProduct(...),
                supplier_item_id=supplier_item_uuid,
            )
    """
    
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize AutoCreationService.
        
        Args:
            session: SQLAlchemy async session
            settings: Application settings (optional)
        """
        self._session = session
        self._settings = settings or get_settings()
        self._stats = AutoCreationStats()
        self._created_product_ids: list[UUID] = []  # Track for variant detection
    
    def get_stats(self) -> AutoCreationStats:
        """Get current auto-creation statistics."""
        return self._stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = AutoCreationStats()
        self._created_product_ids = []
    
    def get_created_product_ids(self) -> list[UUID]:
        """Get list of product IDs created in this session."""
        return self._created_product_ids.copy()
    
    @staticmethod
    def generate_internal_sku() -> str:
        """
        Generate internal SKU for auto-created products.
        
        Format: AUTO-{uuid4().hex[:8].upper()}
        Example: AUTO-A3F2B91C
        
        Returns:
            Unique internal SKU string
        """
        return f"AUTO-{uuid4().hex[:8].upper()}"
    
    async def create_product_from_extraction(
        self,
        extraction: ExtractedProduct,
        supplier_item_id: UUID,
        category_id: Optional[UUID] = None,
    ) -> dict:
        """
        Create a new Product from ML extraction data.
        
        This method:
        1. Creates a new Product with ML-cleaned name
        2. Generates a unique internal_sku (AUTO-{hex})
        3. Sets status='active' for immediate visibility
        4. Links the supplier_item with match_status='auto_created'
        5. Logs the auto-creation event
        
        Args:
            extraction: ExtractedProduct with cleaned data from ML
            supplier_item_id: ID of the supplier_item to link
            category_id: Optional category ID (from extraction/normalization)
        
        Returns:
            Dictionary with created product data
        
        Raises:
            Exception: On database errors (logged and re-raised)
        """
        product_id = uuid4()
        internal_sku = self.generate_internal_sku()
        
        logger.info(
            "auto_creation.creating_product",
            product_id=str(product_id),
            internal_sku=internal_sku,
            supplier_item_id=str(supplier_item_id),
            cleaned_name=extraction.name[:100],
            category_id=str(category_id) if category_id else None,
        )
        
        try:
            # T049-T051: Insert new product
            from sqlalchemy import text
            
            insert_product_sql = text("""
                INSERT INTO products (
                    id, internal_sku, name, category_id, status, 
                    has_variants, created_at, updated_at
                )
                VALUES (
                    :id, :internal_sku, :name, :category_id, 'active',
                    false, NOW(), NOW()
                )
                RETURNING id, internal_sku, name, category_id, status, created_at
            """)
            
            result = await self._session.execute(
                insert_product_sql,
                {
                    "id": str(product_id),
                    "internal_sku": internal_sku,
                    "name": extraction.name,
                    "category_id": str(category_id) if category_id else None,
                },
            )
            product_row = result.fetchone()
            
            # T052: Link supplier_item to new product with match_status='auto_created'
            update_supplier_item_sql = text("""
                UPDATE supplier_items
                SET 
                    product_id = :product_id,
                    match_status = 'auto_created',
                    match_score = NULL,
                    updated_at = NOW()
                WHERE id = :supplier_item_id
            """)
            
            await self._session.execute(
                update_supplier_item_sql,
                {
                    "product_id": str(product_id),
                    "supplier_item_id": str(supplier_item_id),
                },
            )
            
            # Commit the transaction
            await self._session.commit()
            
            # T053: Audit logging
            self._log_auto_creation_event(
                product_id=product_id,
                supplier_item_id=supplier_item_id,
                internal_sku=internal_sku,
                ml_cleaned_name=extraction.name,
                category_id=category_id,
            )
            
            # Update stats
            self._stats.products_created += 1
            self._stats.supplier_items_linked += 1
            
            # T122: Track for variant detection
            self._created_product_ids.append(product_id)
            
            logger.info(
                "auto_creation.product_created",
                product_id=str(product_id),
                internal_sku=internal_sku,
                supplier_item_id=str(supplier_item_id),
            )
            
            return {
                "id": product_id,
                "internal_sku": internal_sku,
                "name": extraction.name,
                "category_id": category_id,
                "status": "active",
                "created_at": product_row.created_at if product_row else datetime.utcnow(),
            }
            
        except Exception as e:
            await self._session.rollback()
            self._stats.errors += 1
            
            logger.error(
                "auto_creation.failed",
                product_id=str(product_id),
                supplier_item_id=str(supplier_item_id),
                error=str(e),
            )
            raise
    
    async def create_products_batch(
        self,
        extractions: list[tuple[ExtractedProduct, UUID, Optional[UUID]]],
        batch_id: str | None = None,
        run_variant_detection: bool = True,
    ) -> list[dict]:
        """
        Create multiple products in a batch operation.
        
        More efficient than calling create_product_from_extraction
        repeatedly for large batches.
        
        T121-T123: Optionally runs variant detection after batch creation.
        
        Args:
            extractions: List of (ExtractedProduct, supplier_item_id, category_id) tuples
            batch_id: Optional batch/job identifier for variant detection
            run_variant_detection: Whether to run variant detection after creation (default True)
        
        Returns:
            List of created product dictionaries
        """
        created_products = []
        
        for extraction, supplier_item_id, category_id in extractions:
            try:
                product = await self.create_product_from_extraction(
                    extraction=extraction,
                    supplier_item_id=supplier_item_id,
                    category_id=category_id,
                )
                created_products.append(product)
            except Exception as e:
                logger.error(
                    "auto_creation.batch_item_failed",
                    supplier_item_id=str(supplier_item_id),
                    error=str(e),
                )
                # Continue with next item (per-item error isolation)
                continue
        
        logger.info(
            "auto_creation.batch_complete",
            total=len(extractions),
            created=len(created_products),
            failed=len(extractions) - len(created_products),
        )
        
        # T121: Call IngestionOrchestrator.on_batch_complete after auto-creation
        if run_variant_detection and created_products and self._settings.variant_detection_enabled:
            await self._run_variant_detection(
                batch_id=batch_id or f"batch-{datetime.utcnow().isoformat()}",
                created_products=created_products,
            )
        
        return created_products
    
    async def _run_variant_detection(
        self,
        batch_id: str,
        created_products: list[dict],
    ) -> None:
        """
        T121-T123: Run variant detection for newly created products.
        
        Calls IngestionOrchestrator.on_batch_complete and updates stats.
        
        Args:
            batch_id: Batch/job identifier
            created_products: List of created product dictionaries
        """
        # Import here to avoid circular imports
        from src.services.ingestion_orchestrator import IngestionOrchestrator
        
        # T122: Pass list of auto-created product IDs to on_batch_complete
        product_ids = [p["id"] for p in created_products]
        
        logger.info(
            "auto_creation.starting_variant_detection",
            batch_id=batch_id,
            product_count=len(product_ids),
        )
        
        try:
            orchestrator = IngestionOrchestrator(self._session, self._settings)
            variant_stats = await orchestrator.on_batch_complete(
                batch_id=batch_id,
                created_product_ids=product_ids,
            )
            
            # T123: Add variant detection metrics to stats
            self._stats.variant_groups_created = variant_stats.variant_groups_created
            self._stats.products_grouped = variant_stats.products_grouped
            
            logger.info(
                "auto_creation.variant_detection_complete",
                batch_id=batch_id,
                variant_stats=variant_stats.to_dict(),
            )
        except Exception as e:
            logger.error(
                "auto_creation.variant_detection_failed",
                batch_id=batch_id,
                error=str(e),
            )
            # Don't raise - variant detection failure shouldn't fail the batch
    
    def _log_auto_creation_event(
        self,
        product_id: UUID,
        supplier_item_id: UUID,
        internal_sku: str,
        ml_cleaned_name: str,
        category_id: Optional[UUID],
    ) -> None:
        """
        Log auto-creation event for audit trail.
        
        T053: Audit logging includes all relevant context.
        
        Args:
            product_id: Created product ID
            supplier_item_id: Linked supplier item ID
            internal_sku: Generated SKU
            ml_cleaned_name: ML-cleaned product name
            category_id: Assigned category ID
        """
        logger.info(
            "auto_creation.audit",
            event_type="product_auto_created",
            product_id=str(product_id),
            supplier_item_id=str(supplier_item_id),
            internal_sku=internal_sku,
            ml_cleaned_name=ml_cleaned_name[:200],
            category_id=str(category_id) if category_id else None,
            timestamp=datetime.utcnow().isoformat(),
        )


# Convenience function for one-off usage
async def auto_create_product(
    session: AsyncSession,
    extraction: ExtractedProduct,
    supplier_item_id: UUID,
    category_id: Optional[UUID] = None,
) -> dict:
    """
    Convenience function to auto-create a single product.
    
    Args:
        session: Database session
        extraction: ExtractedProduct from ML
        supplier_item_id: Supplier item to link
        category_id: Optional category ID
    
    Returns:
        Created product dictionary
    """
    service = AutoCreationService(session)
    return await service.create_product_from_extraction(
        extraction=extraction,
        supplier_item_id=supplier_item_id,
        category_id=category_id,
    )
