"""
Supplier Items Repository
==========================

Data access layer for the supplier_items table.
Provides CRUD operations for supplier items created by ml-analyze.

Follows Repository Pattern: Abstracts database operations.
"""

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
        name: str
        price: Decimal
        sku: str | None
        characteristics: JSONB
        match_status: str ('pending_match', 'matched', 'review', 'new_product')
        source_type: str ('ml_analyzed', 'parsed', etc.)
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
            source_type: Source identifier (default: 'ml_analyzed')

        Returns:
            Created item's UUID
        """
        query = text("""
            INSERT INTO supplier_items (
                supplier_id, name, price, sku, characteristics,
                match_status, source_type, created_at, updated_at
            ) VALUES (
                :supplier_id, :name, :price, :sku, :characteristics::jsonb,
                'pending_match', :source_type, NOW(), NOW()
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

        import json

        result = await self._session.execute(
            query,
            {
                "supplier_id": str(supplier_id),
                "name": row.name,
                "price": float(row.price) if row.price else None,
                "sku": row.sku,
                "characteristics": json.dumps(characteristics),
                "source_type": source_type,
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
        Create multiple supplier items in a batch.

        Uses PostgreSQL's multi-row INSERT for efficiency.

        Args:
            supplier_id: Reference to suppliers table
            rows: List of normalized rows
            source_type: Source identifier

        Returns:
            List of created item UUIDs
        """
        if not rows:
            return []

        import json

        values = []
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

            values.append({
                "supplier_id": str(supplier_id),
                "name": row.name,
                "price": float(row.price) if row.price else None,
                "sku": row.sku,
                "characteristics": json.dumps(characteristics),
                "source_type": source_type,
            })

        # Build multi-row INSERT
        query = text("""
            INSERT INTO supplier_items (
                supplier_id, name, price, sku, characteristics,
                match_status, source_type, created_at, updated_at
            )
            SELECT
                (v->>'supplier_id')::uuid,
                v->>'name',
                (v->>'price')::numeric,
                v->>'sku',
                (v->>'characteristics')::jsonb,
                'pending_match',
                v->>'source_type',
                NOW(),
                NOW()
            FROM jsonb_array_elements(CAST(:values AS jsonb)) AS v
            RETURNING id
        """)

        result = await self._session.execute(query, {"values": json.dumps(values)})
        ids = [row[0] for row in result.fetchall()]

        logger.info("Batch created", count=len(ids), supplier_id=str(supplier_id))
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
            SELECT id, supplier_id, product_id, name, price, sku,
                   characteristics, match_status, source_type,
                   created_at, updated_at
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
        Get items pending matching.

        Args:
            supplier_id: Optional filter by supplier
            limit: Maximum items to return

        Returns:
            List of item dicts
        """
        if supplier_id:
            query = text("""
                SELECT id, supplier_id, name, price, sku, characteristics
                FROM supplier_items
                WHERE match_status = 'pending_match'
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
                SELECT id, supplier_id, name, price, sku, characteristics
                FROM supplier_items
                WHERE match_status = 'pending_match'
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
            SELECT si.id, si.supplier_id, si.name, si.price, si.sku, si.characteristics
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

