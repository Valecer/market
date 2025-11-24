"""Health check script for worker service."""
import sys
import asyncio
from redis.asyncio import Redis
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


async def main() -> int:
    """Run health checks and return exit code.
    
    Returns:
        0 if all checks pass, 1 otherwise
    """
    redis_ok = await check_redis_connection()
    
    if not redis_ok:
        print("Health check failed: Redis connection unavailable", file=sys.stderr)
        return 1
    
    print("Health check passed: All services available")
    return 0


# Support both direct execution and module execution (-m flag)
if __name__ == "__main__" or __name__ == "src.health_check":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
