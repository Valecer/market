"""Idempotency service for hash-based re-ingestion.

Computes deterministic hashes for raw supplier rows, checks cache,
and updates price-only fields on cache hits.

Hash Normalization Logic (T142):
================================
Row data is normalized before hashing to ensure consistency:

1. **Key normalization**: All keys are lowercased and sorted alphabetically
2. **Value normalization**:
   - String values are trimmed of leading/trailing whitespace
   - Null/None/NaN/"null"/"none"/"" values are normalized to empty string ""
   - Other types (numbers, bools) are preserved as-is
3. **Canonical JSON**: Data is serialized with sorted keys, no ASCII escaping,
   and compact separators (",", ":") for deterministic output
4. **Hash input**: Final string is "{supplier_id}|{canonical_json}"

This ensures that:
- Column reordering doesn't change the hash
- Whitespace variations don't cause false misses
- Null representation differences don't affect deduplication

Performance Optimizations (Phase 7 - T135):
==========================================
- Batch hash lookups: Query up to 1000 hashes in a single DB call
- In-memory hash computation: No DB round-trip for hash generation
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.config import settings
from src.db.models import SupplierItem

logger = structlog.get_logger(__name__)

# Performance constants (T135)
BATCH_LOOKUP_SIZE = 1000  # Maximum hashes per batch query


@dataclass
class CacheLookupResult:
    """Result of a cache lookup."""

    item: Optional[SupplierItem]
    is_collision: bool = False


@dataclass
class BatchLookupResult:
    """Result of batch hash lookup (T135).
    
    Tracks which hashes were found (hits) vs. not found (misses),
    enabling efficient bulk processing during re-ingestion.
    """

    hits: Dict[str, SupplierItem] = field(default_factory=dict)  # hash -> item
    misses: List[str] = field(default_factory=list)  # hashes not found
    collisions: List[str] = field(default_factory=list)  # hashes with content mismatch

    @property
    def hit_count(self) -> int:
        """Number of cache hits."""
        return len(self.hits)

    @property
    def miss_count(self) -> int:
        """Number of cache misses."""
        return len(self.misses)

    @property
    def collision_count(self) -> int:
        """Number of hash collisions detected."""
        return len(self.collisions)


class IdempotencyService:
    """Hash-based idempotency operations for supplier rows."""

    def __init__(self, session: AsyncSession, log=None) -> None:
        self.session = session
        self.log = log or logger

    # ------------------------------------------------------------------ #
    # Hashing helpers
    # ------------------------------------------------------------------ #
    def _normalize_row_data(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize row data by trimming and sorting keys.

        - Keys lowercased and sorted
        - String values trimmed
        - Nullish values normalized to empty string
        """
        normalized: Dict[str, Any] = {}
        for key in sorted(row_data.keys(), key=lambda k: k.lower()):
            value = row_data[key]
            if value is None or str(value).strip().lower() in {"", "none", "null", "nan"}:
                normalized[key.lower()] = ""
                continue

            if isinstance(value, str):
                normalized[key.lower()] = value.strip()
            else:
                normalized[key.lower()] = value

        return normalized

    def _canonical_json(self, data: Dict[str, Any]) -> str:
        """Serialize normalized data to canonical JSON string."""
        return json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def compute_row_hash(self, supplier_id: str | UUID, row_data: Dict[str, Any]) -> str:
        """Compute MD5 hash of normalized row data plus supplier context."""
        normalized = self._normalize_row_data(row_data)
        content = f"{supplier_id}|{self._canonical_json(normalized)}"
        algorithm = settings.hash_algorithm.lower()

        if algorithm != "md5":
            self.log.warning("unsupported_hash_algorithm", algorithm=algorithm, fallback="md5")

        return hashlib.md5(content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ #
    # Cache lookup + collision handling
    # ------------------------------------------------------------------ #
    async def get_cached_item(
        self,
        source_row_hash: str,
        row_data: Optional[Dict[str, Any]] = None,
    ) -> CacheLookupResult:
        """Fetch cached supplier item by hash and detect collisions."""
        result = await self.session.execute(
            select(SupplierItem).where(SupplierItem.source_row_hash == source_row_hash)
        )
        item = result.scalar_one_or_none()
        if not item:
            return CacheLookupResult(item=None, is_collision=False)

        if row_data:
            normalized_input = self._canonical_json(self._normalize_row_data(row_data))
            stored_payload = None

            if isinstance(item.characteristics, dict):
                stored_payload = item.characteristics.get("_source_row") or item.characteristics

            if isinstance(stored_payload, dict):
                stored_normalized = self._canonical_json(self._normalize_row_data(stored_payload))
                if stored_normalized != normalized_input:
                    self.log.warning(
                        "hash_collision_detected",
                        supplier_item_id=str(item.id),
                        source_row_hash=source_row_hash,
                    )
                    return CacheLookupResult(item=item, is_collision=True)

        return CacheLookupResult(item=item, is_collision=False)

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    async def update_price_only(
        self,
        item_id: UUID,
        prices: Dict[str, Optional[Decimal]],
        commit: bool = True,
    ) -> None:
        """Update only price-related fields for cached rows."""
        await self.session.execute(
            update(SupplierItem)
            .where(SupplierItem.id == item_id)
            .values(
                current_price=prices.get("current_price"),
                price_opt=prices.get("price_opt"),
                price_rrc=prices.get("price_rrc"),
                last_ingested_at=func.now(),
            )
        )

        if commit:
            await self.session.commit()

        self.log.info(
            "idempotency_price_update",
            supplier_item_id=str(item_id),
            fields_changed=[
                key
                for key, value in prices.items()
                if value is not None or key == "current_price"
            ],
        )

    # ------------------------------------------------------------------ #
    # T135: Batch operations for performance
    # ------------------------------------------------------------------ #
    async def batch_lookup_hashes(
        self,
        hashes: Sequence[str],
        row_data_by_hash: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> BatchLookupResult:
        """Batch lookup multiple hashes in a single query (T135).
        
        Performance optimization: Instead of N individual queries,
        performs ceil(N/1000) queries for N hashes.
        
        Args:
            hashes: Sequence of source_row_hash values to lookup
            row_data_by_hash: Optional mapping of hash -> original row data
                              for collision detection
        
        Returns:
            BatchLookupResult with hits, misses, and collisions
        """
        result = BatchLookupResult()
        
        if not hashes:
            return result
        
        # Process in batches of BATCH_LOOKUP_SIZE (default 1000)
        hash_list = list(hashes)
        for batch_start in range(0, len(hash_list), BATCH_LOOKUP_SIZE):
            batch_end = min(batch_start + BATCH_LOOKUP_SIZE, len(hash_list))
            batch_hashes = hash_list[batch_start:batch_end]
            
            # Query all items matching these hashes
            query_result = await self.session.execute(
                select(SupplierItem).where(
                    SupplierItem.source_row_hash.in_(batch_hashes)
                )
            )
            items = query_result.scalars().all()
            
            # Build lookup dict for this batch
            found_items: Dict[str, SupplierItem] = {
                item.source_row_hash: item
                for item in items
                if item.source_row_hash is not None
            }
            
            # Classify each hash in the batch
            for h in batch_hashes:
                if h in found_items:
                    item = found_items[h]
                    
                    # Check for collision if row_data provided
                    if row_data_by_hash and h in row_data_by_hash:
                        is_collision = self._detect_collision(
                            item, row_data_by_hash[h]
                        )
                        if is_collision:
                            result.collisions.append(h)
                            self.log.warning(
                                "hash_collision_batch",
                                source_row_hash=h,
                                supplier_item_id=str(item.id),
                            )
                            continue
                    
                    result.hits[h] = item
                else:
                    result.misses.append(h)
        
        self.log.info(
            "batch_lookup_complete",
            total_hashes=len(hashes),
            hits=result.hit_count,
            misses=result.miss_count,
            collisions=result.collision_count,
        )
        
        return result

    def _detect_collision(
        self,
        item: SupplierItem,
        original_row_data: Dict[str, Any],
    ) -> bool:
        """Detect hash collision by comparing normalized content.
        
        Args:
            item: Existing supplier item from DB
            original_row_data: Original row data that produced this hash
        
        Returns:
            True if collision detected (same hash, different content)
        """
        normalized_input = self._canonical_json(
            self._normalize_row_data(original_row_data)
        )
        
        stored_payload = None
        if isinstance(item.characteristics, dict):
            stored_payload = (
                item.characteristics.get("_source_row") or item.characteristics
            )
        
        if isinstance(stored_payload, dict):
            stored_normalized = self._canonical_json(
                self._normalize_row_data(stored_payload)
            )
            return stored_normalized != normalized_input
        
        return False

    async def batch_update_prices(
        self,
        updates: List[tuple[UUID, Dict[str, Optional[Decimal]]]],
        commit: bool = True,
    ) -> int:
        """Batch update prices for multiple cached rows (T135).
        
        More efficient than individual update_price_only calls
        for large re-ingestion batches.
        
        Args:
            updates: List of (item_id, prices_dict) tuples
            commit: Whether to commit after all updates
        
        Returns:
            Number of rows updated
        """
        if not updates:
            return 0
        
        updated_count = 0
        for item_id, prices in updates:
            await self.session.execute(
                update(SupplierItem)
                .where(SupplierItem.id == item_id)
                .values(
                    current_price=prices.get("current_price"),
                    price_opt=prices.get("price_opt"),
                    price_rrc=prices.get("price_rrc"),
                    last_ingested_at=func.now(),
                )
            )
            updated_count += 1
        
        if commit:
            await self.session.commit()
        
        self.log.info(
            "batch_price_update_complete",
            rows_updated=updated_count,
        )
        
        return updated_count

    def compute_hashes_batch(
        self,
        supplier_id: str | UUID,
        rows: Sequence[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute hashes for multiple rows (T135).
        
        Returns mapping of hash -> original row data for efficient
        collision detection during batch lookup.
        
        Args:
            supplier_id: Supplier context for hash computation
            rows: Sequence of row data dictionaries
        
        Returns:
            Dict mapping hash -> row_data
        """
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            h = self.compute_row_hash(supplier_id, row)
            result[h] = row
        return result

