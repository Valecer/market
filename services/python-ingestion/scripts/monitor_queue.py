#!/usr/bin/env python3
"""Helper script for monitoring Redis queue depth and DLQ.

Usage:
    python scripts/monitor_queue.py
    python scripts/monitor_queue.py --watch  # Continuous monitoring
"""
import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Load .env file if it exists (for local development)
env_file = project_root / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        print("⚠️  Warning: python-dotenv not installed. Install with: pip install python-dotenv")
        print("   Or set environment variables manually.")
elif not os.getenv("REDIS_PASSWORD") and not os.getenv("DATABASE_URL"):
    # Check if we're in Docker (where env vars should be set)
    if not os.path.exists("/.dockerenv"):
        print("⚠️  Error: .env file not found and required environment variables not set.")
        print(f"   Expected .env file at: {env_file}")
        print("   Please create .env file or set REDIS_PASSWORD and DATABASE_URL environment variables.")
        print("\n   Example .env file:")
        print("   REDIS_PASSWORD=dev_redis_password")
        print("   DATABASE_URL=postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel")
        sys.exit(1)

from arq.connections import RedisSettings, create_pool
from arq import ArqRedis
from src.config import settings


async def get_queue_stats(pool: ArqRedis) -> Dict[str, Any]:
    """Get queue statistics from Redis.
    
    Args:
        pool: Redis connection pool
    
    Returns:
        Dictionary with queue statistics
    """
    queue_name = settings.queue_name
    dlq_name = settings.dlq_name
    
    # Get queue depths
    queue_depth = await pool.llen(f"arq:queue:{queue_name}")
    # DLQ is stored as a Redis set (arq:dlq:{dlq_name})
    dlq_depth = await pool.scard(f"arq:dlq:{dlq_name}")
    
    # Get in-progress jobs (jobs being processed)
    in_progress = await pool.llen(f"arq:in-progress:{queue_name}")
    
    # Get job results count (approximate)
    results_count = await pool.llen(f"arq:result:{queue_name}")
    
    return {
        "queue_name": queue_name,
        "queue_depth": queue_depth,
        "in_progress": in_progress,
        "dlq_name": dlq_name,
        "dlq_depth": dlq_depth,
        "results_count": results_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def display_queue_stats(pool: ArqRedis) -> None:
    """Display queue statistics in a formatted table.
    
    Args:
        pool: Redis connection pool
    """
    stats = await get_queue_stats(pool)
    
    print("\n" + "=" * 60)
    print("Redis Queue Statistics")
    print("=" * 60)
    print(f"Timestamp: {stats['timestamp']}")
    print()
    print(f"Queue: {stats['queue_name']}")
    print(f"  Depth:        {stats['queue_depth']:>6} jobs")
    print(f"  In Progress:  {stats['in_progress']:>6} jobs")
    print(f"  Results:      {stats['results_count']:>6} results")
    print()
    print(f"Dead Letter Queue: {stats['dlq_name']}")
    print(f"  Depth:        {stats['dlq_depth']:>6} jobs")
    print("=" * 60)
    
    # Status indicators
    if stats['dlq_depth'] > 0:
        print("⚠️  WARNING: Dead letter queue has failed tasks!")
    if stats['queue_depth'] > 100:
        print("⚠️  WARNING: Queue depth is high (>100 jobs)")
    if stats['queue_depth'] == 0 and stats['in_progress'] == 0:
        print("✅ Queue is empty and idle")


async def monitor_continuous(pool: ArqRedis, interval: int = 5) -> None:
    """Continuously monitor queue statistics.
    
    Args:
        pool: Redis connection pool
        interval: Refresh interval in seconds (default: 5)
    """
    try:
        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")
            await display_queue_stats(pool)
            print(f"\nRefreshing every {interval} seconds (Ctrl+C to stop)...")
            await asyncio.sleep(interval)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\nMonitoring stopped.")
        # Exit cleanly without traceback
        raise SystemExit(0)


async def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Monitor Redis queue depth and DLQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Display current queue stats
  python scripts/monitor_queue.py

  # Continuous monitoring (refresh every 5 seconds)
  python scripts/monitor_queue.py --watch

  # Custom refresh interval
  python scripts/monitor_queue.py --watch --interval 10
        """
    )
    
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously monitor queue (refresh every N seconds)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Refresh interval in seconds for --watch mode (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Create Redis connection pool
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool: ArqRedis = await create_pool(redis_settings)
    
    try:
        if args.watch:
            await monitor_continuous(pool, args.interval)
        else:
            await display_queue_stats(pool)
    except SystemExit:
        # Re-raise SystemExit to exit cleanly (raised by monitor_continuous on Ctrl+C)
        raise
    except Exception as e:
        print(f"❌ Error monitoring queue: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await pool.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C at the top level to exit cleanly
        print("\n\nMonitoring stopped.")
        sys.exit(0)

