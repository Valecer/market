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

