"""Health check script for Docker container."""
import sys
import asyncio
from redis.asyncio import Redis
from src.config import settings


async def check_redis() -> bool:
    """Check Redis connection health."""
    try:
        redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True,
        )
        await redis.ping()
        await redis.aclose()
        return True
    except Exception:
        return False


async def main() -> int:
    """Run health checks and return exit code."""
    redis_healthy = await check_redis()
    
    if not redis_healthy:
        print("Health check failed: Redis connection failed", file=sys.stderr)
        return 1
    
    print("Health check passed: All services healthy")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

