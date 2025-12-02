"""Sync state management service using Redis.

This module provides helper functions for managing sync pipeline state
in Redis, including:
- Distributed lock acquisition/release
- Sync status tracking
- Progress updates for UI feedback
"""
import json
from typing import Optional, Tuple
from datetime import datetime, timezone
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.models.sync_messages import (
    SyncState,
    SyncStatusMessage,
    SyncProgressUpdate,
)

logger = structlog.get_logger(__name__)

# Redis key constants
SYNC_STATUS_KEY = "sync:status"
SYNC_LOCK_KEY = "sync:lock"
SYNC_LAST_RUN_KEY = "sync:last_run"

# Lock TTL (1 hour) - auto-expires to prevent deadlocks
SYNC_LOCK_TTL_SECONDS = 3600


async def acquire_sync_lock(
    redis: Redis,
    task_id: str,
    ttl_seconds: int = SYNC_LOCK_TTL_SECONDS,
) -> Tuple[bool, Optional[str]]:
    """Acquire an exclusive sync lock using Redis SET NX.
    
    Uses Redis SET NX (set if not exists) to implement a distributed lock.
    Only one sync operation can run at a time across all workers.
    
    Args:
        redis: Redis connection
        task_id: Unique identifier for the sync task
        ttl_seconds: Lock TTL in seconds (default: 1 hour)
    
    Returns:
        Tuple of (acquired: bool, current_holder: str or None)
        - acquired=True: Lock was acquired successfully
        - acquired=False: Lock held by another task (current_holder contains task_id)
    """
    log = logger.bind(task_id=task_id)
    
    try:
        # Try to acquire lock using SET NX with expiry
        result = await redis.set(
            SYNC_LOCK_KEY,
            task_id,
            nx=True,  # Only set if not exists
            ex=ttl_seconds,  # Expire after TTL
        )
        
        if result:
            log.info("sync_lock_acquired", ttl_seconds=ttl_seconds)
            return True, None
        else:
            # Lock held by another task
            current_holder = await redis.get(SYNC_LOCK_KEY)
            holder_id = current_holder.decode() if current_holder else "unknown"
            log.warning("sync_lock_denied", current_holder=holder_id)
            return False, holder_id
            
    except RedisError as e:
        log.error("sync_lock_acquire_failed", error=str(e))
        raise


async def release_sync_lock(
    redis: Redis,
    task_id: str,
) -> bool:
    """Release the sync lock if held by this task.
    
    Only releases the lock if it's held by the specified task_id.
    This prevents accidentally releasing another task's lock.
    
    Args:
        redis: Redis connection
        task_id: Task ID that should hold the lock
    
    Returns:
        True if lock was released, False if lock not held by this task
    """
    log = logger.bind(task_id=task_id)
    
    try:
        # Use Lua script for atomic check-and-delete
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await redis.eval(script, 1, SYNC_LOCK_KEY, task_id)
        
        if result:
            log.info("sync_lock_released")
            return True
        else:
            current_holder = await redis.get(SYNC_LOCK_KEY)
            holder_id = current_holder.decode() if current_holder else "none"
            log.warning("sync_lock_not_owned", current_holder=holder_id)
            return False
            
    except RedisError as e:
        log.error("sync_lock_release_failed", error=str(e))
        raise


async def get_sync_status(
    redis: Redis,
) -> SyncStatusMessage:
    """Get current sync status from Redis.
    
    Args:
        redis: Redis connection
    
    Returns:
        SyncStatusMessage with current sync state
    """
    try:
        status_json = await redis.get(SYNC_STATUS_KEY)
        
        if status_json:
            status_data = json.loads(status_json.decode())
            return SyncStatusMessage(**status_data)
        else:
            # No status stored, return idle state
            return SyncStatusMessage(state=SyncState.IDLE)
            
    except (json.JSONDecodeError, RedisError) as e:
        logger.error("get_sync_status_failed", error=str(e))
        # Return idle state on error
        return SyncStatusMessage(state=SyncState.IDLE)


async def update_sync_status(
    redis: Redis,
    state: SyncState,
    task_id: Optional[str] = None,
    started_at: Optional[str] = None,
    progress_current: int = 0,
    progress_total: int = 0,
) -> bool:
    """Update sync status in Redis.
    
    Args:
        redis: Redis connection
        state: New sync state
        task_id: Current task ID (if syncing)
        started_at: ISO timestamp when sync started
        progress_current: Number of suppliers processed
        progress_total: Total suppliers to process
    
    Returns:
        True if status was updated successfully
    """
    log = logger.bind(state=state.value, task_id=task_id)
    
    try:
        status = SyncStatusMessage(
            state=state,
            task_id=task_id,
            started_at=started_at,
            progress_current=progress_current,
            progress_total=progress_total,
        )
        
        await redis.set(
            SYNC_STATUS_KEY,
            json.dumps(status.model_dump()),
        )
        
        log.debug("sync_status_updated")
        return True
        
    except (json.JSONDecodeError, RedisError) as e:
        log.error("update_sync_status_failed", error=str(e))
        return False


async def update_sync_progress(
    redis: Redis,
    current: int,
    total: int,
) -> bool:
    """Update sync progress for UI feedback.
    
    Efficiently updates only the progress fields without
    modifying other status data.
    
    Args:
        redis: Redis connection
        current: Number of suppliers processed
        total: Total suppliers to process
    
    Returns:
        True if progress was updated successfully
    """
    log = logger.bind(current=current, total=total)
    
    try:
        # Get current status
        status = await get_sync_status(redis)
        
        # Update progress fields
        status.progress_current = current
        status.progress_total = total
        
        await redis.set(
            SYNC_STATUS_KEY,
            json.dumps(status.model_dump()),
        )
        
        log.debug(
            "sync_progress_updated",
            percentage=status.progress_percentage,
        )
        return True
        
    except (json.JSONDecodeError, RedisError) as e:
        log.error("update_sync_progress_failed", error=str(e))
        return False


async def set_sync_started(
    redis: Redis,
    task_id: str,
) -> bool:
    """Mark sync as started (syncing_master state).
    
    Args:
        redis: Redis connection
        task_id: Task ID for the sync operation
    
    Returns:
        True if status was updated successfully
    """
    return await update_sync_status(
        redis=redis,
        state=SyncState.SYNCING_MASTER,
        task_id=task_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


async def set_sync_processing_suppliers(
    redis: Redis,
    task_id: str,
    total_suppliers: int,
) -> bool:
    """Mark sync as processing suppliers.
    
    Args:
        redis: Redis connection
        task_id: Task ID for the sync operation
        total_suppliers: Total number of suppliers to process
    
    Returns:
        True if status was updated successfully
    """
    # Get current started_at
    current_status = await get_sync_status(redis)
    
    return await update_sync_status(
        redis=redis,
        state=SyncState.PROCESSING_SUPPLIERS,
        task_id=task_id,
        started_at=current_status.started_at,
        progress_current=0,
        progress_total=total_suppliers,
    )


async def set_sync_idle(
    redis: Redis,
) -> bool:
    """Mark sync as idle (completed or not running).
    
    Args:
        redis: Redis connection
    
    Returns:
        True if status was updated successfully
    """
    return await update_sync_status(
        redis=redis,
        state=SyncState.IDLE,
    )


async def record_sync_completion(
    redis: Redis,
) -> bool:
    """Record sync completion timestamp.
    
    Args:
        redis: Redis connection
    
    Returns:
        True if timestamp was recorded successfully
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        await redis.set(SYNC_LAST_RUN_KEY, now)
        logger.debug("sync_completion_recorded", completed_at=now)
        return True
    except RedisError as e:
        logger.error("record_sync_completion_failed", error=str(e))
        return False


async def get_last_sync_at(
    redis: Redis,
) -> Optional[str]:
    """Get timestamp of last completed sync.
    
    Args:
        redis: Redis connection
    
    Returns:
        ISO timestamp string or None if never synced
    """
    try:
        last_run = await redis.get(SYNC_LAST_RUN_KEY)
        if last_run:
            return last_run.decode()
        return None
    except RedisError as e:
        logger.error("get_last_sync_at_failed", error=str(e))
        return None


async def check_sync_lock(
    redis: Redis,
) -> Tuple[bool, Optional[str]]:
    """Check if sync lock is currently held.
    
    Args:
        redis: Redis connection
    
    Returns:
        Tuple of (is_locked: bool, holder_task_id: str or None)
    """
    try:
        holder = await redis.get(SYNC_LOCK_KEY)
        if holder:
            return True, holder.decode()
        return False, None
    except RedisError as e:
        logger.error("check_sync_lock_failed", error=str(e))
        return False, None


# =============================================================================
# Manual Sync Trigger (for Bun API integration)
# =============================================================================

SYNC_TRIGGER_KEY = "sync:trigger"


async def set_sync_trigger(
    redis: Redis,
    task_id: str,
    triggered_by: str = "manual",
) -> bool:
    """Set a sync trigger request in Redis.
    
    This is called by the Bun API to request a manual sync.
    The Python worker polls this key and triggers sync when set.
    
    Args:
        redis: Redis connection
        task_id: Unique task identifier
        triggered_by: What initiated the sync ("manual" or "api")
    
    Returns:
        True if trigger was set successfully
    """
    log = logger.bind(task_id=task_id, triggered_by=triggered_by)
    
    try:
        trigger_data = {
            "task_id": task_id,
            "triggered_by": triggered_by,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Use SET with NX to prevent overwriting existing trigger
        # TTL of 5 minutes to auto-cleanup stale triggers
        result = await redis.set(
            SYNC_TRIGGER_KEY,
            json.dumps(trigger_data),
            nx=True,
            ex=300,  # 5 minute TTL
        )
        
        if result:
            log.info("sync_trigger_set")
            return True
        else:
            # Trigger already exists
            log.warning("sync_trigger_already_pending")
            return False
            
    except RedisError as e:
        log.error("set_sync_trigger_failed", error=str(e))
        raise


async def get_sync_trigger(
    redis: Redis,
) -> Optional[dict]:
    """Get pending sync trigger from Redis.
    
    Called by the Python worker to check for manual sync requests.
    
    Args:
        redis: Redis connection
    
    Returns:
        Trigger data dict or None if no trigger pending
    """
    try:
        trigger_json = await redis.get(SYNC_TRIGGER_KEY)
        
        if trigger_json:
            return json.loads(trigger_json.decode())
        return None
        
    except (json.JSONDecodeError, RedisError) as e:
        logger.error("get_sync_trigger_failed", error=str(e))
        return None


async def clear_sync_trigger(
    redis: Redis,
) -> bool:
    """Clear the sync trigger after processing.
    
    Args:
        redis: Redis connection
    
    Returns:
        True if trigger was cleared
    """
    try:
        await redis.delete(SYNC_TRIGGER_KEY)
        logger.debug("sync_trigger_cleared")
        return True
    except RedisError as e:
        logger.error("clear_sync_trigger_failed", error=str(e))
        return False


# =============================================================================
# Parse Trigger (for file upload integration)
# =============================================================================

PARSE_TRIGGERS_KEY = "parse:triggers"


async def add_parse_trigger(
    redis: Redis,
    task_id: str,
    parser_type: str,
    supplier_name: str,
    source_config: dict,
) -> bool:
    """Add a parse trigger to the queue.
    
    Called by Bun API when a file is uploaded for parsing.
    The Python worker polls this and executes parse tasks.
    
    Args:
        redis: Redis connection
        task_id: Unique task identifier
        parser_type: Parser type (csv, excel, google_sheets)
        supplier_name: Name of the supplier
        source_config: Parser configuration dict
    
    Returns:
        True if trigger was added successfully
    """
    log = logger.bind(task_id=task_id, parser_type=parser_type, supplier_name=supplier_name)
    
    try:
        trigger_data = {
            "task_id": task_id,
            "parser_type": parser_type,
            "supplier_name": supplier_name,
            "source_config": source_config,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add to list of pending triggers
        await redis.rpush(PARSE_TRIGGERS_KEY, json.dumps(trigger_data))
        log.info("parse_trigger_added")
        return True
        
    except RedisError as e:
        log.error("add_parse_trigger_failed", error=str(e))
        raise


async def get_pending_parse_triggers(
    redis: Redis,
    max_count: int = 10,
) -> list:
    """Get pending parse triggers from Redis.
    
    Atomically pops triggers from the list to prevent duplicate processing.
    
    Args:
        redis: Redis connection
        max_count: Maximum triggers to retrieve at once
    
    Returns:
        List of trigger data dicts
    """
    triggers = []
    
    try:
        for _ in range(max_count):
            # LPOP atomically removes and returns the first element
            trigger_json = await redis.lpop(PARSE_TRIGGERS_KEY)
            
            if not trigger_json:
                break
            
            try:
                trigger_data = json.loads(trigger_json.decode())
                triggers.append(trigger_data)
            except json.JSONDecodeError as e:
                logger.warning("parse_trigger_invalid_json", error=str(e))
                continue
        
        if triggers:
            logger.debug("parse_triggers_retrieved", count=len(triggers))
        
        return triggers
        
    except RedisError as e:
        logger.error("get_parse_triggers_failed", error=str(e))
        return []


async def get_parse_trigger_count(
    redis: Redis,
) -> int:
    """Get count of pending parse triggers.
    
    Args:
        redis: Redis connection
    
    Returns:
        Number of pending triggers
    """
    try:
        return await redis.llen(PARSE_TRIGGERS_KEY)
    except RedisError as e:
        logger.error("get_parse_trigger_count_failed", error=str(e))
        return 0

