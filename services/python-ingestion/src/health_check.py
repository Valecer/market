"""Health check script for worker service."""
import sys
import asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from src.config import settings


async def check_redis_connection() -> bool:
    """Check if Redis connection is available.
    
    Returns:
        True if Redis is accessible, False otherwise
    """
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True
        )
        await redis.ping()
        await redis.aclose()
        return True
    except Exception as e:
        print(f"Redis health check failed: {e}", file=sys.stderr)
        return False


async def check_database_connection() -> bool:
    """Check if PostgreSQL database connection is available.
    
    Returns:
        True if database is accessible, False otherwise
    """
    try:
        from sqlalchemy import text
        # Create a temporary engine just for health check
        engine = create_async_engine(
            settings.database_url,
            connect_args={"server_settings": {"application_name": "health_check"}},
            pool_pre_ping=True,  # Verify connection health
        )
        async with engine.begin() as conn:
            # Execute a simple query to verify connection
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception as e:
        print(f"Database health check failed: {e}", file=sys.stderr)
        return False


async def main() -> int:
    """Run health checks and return exit code.
    
    Returns:
        0 if all checks pass, 1 otherwise
    """
    redis_ok = await check_redis_connection()
    database_ok = await check_database_connection()
    
    if not redis_ok:
        print("Health check failed: Redis connection unavailable", file=sys.stderr)
        return 1
    
    if not database_ok:
        print("Health check failed: Database connection unavailable", file=sys.stderr)
        return 1
    
    print("Health check passed: All services available")
    return 0


# Only execute when run directly as a script
if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
