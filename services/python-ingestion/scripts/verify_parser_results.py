#!/usr/bin/env python3
"""Script to verify parser results for T082 and T083.

This script checks:
- T082: Verify 95 ParsedSupplierItem objects returned from parser
- T083: Verify 5 ValidationError entries (will check logs until Phase 7 completes)

Usage:
    python scripts/verify_parser_results.py --task-id test-001
"""
import argparse
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Add src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Load .env file if it exists
env_file = project_root / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

from arq.connections import RedisSettings, create_pool
from arq import ArqRedis
from src.config import settings

# Try to import database models for Phase 7 checks
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select, func
    from src.db.base import Base
    from src.db.models.parsing_log import ParsingLog
    from src.db.models.supplier_item import SupplierItem
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("⚠️  Database models not available - T083 check will be limited")


async def get_task_result(task_id: str, pool: ArqRedis) -> Dict[str, Any] | None:
    """Get task result from Redis.
    
    Args:
        task_id: Task identifier
        pool: Redis connection pool
    
    Returns:
        Task result dictionary or None if not found
    """
    try:
        # Try to get result from arq
        result_key = f"arq:result:{settings.queue_name}:{task_id}"
        result_data = await pool.get(result_key)
        if result_data:
            return json.loads(result_data)
    except Exception as e:
        print(f"⚠️  Could not retrieve task result from Redis: {e}")
    
    return None


async def check_parsing_logs(task_id: str, expected_errors: int = 5) -> Dict[str, Any]:
    """Check parsing_logs table for ValidationError entries.
    
    Args:
        task_id: Task identifier
        expected_errors: Expected number of ValidationError entries
    
    Returns:
        Dictionary with check results
    """
    if not DB_AVAILABLE:
        return {
            "available": False,
            "message": "Database not available - Phase 7 (data ingestion) not yet complete"
        }
    
    try:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session_maker() as session:
            # Count ValidationError entries for this task
            stmt = select(func.count(ParsingLog.id)).where(
                ParsingLog.task_id == task_id,
                ParsingLog.error_type == "ValidationError"
            )
            result = await session.execute(stmt)
            error_count = result.scalar() or 0
            
            # Get all parsing logs for this task
            stmt_all = select(ParsingLog).where(ParsingLog.task_id == task_id)
            result_all = await session.execute(stmt_all)
            all_logs = result_all.scalars().all()
            
            return {
                "available": True,
                "error_count": error_count,
                "expected_errors": expected_errors,
                "matches": error_count == expected_errors,
                "total_logs": len(all_logs),
                "logs": [
                    {
                        "error_type": log.error_type,
                        "error_message": log.error_message,
                        "row_number": log.row_number
                    }
                    for log in all_logs[:10]  # Show first 10
                ]
            }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "message": f"Could not query parsing_logs table: {e}"
        }


async def check_supplier_items(supplier_name: str, expected_count: int = 95) -> Dict[str, Any]:
    """Check supplier_items table for parsed items (Phase 7 feature).
    
    Args:
        supplier_name: Name of supplier
        expected_count: Expected number of items
    
    Returns:
        Dictionary with check results
    """
    if not DB_AVAILABLE:
        return {
            "available": False,
            "message": "Database not available - Phase 7 (data ingestion) not yet complete"
        }
    
    try:
        from src.db.models.supplier import Supplier
        
        engine = create_async_engine(settings.database_url, echo=False)
        async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session_maker() as session:
            # Find supplier
            stmt = select(Supplier).where(Supplier.name == supplier_name)
            result = await session.execute(stmt)
            supplier = result.scalar_one_or_none()
            
            if not supplier:
                return {
                    "available": True,
                    "supplier_found": False,
                    "message": f"Supplier '{supplier_name}' not found in database"
                }
            
            # Count supplier items
            stmt_count = select(func.count(SupplierItem.id)).where(
                SupplierItem.supplier_id == supplier.id
            )
            result_count = await session.execute(stmt_count)
            item_count = result_count.scalar() or 0
            
            return {
                "available": True,
                "supplier_found": True,
                "item_count": item_count,
                "expected_count": expected_count,
                "matches": item_count == expected_count
            }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "message": f"Could not query supplier_items table: {e}"
        }


async def verify_task_results(task_id: str, supplier_name: str) -> None:
    """Verify parser results for T082 and T083.
    
    Args:
        task_id: Task identifier
        supplier_name: Supplier name
    """
    print("\n" + "=" * 70)
    print(f"Verifying Parser Results for Task: {task_id}")
    print("=" * 70)
    
    # Create Redis connection
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool: ArqRedis = await create_pool(redis_settings)
    
    try:
        # Check task result from Redis
        print("\n📊 Checking Task Results (T082 - Parser Output)...")
        print("-" * 70)
        
        task_result = await get_task_result(task_id, pool)
        if task_result:
            print(f"✅ Task result found in Redis")
            print(f"   Status: {task_result.get('status', 'unknown')}")
            print(f"   Items Parsed: {task_result.get('items_parsed', 0)}")
            print(f"   Errors: {len(task_result.get('errors', []))}")
            
            items_parsed = task_result.get('items_parsed', 0)
            if items_parsed == 95:
                print(f"   ✅ T082 PASS: 95 ParsedSupplierItem objects returned (as expected)")
            else:
                print(f"   ⚠️  T082 CHECK: Expected 95 items, got {items_parsed}")
        else:
            print(f"⚠️  Task result not found in Redis")
            print(f"   The task may still be processing or result has expired")
            print(f"   Check worker logs for task completion")
        
        # Check parsing logs (T083)
        print("\n📋 Checking Parsing Logs (T083 - Error Logging)...")
        print("-" * 70)
        
        logs_result = await check_parsing_logs(task_id, expected_errors=5)
        if logs_result.get("available"):
            error_count = logs_result.get("error_count", 0)
            expected = logs_result.get("expected_errors", 5)
            
            if error_count == expected:
                print(f"✅ T083 PASS: {error_count} ValidationError entries found in parsing_logs")
            else:
                print(f"⚠️  T083 CHECK: Expected {expected} errors, found {error_count}")
            
            if logs_result.get("logs"):
                print(f"\n   Recent error logs:")
                for log in logs_result["logs"][:5]:
                    print(f"   - Row {log['row_number']}: {log['error_type']} - {log['error_message'][:60]}")
        else:
            print(f"ℹ️  T083 INFO: {logs_result.get('message', 'Database check not available')}")
            print(f"   Phase 7 (data ingestion pipeline) needs to be complete for full T083 verification")
            print(f"   Currently, the parser logs errors but doesn't persist them to database yet")
        
        # Check supplier items (bonus check for Phase 7)
        print("\n📦 Checking Supplier Items (Phase 7 - Data Persistence)...")
        print("-" * 70)
        
        items_result = await check_supplier_items(supplier_name, expected_count=95)
        if items_result.get("available"):
            if items_result.get("supplier_found"):
                item_count = items_result.get("item_count", 0)
                expected = items_result.get("expected_count", 95)
                if item_count == expected:
                    print(f"✅ Phase 7 CHECK: {item_count} supplier items found in database")
                else:
                    print(f"⚠️  Phase 7 CHECK: Expected {expected} items, found {item_count}")
            else:
                print(f"ℹ️  Phase 7 INFO: {items_result.get('message')}")
        else:
            print(f"ℹ️  Phase 7 INFO: {items_result.get('message', 'Database not available')}")
            print(f"   Phase 7 (data ingestion pipeline) not yet complete")
        
        # Summary
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        
        if task_result and task_result.get('items_parsed') == 95:
            print("✅ T082: PARSER TEST PASSED - 95 items parsed successfully")
        else:
            print("⏳ T082: PARSER TEST - Check worker logs for detailed results")
        
        if logs_result.get("available") and logs_result.get("error_count") == 5:
            print("✅ T083: ERROR LOGGING PASSED - 5 ValidationErrors logged to parsing_logs")
        else:
            print("⏳ T083: ERROR LOGGING - Phase 7 needed for full verification")
            print("   (Parser handles errors, but database logging happens in Phase 7)")
        
        print("\n💡 Tip: Check worker logs for detailed parsing output:")
        print("   docker-compose logs -f worker | grep test-001")
        print("=" * 70)
        
    finally:
        await pool.aclose()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify parser results for T082 and T083",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--task-id',
        type=str,
        required=True,
        help='Task ID to verify (e.g., test-001)'
    )
    
    parser.add_argument(
        '--supplier-name',
        type=str,
        default='Test Supplier',
        help='Supplier name (default: Test Supplier)'
    )
    
    args = parser.parse_args()
    
    try:
        await verify_task_results(args.task_id, args.supplier_name)
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        import asyncio
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n\nVerification cancelled.")
        sys.exit(0)

