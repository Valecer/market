"""
Supplier Items Repository
==========================

Data access layer for the supplier_items table.
Provides CRUD operations for supplier items created by ml-analyze.

Follows Repository Pattern: Abstracts database operations.
"""

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.domain import NormalizedRow
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_deterministic_sku(
    supplier_id: UUID, 
    name: str, 
    price: float | None = None,
) -> str:
    """
    Generate a deterministic SKU from supplier ID, product name, and price.
    
    Uses MD5 hash to ensure:
    - Same product (name + price) always gets the same SKU
    - SKU is unique per supplier
    - SKU is stable across Python process restarts
    - Products with same name but different prices get different SKUs
      (aligns with DeduplicationService behavior)
    
    Args:
        supplier_id: Supplier UUID
        name: Product name
        price: Product price (used to distinguish variants with same name)
    
    Returns:
        Deterministic SKU in format: ML-{supplier_short}-{hash}
    """
    # Normalize name: lowercase, strip, collapse whitespace
    normalized_name = " ".join(name.strip().lower().split())
    
    # Include price in hash to distinguish variants with same name but different prices
    # Round to 2 decimal places for consistency
    price_str = f"{price:.2f}" if price is not None else "0.00"
    
    # Create stable hash from supplier_id + normalized_name + price
    hash_input = f"{supplier_id}:{normalized_name}:{price_str}".encode("utf-8")
    content_hash = hashlib.md5(hash_input, usedforsecurity=False).hexdigest()[:12]
    
    # Use first 8 chars of supplier_id for readability
    supplier_short = str(supplier_id)[:8]
    
    return f"ML-{supplier_short}-{content_hash}"


class SupplierItemsRepository:
    """
    Repository for supplier_items table operations.

    The supplier_items table is owned by the python-ingestion service,
    but ml-analyze needs to:
    - Insert newly parsed items
    - Update product_id when matches are found
    - Query items for embedding generation

    Table Schema (from existing migrations):
        id: UUID (PK)
        supplier_id: UUID (FK → suppliers)
        product_id: UUID | None (FK → products)
        supplier_sku: str (required)
        name: str
        current_price: Decimal
        characteristics: JSONB
        match_status: enum ('unmatched', 'matched', 'review', 'auto_matched')
        last_ingested_at: datetime
        created_at: datetime
        updated_at: datetime
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with async session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def create(
        self,
        supplier_id: UUID,
        row: NormalizedRow,
        source_type: str = "ml_analyzed",
    ) -> UUID:
        """
        Create a new supplier item from normalized row.

        Args:
            supplier_id: Reference to suppliers table
            row: Normalized row data
            source_type: Source identifier (stored in characteristics._source_type)

        Returns:
            Created item's UUID
        """
        query = text("""
            INSERT INTO supplier_items (
                supplier_id, name, current_price, supplier_sku, characteristics,
                match_status, last_ingested_at, created_at, updated_at
            ) VALUES (
                :supplier_id, :name, :price, :sku, :characteristics::jsonb,
                'unmatched', NOW(), NOW(), NOW()
            )
            RETURNING id
        """)

        # Build characteristics with raw_data if available
        characteristics = row.characteristics.copy() if row.characteristics else {}
        if row.category:
            characteristics["_category"] = row.category
        if row.brand:
            characteristics["_brand"] = row.brand
        if row.unit:
            characteristics["_unit"] = row.unit
        if row.description:
            characteristics["_description"] = row.description
        # Store source_type in characteristics since column doesn't exist
        characteristics["_source_type"] = source_type

        import json

        # Get price for SKU generation
        price = float(row.price) if row.price else 0.0

        # Generate deterministic SKU if not provided (required field)
        # Uses normalized name + price hash for stable UPSERT behavior across syncs
        # Price is included to distinguish variants with same name but different prices
        sku = row.sku or generate_deterministic_sku(supplier_id, row.name, price)

        result = await self._session.execute(
            query,
            {
                "supplier_id": str(supplier_id),
                "name": row.name,
                "price": price,
                "sku": sku,
                "characteristics": json.dumps(characteristics),
            },
        )

        item_id = result.scalar_one()
        logger.debug("Supplier item created", item_id=str(item_id), name=row.name[:50])
        return item_id

    async def create_batch(
        self,
        supplier_id: UUID,
        rows: list[NormalizedRow],
        source_type: str = "ml_analyzed",
    ) -> list[UUID]:
        """
        Create or update multiple supplier items in a batch (UPSERT).

        Uses PostgreSQL's INSERT...ON CONFLICT DO UPDATE for efficiency.
        On re-sync, existing items are updated while preserving:
        - created_at (original creation timestamp)
        - match_status (user curation state)
        - product_id (matched product reference)

        Note: Deduplicates by SKU before insert to prevent PostgreSQL's
        "ON CONFLICT DO UPDATE command cannot affect row a second time" error.
        Last occurrence wins (fresher data in batch processing).

        Args:
            supplier_id: Reference to suppliers table
            rows: List of normalized rows
            source_type: Source identifier (stored in characteristics._source_type)

        Returns:
            List of created/updated item UUIDs
        """
        if not rows:
            return []

        import json

        # Build values with SKU-based deduplication
        # Use dict keyed by SKU to keep last occurrence (fresher data wins)
        values_by_sku: dict[str, dict] = {}
        duplicates_skipped = 0
        
        for row in rows:
            characteristics = row.characteristics.copy() if row.characteristics else {}
            if row.category:
                characteristics["_category"] = row.category
            if row.brand:
                characteristics["_brand"] = row.brand
            if row.unit:
                characteristics["_unit"] = row.unit
            if row.description:
                characteristics["_description"] = row.description
            # Store source_type in characteristics since column doesn't exist
            characteristics["_source_type"] = source_type

            # Get price for SKU generation
            price = float(row.price) if row.price else 0.0

            # Generate deterministic SKU if not provided (required field)
            # Uses normalized name + price hash for stable UPSERT behavior across syncs
            # Price is included to distinguish variants with same name but different prices
            sku = row.sku or generate_deterministic_sku(supplier_id, row.name, price)

            # Track if we're replacing an existing SKU
            if sku in values_by_sku:
                duplicates_skipped += 1
                logger.debug(
                    "Duplicate SKU in batch, keeping last occurrence",
                    sku=sku,
                    name=row.name[:50],
                )
            
            values_by_sku[sku] = {
                "supplier_id": str(supplier_id),
                "name": row.name,
                "price": price,
                "sku": sku,
                "characteristics": json.dumps(characteristics),
            }
        
        values = list(values_by_sku.values())
        
        if duplicates_skipped > 0:
            logger.info(
                "Deduplicated batch by SKU before insert",
                original_count=len(rows),
                unique_count=len(values),
                duplicates_skipped=duplicates_skipped,
                supplier_id=str(supplier_id),
            )

        # Build multi-row UPSERT (INSERT...ON CONFLICT DO UPDATE)
        # On conflict (same supplier_id + supplier_sku), update the item
        # but preserve: created_at, match_status, product_id (user curation)
        query = text("""
            INSERT INTO supplier_items (
                supplier_id, name, current_price, supplier_sku, characteristics,
                match_status, last_ingested_at, created_at, updated_at
            )
            SELECT
                (v->>'supplier_id')::uuid,
                v->>'name',
                COALESCE((v->>'price')::numeric, 0),
                v->>'sku',
                (v->>'characteristics')::jsonb,
                'unmatched',
                NOW(),
                NOW(),
                NOW()
            FROM jsonb_array_elements(CAST(:values AS jsonb)) AS v
            ON CONFLICT (supplier_id, supplier_sku) DO UPDATE SET
                name = EXCLUDED.name,
                current_price = EXCLUDED.current_price,
                characteristics = EXCLUDED.characteristics,
                last_ingested_at = NOW(),
                updated_at = NOW()
            RETURNING id
        """)

        result = await self._session.execute(query, {"values": json.dumps(values)})
        ids = [row[0] for row in result.fetchall()]

        logger.info("Batch upserted", count=len(ids), supplier_id=str(supplier_id))
        return ids

    async def update_product_id(
        self,
        item_id: UUID,
        product_id: UUID,
        match_status: str = "matched",
    ) -> bool:
        """
        Update supplier item with matched product.

        Called when LLM matching finds a high-confidence match.

        Args:
            item_id: Supplier item to update
            product_id: Matched product
            match_status: New status ('matched' or 'auto_matched')

        Returns:
            True if update succeeded
        """
        query = text("""
            UPDATE supplier_items
            SET product_id = :product_id,
                match_status = :match_status,
                updated_at = NOW()
            WHERE id = :item_id
        """)

        result = await self._session.execute(
            query,
            {
                "item_id": str(item_id),
                "product_id": str(product_id),
                "match_status": match_status,
            },
        )

        updated = result.rowcount > 0
        if updated:
            logger.debug(
                "Product ID updated",
                item_id=str(item_id),
                product_id=str(product_id),
            )
        return updated

    async def get_by_id(self, item_id: UUID) -> dict[str, Any] | None:
        """
        Get supplier item by ID.

        Args:
            item_id: Item UUID

        Returns:
            Item dict or None if not found
        """
        query = text("""
            SELECT id, supplier_id, product_id, name, current_price as price,
                   supplier_sku as sku, characteristics, match_status,
                   last_ingested_at, created_at, updated_at
            FROM supplier_items
            WHERE id = :item_id
        """)

        result = await self._session.execute(query, {"item_id": str(item_id)})
        row = result.mappings().fetchone()

        return dict(row) if row else None

    async def get_pending_match(
        self,
        supplier_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get items pending matching (unmatched status).

        Args:
            supplier_id: Optional filter by supplier
            limit: Maximum items to return

        Returns:
            List of item dicts
        """
        if supplier_id:
            query = text("""
                SELECT id, supplier_id, name, current_price as price,
                       supplier_sku as sku, characteristics
                FROM supplier_items
                WHERE match_status = 'unmatched'
                  AND supplier_id = :supplier_id
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await self._session.execute(
                query,
                {"supplier_id": str(supplier_id), "limit": limit},
            )
        else:
            query = text("""
                SELECT id, supplier_id, name, current_price as price,
                       supplier_sku as sku, characteristics
                FROM supplier_items
                WHERE match_status = 'unmatched'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await self._session.execute(query, {"limit": limit})

        return [dict(row) for row in result.mappings().fetchall()]

    async def get_without_embeddings(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get items that don't have embeddings yet.

        Args:
            limit: Maximum items to return

        Returns:
            List of item dicts
        """
        query = text("""
            SELECT si.id, si.supplier_id, si.name, si.current_price as price,
                   si.supplier_sku as sku, si.characteristics
            FROM supplier_items si
            LEFT JOIN product_embeddings pe ON si.id = pe.supplier_item_id
            WHERE pe.id IS NULL
            ORDER BY si.created_at DESC
            LIMIT :limit
        """)

        result = await self._session.execute(query, {"limit": limit})
        return [dict(row) for row in result.mappings().fetchall()]

    async def count_by_status(self, supplier_id: UUID | None = None) -> dict[str, int]:
        """
        Count items by match status.

        Args:
            supplier_id: Optional filter by supplier

        Returns:
            Dict mapping status to count
        """
        if supplier_id:
            query = text("""
                SELECT match_status, COUNT(*) as count
                FROM supplier_items
                WHERE supplier_id = :supplier_id
                GROUP BY match_status
            """)
            result = await self._session.execute(query, {"supplier_id": str(supplier_id)})
        else:
            query = text("""
                SELECT match_status, COUNT(*) as count
                FROM supplier_items
                GROUP BY match_status
            """)
            result = await self._session.execute(query)

        return {row["match_status"]: row["count"] for row in result.mappings().fetchall()}

