"""Pytest fixtures for integration tests.

This conftest.py provides integration-specific fixtures:
- Database session with automatic cleanup
- Event loop for async tests
- Integration test environment variables
- Database migrations setup

The root tests/conftest.py handles Python path setup and basic environment.
"""
import os
import pytest
import asyncio
import warnings
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

# Suppress RuntimeWarnings about unawaited coroutines during asyncpg connection cleanup
# These warnings occur during garbage collection when connections are GC'd after the
# event loop closes. They are harmless and don't affect test functionality.
warnings.filterwarnings(
    "ignore",
    message=".*coroutine 'Connection._cancel' was never awaited.*",
    category=RuntimeWarning,
)

# Suppress warnings about tasks attached to different event loops
# This can occur during fixture cleanup when pytest-asyncio creates a new event loop
# for the next test while cleanup from the previous test is still running.
# This is harmless because each test cleans the database at the start anyway.
warnings.filterwarnings(
    "ignore",
    message=".*got Future.*attached to a different loop.*",
    category=RuntimeWarning,
)

# Note: Python path setup is handled in tests/conftest.py (parent conftest)
# We override environment variables here for integration tests

# Set environment variables BEFORE importing modules
os.environ.setdefault("LOG_LEVEL", "DEBUG")

os.environ["DATABASE_URL"] = "postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel_test"
os.environ["REDIS_PASSWORD"] = "dev_redis_password"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"

# Import after environment variables are set
from src.db.base import Base, async_session_maker
from src.db.models.supplier import Supplier
from src.db.models.supplier_item import SupplierItem
from src.db.models.price_history import PriceHistory
from src.db.models.parsing_log import ParsingLog
from src.db.models.product import Product
from src.db.models.category import Category


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests with proper cleanup."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    # Cancel all pending tasks before closing
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            if not task.done():
                task.cancel()
        # Run until all tasks are cancelled
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass  # Ignore errors during cleanup
    finally:
        loop.close()


def _run_migrations_sync():
    """Run Alembic migrations synchronously using subprocess."""
    import subprocess
    import sys
    
    # Get the project root (where alembic.ini is located)
    project_root = Path(__file__).parent.parent.parent
    
    # Run alembic upgrade head command
    # This ensures proper initialization of Alembic context
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        raise RuntimeError(
            f"Migration failed with return code {result.returncode}.\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )


async def _run_migrations():
    """Run Alembic migrations to set up the test database schema."""
    # Run migrations in a thread pool since subprocess is blocking
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations_sync)


@pytest.fixture(scope="session", autouse=True)
def setup_database(event_loop):
    """Set up database schema by running migrations before all tests.
    
    This is a synchronous fixture that runs async code to ensure
    migrations are applied before any tests run.
    """
    # Run async migrations in the event loop
    event_loop.run_until_complete(_run_migrations())
    yield
    # Cleanup: Close all database connections properly
    # This helps prevent RuntimeWarning about unawaited coroutines
    async def _cleanup_connections():
        """Close all database connections and dispose engine."""
        try:
            from src.db.base import engine
            if engine:
                # Close all connections in the pool
                await engine.dispose(close=True)
        except Exception:
            pass  # Ignore errors during cleanup
    
    # Run cleanup in event loop before it closes
    try:
        event_loop.run_until_complete(_cleanup_connections())
        # Give a small delay for connections to fully close
        import time
        time.sleep(0.1)
    except Exception:
        pass  # Ignore errors during cleanup


@pytest.fixture(autouse=True)
async def dispose_engine_pool():
    """Dispose engine connection pool after each test to prevent event loop mismatches.
    
    With asyncio_mode=auto, each test gets a new event loop. Database connections
    from the previous test's loop need to be closed. This fixture ensures the
    connection pool is disposed after each test.
    """
    yield
    # Dispose connections after test completes
    try:
        from src.db.base import engine
        if engine:
            await engine.dispose(close=False)  # Close connections, keep pool
    except Exception:
        # Ignore errors - engine might not be initialized yet
        pass


@pytest.fixture
async def db_session():
    """Create database session for each test with automatic cleanup.
    
    With asyncio_mode=auto, pytest-asyncio creates a new event loop for each test.
    The dispose_engine_pool fixture ensures connections are closed between tests.
    """
    # Use the existing async_session_maker from base
    # The async with statement automatically handles session cleanup
    async with async_session_maker() as session:
        # Clean database before test
        try:
            await _clean_database(session)
        except Exception as e:
            # If cleanup fails, continue anyway - database might be clean or we'll clean at end
            error_msg = str(e)
            if "attached to a different loop" not in error_msg and "Event loop is closed" not in error_msg:
                warnings.warn(f"Pre-test cleanup failed: {e}", RuntimeWarning, stacklevel=2)
        yield session
        # Clean database after test
        try:
            await _clean_database(session)
        except (RuntimeError, Exception) as e:
            # Handle edge cases where cleanup might fail:
            # 1. Event loop mismatch (harmless - next test will clean up)
            # 2. Session already closed
            error_msg = str(e)
            if "attached to a different loop" not in error_msg and "Event loop is closed" not in error_msg:
                # Unexpected error - log it
                warnings.warn(f"Post-test cleanup failed: {e}", RuntimeWarning, stacklevel=2)
        # Session is automatically closed by async with context manager


async def _clean_database(session: AsyncSession):
    """Clean all test data from database.
    
    This function may raise RuntimeError if called in a different event loop context.
    The calling fixture handles this gracefully.
    """
    try:
        # Delete in reverse dependency order
        await session.execute(delete(ParsingLog))
        await session.execute(delete(PriceHistory))
        await session.execute(delete(SupplierItem))
        await session.execute(delete(Supplier))
        await session.execute(delete(Product))
        await session.execute(delete(Category))
        await session.commit()
    except Exception as e:
        try:
            await session.rollback()
        except Exception:
            # Session might already be closed - ignore
            pass
        # Re-raise RuntimeError about event loop mismatch to handle in fixture
        # Other exceptions are also re-raised to be handled by the fixture
        raise

