"""Base SQLAlchemy configuration and mixins."""
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import func, DateTime
from datetime import datetime
from typing import Optional, AsyncGenerator
import uuid

from src.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models with async support."""
    pass


class UUIDMixin:
    """Mixin for UUID primary key."""
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Create async engine with configurable connection pooling (T138)
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_pre_ping=True,  # Verify connection health before use
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session (async generator)."""
    async with async_session_maker() as session:
        yield session

