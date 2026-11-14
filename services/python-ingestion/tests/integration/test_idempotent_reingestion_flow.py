"""Integration test for idempotent re-ingestion (T047)."""

import asyncio
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from src.db.base import async_session_maker
from src.db.models import Supplier, SupplierItem
from src.services.idempotency_service import IdempotencyService
from src.tasks.download_tasks import _preprocess_hash_cache  # type: ignore


@pytest.mark.asyncio
async def test_idempotent_reingestion_flow(tmp_path: Path):
    """E2E-ish check: hash hit updates price, hash miss remains for ML."""
    # Create supplier and existing item (simulates first ingestion)
    async with async_session_maker() as session:
        supplier = Supplier(name="Test Supplier", source_type="csv")
        session.add(supplier)
        await session.commit()
        await session.refresh(supplier)

        service = IdempotencyService(session)

        row_cached = {"name": "Battery 48V", "price": "10.50", "brand": "Shtenli"}
        row_cached_hash = service.compute_row_hash(supplier.id, row_cached)

        item = SupplierItem(
            supplier_id=supplier.id,
            supplier_sku="SKU-001",
            name=row_cached["name"],
            current_price=Decimal("10.50"),
            source_row_hash=row_cached_hash,
            characteristics={"_source_row": row_cached},
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)

    # Prepare re-ingestion file: one cached row with new price, one new row
    csv_content = "name,price,brand\nBattery 48V,12.00,Shtenli\nDrill 18V,45.00,Bosch\n"
    file_path = tmp_path / "reingest.csv"
    file_path.write_text(csv_content, encoding="utf-8")

    job_id = uuid4()

    stats = await _preprocess_hash_cache(
        file_path=file_path,
        supplier_id=supplier.id,
        job_id=job_id,
        redis=None,  # Metrics to Redis not required for this test
        log=None,
    )

    # Reload item to verify price-only update was applied
    async with async_session_maker() as session:
        refreshed = await session.get(SupplierItem, item.id)

    assert stats is not None
    assert stats.hash_hits == 1
    assert stats.hash_misses == 1
    assert stats.ml_extractions_saved == 1
    assert refreshed.current_price == Decimal("12.00")
    assert refreshed.name == "Battery 48V"
