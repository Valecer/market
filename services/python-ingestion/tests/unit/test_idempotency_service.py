"""Unit tests for IdempotencyService (Phase 3 US1)."""

import os
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict
from uuid import uuid4

import pytest

# Skip suite if aiosqlite is unavailable (async SQLite backend for SQLAlchemy)
try:
    import aiosqlite  # noqa: F401
except ImportError:
    pytest.skip("aiosqlite not installed; skipping async SQLite-backed tests", allow_module_level=True)
from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Set required environment variables before importing settings-backed modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_PASSWORD", "test_password")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("LOG_LEVEL", "INFO")

from src.db.base import Base
from src.db.models import Supplier, SupplierItem
from src.services.idempotency_service import IdempotencyService


def _prepare_sqlite_metadata() -> None:
    """Make PostgreSQL-specific types compatible with SQLite for tests."""
    for table in Base.metadata.tables.values():
        constraints_to_remove = [
            constraint
            for constraint in list(table.constraints)
            if isinstance(constraint, CheckConstraint)
        ]
        for constraint in constraints_to_remove:
            table.constraints.discard(constraint)

        for column in table.columns:
            if isinstance(column.type, postgresql.JSONB):
                column.type = JSON()
            elif hasattr(postgresql, "JSONB") and isinstance(column.type, postgresql.JSONB):  # safety
                column.type = JSON()
            elif isinstance(column.type, postgresql.ENUM):
                column.type = String(50)
                column.server_default = None


@pytest.fixture(scope="function")
async def async_session():
    """Provide an async SQLite session for unit tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    _prepare_sqlite_metadata()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as session:
            yield session
    finally:
        await engine.dispose()


async def _create_supplier(session: AsyncSession) -> Supplier:
    supplier = Supplier(name="Test Supplier", source_type="csv")
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


def _sample_row(extra: Dict[str, str] | None = None) -> Dict[str, str]:
    base = {"name": "Battery 48V", "price": "10.50", "brand": "Shtenli"}
    if extra:
        base.update(extra)
    return base


@pytest.mark.asyncio
async def test_compute_row_hash_deterministic(async_session: AsyncSession):
    service = IdempotencyService(async_session)
    row = _sample_row()

    hash1 = service.compute_row_hash("supplier-1", row)
    hash2 = service.compute_row_hash("supplier-1", row)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_compute_row_hash_column_order_invariant(async_session: AsyncSession):
    service = IdempotencyService(async_session)
    row_a = {"name": "Battery", "price": "12.00", "brand": "A"}
    row_b = {"brand": "A", "price": "12.00", "name": "Battery"}  # different order

    hash_a = service.compute_row_hash("supplier-1", row_a)
    hash_b = service.compute_row_hash("supplier-1", row_b)

    assert hash_a == hash_b


@pytest.mark.asyncio
async def test_get_cached_item_exists(async_session: AsyncSession):
    service = IdempotencyService(async_session)
    supplier = await _create_supplier(async_session)
    row = _sample_row()
    row_hash = service.compute_row_hash(supplier.id, row)

    item = SupplierItem(
        supplier_id=supplier.id,
        supplier_sku="SKU-001",
        name="Battery 48V",
        current_price=Decimal("10.50"),
        source_row_hash=row_hash,
        characteristics={"_source_row": row},
    )
    async_session.add(item)
    await async_session.commit()

    lookup = await service.get_cached_item(row_hash, row_data=row)
    assert lookup.item is not None
    assert lookup.item.id == item.id
    assert lookup.is_collision is False


@pytest.mark.asyncio
async def test_get_cached_item_not_found(async_session: AsyncSession):
    service = IdempotencyService(async_session)

    lookup = await service.get_cached_item("nonexistent-hash")
    assert lookup.item is None
    assert lookup.is_collision is False


@pytest.mark.asyncio
async def test_update_price_only(async_session: AsyncSession):
    service = IdempotencyService(async_session)
    supplier = await _create_supplier(async_session)
    row = _sample_row()
    row_hash = service.compute_row_hash(supplier.id, row)

    item = SupplierItem(
        supplier_id=supplier.id,
        supplier_sku="SKU-001",
        name="Battery 48V",
        current_price=Decimal("10.50"),
        source_row_hash=row_hash,
        characteristics={"_source_row": row},
    )
    async_session.add(item)
    await async_session.commit()
    await async_session.refresh(item)

    await service.update_price_only(
        item_id=item.id,
        prices={"current_price": Decimal("11.00"), "price_opt": Decimal("9.00"), "price_rrc": None},
    )

    await async_session.refresh(item)
    assert item.current_price == Decimal("11.00")
    assert item.name == "Battery 48V"
    assert item.price_opt == Decimal("9.00")
    assert item.price_rrc is None
    assert item.last_ingested_at is not None


@pytest.mark.asyncio
async def test_hash_collision_handling(async_session: AsyncSession):
    service = IdempotencyService(async_session)
    supplier = await _create_supplier(async_session)
    row_a = _sample_row({"price": "10.50"})
    row_b = _sample_row({"price": "11.00"})  # different content but will reuse same hash value manually

    # Force same hash by using hash of row_a
    forced_hash = service.compute_row_hash(supplier.id, row_a)

    item = SupplierItem(
        supplier_id=supplier.id,
        supplier_sku="SKU-001",
        name="Battery 48V",
        current_price=Decimal("10.50"),
        source_row_hash=forced_hash,
        characteristics={"_source_row": row_a},
    )
    async_session.add(item)
    await async_session.commit()

    lookup = await service.get_cached_item(forced_hash, row_data=row_b)
    assert lookup.item is not None
    assert lookup.is_collision is True

