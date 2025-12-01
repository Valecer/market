"""Pydantic models for sync queue messages and status tracking.

This module defines the data models for sync pipeline communication
between the Bun API and Python worker via Redis queue.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime, timezone
from enum import Enum


class SyncState(str, Enum):
    """Sync pipeline states for status tracking."""
    IDLE = "idle"
    SYNCING_MASTER = "syncing_master"
    PROCESSING_SUPPLIERS = "processing_suppliers"


class TriggerMasterSyncMessage(BaseModel):
    """Message to trigger master sync pipeline (Bun API → Python Worker).
    
    This message is published to the Redis queue to initiate
    a full sync from the Master Google Sheet.
    
    Attributes:
        task_id: Unique identifier for tracking the sync job
        triggered_by: What initiated the sync (manual or scheduled)
        triggered_at: ISO 8601 timestamp when sync was triggered
        master_sheet_url: Optional override for the Master Sheet URL
    """
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier for tracking the sync job"
    )
    triggered_by: Literal["manual", "scheduled"] = Field(
        ...,
        description="What initiated the sync (manual or scheduled)"
    )
    triggered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp when sync was triggered"
    )
    master_sheet_url: Optional[str] = Field(
        default=None,
        description="Optional override for the Master Sheet URL"
    )
    
    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """Strip whitespace from task_id."""
        return v.strip()


class SyncStatusMessage(BaseModel):
    """Current sync status stored in Redis.
    
    This message represents the current state of the sync pipeline
    and is read by the Bun API to provide status updates to the frontend.
    
    Attributes:
        state: Current sync state
        task_id: Current running task ID (if any)
        started_at: ISO 8601 timestamp when sync started
        progress_current: Number of suppliers processed so far
        progress_total: Total number of suppliers to process
    """
    state: SyncState = Field(
        default=SyncState.IDLE,
        description="Current sync state"
    )
    task_id: Optional[str] = Field(
        default=None,
        description="Current running task ID (if any)"
    )
    started_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when sync started"
    )
    progress_current: int = Field(
        default=0,
        ge=0,
        description="Number of suppliers processed so far"
    )
    progress_total: int = Field(
        default=0,
        ge=0,
        description="Total number of suppliers to process"
    )
    
    @property
    def is_syncing(self) -> bool:
        """Whether a sync operation is currently in progress."""
        return self.state != SyncState.IDLE
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage (0-100)."""
        if self.progress_total == 0:
            return 0.0
        return (self.progress_current / self.progress_total) * 100


class SyncProgressUpdate(BaseModel):
    """Progress update during sync (for updating Redis status).
    
    Attributes:
        current: Number of suppliers processed
        total: Total number of suppliers to process
    """
    current: int = Field(
        ...,
        ge=0,
        description="Number of suppliers processed"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of suppliers to process"
    )


class SyncCompletedMessage(BaseModel):
    """Message sent when sync pipeline completes.
    
    Attributes:
        task_id: Task identifier
        status: Completion status (success, partial_success, error)
        suppliers_processed: Number of suppliers processed
        suppliers_with_errors: Number of suppliers with parsing errors
        duration_seconds: Total sync duration
        completed_at: ISO 8601 timestamp when sync completed
    """
    task_id: str = Field(
        ...,
        description="Task identifier"
    )
    status: Literal["success", "partial_success", "error"] = Field(
        ...,
        description="Completion status"
    )
    suppliers_processed: int = Field(
        default=0,
        ge=0,
        description="Number of suppliers processed"
    )
    suppliers_with_errors: int = Field(
        default=0,
        ge=0,
        description="Number of suppliers with parsing errors"
    )
    duration_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Total sync duration in seconds"
    )
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp when sync completed"
    )

