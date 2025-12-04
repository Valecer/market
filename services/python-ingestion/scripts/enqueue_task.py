#!/usr/bin/env python3
"""Helper script for enqueuing download and ML processing tasks to Redis queue.

Phase 9: Courier pattern - triggers ML pipeline instead of legacy parsing.

Usage:
    python scripts/enqueue_task.py --task-id task-001 --source-type google_sheets \\
        --supplier-name "Acme Wholesale" --source-url "https://docs.google.com/..."
"""
import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

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
        sys.exit(1)

from arq.connections import RedisSettings, create_pool
from arq import ArqRedis
from src.config import settings


async def enqueue_ml_task(
    task_id: str,
    job_id: str,
    supplier_id: str,
    supplier_name: str,
    source_type: str,
    source_url: str,
    original_filename: Optional[str] = None,
    sheet_name: Optional[str] = None,
) -> str:
    """Enqueue a download_and_trigger_ml task.
    
    Args:
        task_id: Unique task identifier
        job_id: Unique job identifier for tracking
        supplier_id: Supplier UUID
        supplier_name: Human-readable supplier name
        source_type: Source type (google_sheets, csv, excel)
        source_url: URL or path to source file
        original_filename: Original filename for metadata
        sheet_name: Sheet name for Google Sheets
    
    Returns:
        Enqueued job ID
    """
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    
    print(f"📤 Connecting to Redis: {settings.redis_url.split('@')[-1] if '@' in settings.redis_url else settings.redis_url}")
    
    pool: ArqRedis = await create_pool(redis_settings)
    
    try:
        job = await pool.enqueue_job(
            "download_and_trigger_ml",
            task_id=task_id,
            job_id=job_id,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            source_type=source_type,
            source_url=source_url,
            original_filename=original_filename,
            sheet_name=sheet_name,
            use_ml_processing=True,
        )
        
        print(f"✅ Task enqueued successfully!")
        print(f"   Task ID:  {task_id}")
        print(f"   Job ID:   {job_id}")
        print(f"   Queue:    {settings.queue_name}")
        print(f"   Supplier: {supplier_name}")
        print(f"   Source:   {source_type}")
        
        return job.job_id
        
    finally:
        await pool.close()


def main():
    parser = argparse.ArgumentParser(
        description="Enqueue ML processing task to Redis queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Google Sheets
  python scripts/enqueue_task.py --source-type google_sheets \\
    --supplier-name "Acme Corp" \\
    --source-url "https://docs.google.com/spreadsheets/d/abc123/edit"

  # Excel file (local path in shared volume)
  python scripts/enqueue_task.py --source-type excel \\
    --supplier-name "Test Supplier" \\
    --source-url "/uploads/price-list.xlsx"

  # CSV file
  python scripts/enqueue_task.py --source-type csv \\
    --supplier-name "CSV Supplier" \\
    --source-url "https://example.com/prices.csv"
        """
    )
    
    parser.add_argument(
        "--task-id",
        help="Unique task ID (auto-generated if not provided)"
    )
    parser.add_argument(
        "--job-id",
        help="Unique job ID for tracking (auto-generated if not provided)"
    )
    parser.add_argument(
        "--supplier-id",
        help="Supplier UUID (auto-generated if not provided)"
    )
    parser.add_argument(
        "--supplier-name",
        required=True,
        help="Human-readable supplier name"
    )
    parser.add_argument(
        "--source-type",
        required=True,
        choices=["google_sheets", "csv", "excel"],
        help="Source type"
    )
    parser.add_argument(
        "--source-url",
        required=True,
        help="URL or path to source file"
    )
    parser.add_argument(
        "--filename",
        help="Original filename for metadata"
    )
    parser.add_argument(
        "--sheet-name",
        default="Sheet1",
        help="Sheet name for Google Sheets (default: Sheet1)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print task details without enqueuing"
    )
    
    args = parser.parse_args()
    
    # Generate IDs if not provided
    timestamp = int(datetime.now(timezone.utc).timestamp())
    task_id = args.task_id or f"enqueue-{timestamp}-{args.supplier_name.lower().replace(' ', '-')}"
    job_id = args.job_id or str(uuid4())
    supplier_id = args.supplier_id or str(uuid4())
    
    # Determine filename
    original_filename = args.filename
    if not original_filename:
        if args.source_type == "google_sheets":
            original_filename = f"{args.supplier_name}_export.xlsx"
        else:
            original_filename = Path(args.source_url).name
    
    if args.dry_run:
        print("🔍 DRY RUN - Task details:")
        print(f"   Task ID:     {task_id}")
        print(f"   Job ID:      {job_id}")
        print(f"   Supplier ID: {supplier_id}")
        print(f"   Supplier:    {args.supplier_name}")
        print(f"   Source Type: {args.source_type}")
        print(f"   Source URL:  {args.source_url}")
        print(f"   Filename:    {original_filename}")
        if args.source_type == "google_sheets":
            print(f"   Sheet Name:  {args.sheet_name}")
        return
    
    # Enqueue task
    asyncio.run(enqueue_ml_task(
        task_id=task_id,
        job_id=job_id,
        supplier_id=supplier_id,
        supplier_name=args.supplier_name,
        source_type=args.source_type,
        source_url=args.source_url,
        original_filename=original_filename,
        sheet_name=args.sheet_name if args.source_type == "google_sheets" else None,
    ))


if __name__ == "__main__":
    main()
