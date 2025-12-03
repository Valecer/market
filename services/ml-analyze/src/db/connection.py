"""
Database Connection Pool Management
====================================

Async connection pool management using SQLAlchemy AsyncIO with asyncpg.
Provides session management, health checks, and pgvector type registration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.config.settings import Settings, get_settings
from src.db.models import Base
from src.utils.errors import DatabaseError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Manages async database connections with connection pooling.

    Features:
        - AsyncIO connection pool with asyncpg
        - pgvector type registration for vector operations
        - Health check functionality
        - Session lifecycle management
        - Automatic connection pool cleanup
    """

    _instance: "DatabaseManager | None" = None
    _engine: AsyncEngine | None = None
    _session_factory: async_sessionmaker[AsyncSession] | None = None

    def __new__(cls) -> "DatabaseManager":
        """Singleton pattern to ensure single database manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls, settings: Settings | None = None) -> "DatabaseManager":
        """
        Initialize the database connection pool.

        Args:
            settings: Application settings (uses default if not provided)

        Returns:
            DatabaseManager instance

        Raises:
            DatabaseError: If connection initialization fails
        """
        instance = cls()

        if instance._engine is not None:
            logger.debug("Database already initialized, reusing connection pool")
            return instance

        settings = settings or get_settings()

        try:
            logger.info(
                "Initializing database connection pool",
                pool_min=settings.db_pool_min,
                pool_max=settings.db_pool_max,
            )

            # Create async engine with connection pooling
            # Note: pgvector types are handled via CAST in SQL queries, no need
            # for type registration on the Python side
            instance._engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_size=settings.db_pool_min,
                max_overflow=settings.db_pool_max - settings.db_pool_min,
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=True,  # Verify connection health before use
                poolclass=AsyncAdaptedQueuePool,
                connect_args={
                    "server_settings": {"jit": "off"},  # Disable JIT for pgvector
                },
            )

            # Create session factory
            instance._session_factory = async_sessionmaker(
                instance._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            logger.info("Database connection pool initialized successfully")
            return instance

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise DatabaseError(
                message="Database initialization failed",
                details={"error": str(e)},
            ) from e

    @classmethod
    async def close(cls) -> None:
        """
        Close the database connection pool.

        Should be called during application shutdown.
        """
        instance = cls._instance

        if instance is None or instance._engine is None:
            logger.debug("Database not initialized, nothing to close")
            return

        try:
            logger.info("Closing database connection pool")
            await instance._engine.dispose()
            instance._engine = None
            instance._session_factory = None
            cls._instance = None
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error("Error closing database connection pool", error=str(e))
            raise DatabaseError(
                message="Failed to close database connection",
                details={"error": str(e)},
            ) from e

    @classmethod
    def get_engine(cls) -> AsyncEngine:
        """
        Get the async engine instance.

        Returns:
            AsyncEngine instance

        Raises:
            DatabaseError: If database is not initialized
        """
        instance = cls._instance

        if instance is None or instance._engine is None:
            raise DatabaseError(
                message="Database not initialized",
                details={"hint": "Call DatabaseManager.initialize() first"},
            )

        return instance._engine

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session.

        Yields:
            AsyncSession instance with automatic cleanup

        Raises:
            DatabaseError: If database is not initialized

        Usage:
            async with DatabaseManager.get_session() as session:
                result = await session.execute(...)
        """
        instance = cls._instance

        if instance is None or instance._session_factory is None:
            raise DatabaseError(
                message="Database not initialized",
                details={"hint": "Call DatabaseManager.initialize() first"},
            )

        async with instance._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Database session error, rolled back", error=str(e))
                raise

    @classmethod
    async def health_check(cls) -> dict:
        """
        Check database connection health.

        Returns:
            Health check result dict

        Usage:
            status = await DatabaseManager.health_check()
            # {"status": "healthy", "latency_ms": 5.2}
        """
        import time

        instance = cls._instance

        if instance is None or instance._engine is None:
            return {"status": "not_initialized", "error": "Database not initialized"}

        start = time.perf_counter()

        try:
            async with instance._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            latency = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Convenience functions for direct import
async def init_database(settings: Settings | None = None) -> DatabaseManager:
    """Initialize database connection pool."""
    return await DatabaseManager.initialize(settings)


async def close_database() -> None:
    """Close database connection pool."""
    await DatabaseManager.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with DatabaseManager.get_session() as session:
        yield session


async def health_check() -> dict:
    """Check database health."""
    return await DatabaseManager.health_check()

