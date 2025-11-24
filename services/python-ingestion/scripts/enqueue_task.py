#!/usr/bin/env python3
"""Helper script for enqueuing parse tasks to Redis queue.

Usage:
    python scripts/enqueue_task.py --task-id task-001 --parser-type google_sheets \\
        --supplier-name "Acme Wholesale" --sheet-url "https://docs.google.com/..."
"""
import asyncio
import argparse
import json
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
        print("\n   Or copy from .env.example:")
        print(f"   cp {project_root.parent / '.env.example'} {env_file}")
        sys.exit(1)

from arq.connections import RedisSettings, create_pool
from arq import ArqRedis
from src.config import settings
from src.models.queue_message import ParseTaskMessage
# Import parsers to trigger registration
import src.parsers  # noqa: F401
from src.parsers import list_registered_parsers


async def enqueue_task(
    task_id: str,
    parser_type: str,
    supplier_name: str,
    source_config: Dict[str, Any],
    retry_count: int = 0,
    max_retries: int = 3,
    priority: str = "normal"
) -> str:
    """Enqueue a parse task to Redis queue.
    
    Args:
        task_id: Unique task identifier
        parser_type: Type of parser (google_sheets, csv, excel)
        supplier_name: Name of the supplier
        source_config: Parser-specific configuration
        retry_count: Current retry attempt (default: 0)
        max_retries: Maximum retry attempts (default: 3)
        priority: Task priority (low, normal, high)
    
    Returns:
        Job ID from arq
    """
    # Validate message using Pydantic model
    task_msg = ParseTaskMessage(
        task_id=task_id,
        parser_type=parser_type,
        supplier_name=supplier_name,
        source_config=source_config,
        retry_count=retry_count,
        max_retries=max_retries,
        priority=priority,
        enqueued_at=datetime.now(timezone.utc)
    )
    
    # Create Redis connection pool
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool: ArqRedis = await create_pool(redis_settings)
    
    try:
        # Enqueue the task (pass message dict as first positional arg after ctx)
        job = await pool.enqueue_job(
            "parse_task",
            message=task_msg.model_dump(),
            _job_id=task_id
        )
        
        if job:
            print(f"✅ Task enqueued successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Job ID: {job.job_id}")
            print(f"   Parser Type: {parser_type}")
            print(f"   Supplier: {supplier_name}")
            return job.job_id
        else:
            print(f"❌ Failed to enqueue task (job with ID {task_id} may already exist)")
            return None
    finally:
        await pool.aclose()


async def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Enqueue a parse task to Redis queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enqueue Google Sheets task
  python scripts/enqueue_task.py \\
    --task-id task-001 \\
    --parser-type google_sheets \\
    --supplier-name "Acme Wholesale" \\
    --sheet-url "https://docs.google.com/spreadsheets/d/abc123/edit" \\
    --sheet-name "Price List"

  # Enqueue with custom config JSON
  python scripts/enqueue_task.py \\
    --task-id task-002 \\
    --parser-type google_sheets \\
    --supplier-name "Test Supplier" \\
    --config-file config.json
        """
    )
    
    parser.add_argument(
        "--task-id",
        required=True,
        help="Unique task identifier"
    )
    # Get available parsers dynamically from registry
    available_parsers = list_registered_parsers()
    if not available_parsers:
        # Fallback to known parsers if registry is empty
        available_parsers = ["google_sheets", "csv", "excel", "stub"]
    
    parser.add_argument(
        "--parser-type",
        required=True,
        choices=available_parsers,
        help=f"Type of parser to use (available: {', '.join(available_parsers)})"
    )
    parser.add_argument(
        "--supplier-name",
        required=True,
        help="Name of the supplier"
    )
    
    # Source config options
    config_group = parser.add_mutually_exclusive_group(required=True)
    config_group.add_argument(
        "--config-file",
        help="Path to JSON file containing source_config"
    )
    config_group.add_argument(
        "--sheet-url",
        help="Google Sheets URL (for google_sheets parser)"
    )
    
    parser.add_argument(
        "--sheet-name",
        default="Sheet1",
        help="Sheet name (for google_sheets parser, default: Sheet1)"
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=0,
        help="Current retry attempt (default: 0)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)"
    )
    parser.add_argument(
        "--priority",
        choices=["low", "normal", "high"],
        default="normal",
        help="Task priority (default: normal)"
    )
    
    args = parser.parse_args()
    
    # Build source_config
    if args.config_file:
        with open(args.config_file, "r") as f:
            source_config = json.load(f)
    elif args.sheet_url:
        source_config = {
            "sheet_url": args.sheet_url,
            "sheet_name": args.sheet_name
        }
    else:
        parser.error("Either --config-file or --sheet-url must be provided")
    
    # Enqueue task
    try:
        job_id = await enqueue_task(
            task_id=args.task_id,
            parser_type=args.parser_type,
            supplier_name=args.supplier_name,
            source_config=source_config,
            retry_count=args.retry_count,
            max_retries=args.max_retries,
            priority=args.priority
        )
        sys.exit(0 if job_id else 1)
    except Exception as e:
        print(f"❌ Error enqueuing task: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

