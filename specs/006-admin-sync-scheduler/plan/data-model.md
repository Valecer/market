# Data Model: Admin Control Panel & Master Sync Scheduler

**Date:** 2025-12-01

**Status:** Complete

---

## Database Schema Changes

### 1. Extended Suppliers Table

No new columns required. Existing columns are sufficient:
- `meta` (JSONB): Store Master Sheet row data including `source_url`
- `source_type`: Already supports "google_sheets", "csv", "excel"
- `updated_at`: Automatically tracks last modification

**Note:** `is_active` will be stored in `meta` JSONB field as `meta.is_active`.

---

### 2. New: Sync State Table (Optional - Using Redis Instead)

Per research decision, sync state is stored in Redis for ephemeral data. No new table needed.

**Redis Keys:**
```
sync:status    -> JSON {"state": "idle", "started_at": null}
sync:progress  -> JSON {"current": 0, "total": 0}
sync:lock      -> STRING "task-id" or null
sync:last_run  -> STRING ISO timestamp
```

---

## Python Models (Pydantic)

### Master Sheet Configuration

```python
# src/models/master_sheet_config.py
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List
from enum import Enum

class SourceFormat(str, Enum):
    """Supported data source formats."""
    GOOGLE_SHEETS = "google_sheets"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"  # Noted but not parsed

class SupplierConfigRow(BaseModel):
    """Single row from Master Google Sheet."""
    supplier_name: str = Field(..., min_length=1, max_length=255)
    source_url: HttpUrl
    format: SourceFormat
    is_active: bool = Field(default=True)
    notes: Optional[str] = None

class MasterSheetConfig(BaseModel):
    """Configuration for reading the Master Sheet."""
    sheet_url: HttpUrl
    sheet_name: str = Field(default="Suppliers", min_length=1)
    header_row: int = Field(default=1, ge=1)
    data_start_row: int = Field(default=2, ge=2)

class MasterSyncResult(BaseModel):
    """Result of master sheet sync operation."""
    suppliers_created: int = 0
    suppliers_updated: int = 0
    suppliers_deactivated: int = 0
    suppliers_skipped: int = 0
    errors: List[str] = Field(default_factory=list)
```

### Queue Messages

```python
# src/models/sync_messages.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SyncState(str, Enum):
    """Sync pipeline states."""
    IDLE = "idle"
    SYNCING_MASTER = "syncing_master"
    PROCESSING_SUPPLIERS = "processing_suppliers"

class TriggerMasterSyncMessage(BaseModel):
    """Message to trigger master sync pipeline."""
    task_id: str
    triggered_by: str  # "manual" or "scheduled"
    triggered_at: str  # ISO timestamp
    master_sheet_url: Optional[str] = None  # Override default if provided

class SyncStatusMessage(BaseModel):
    """Current sync status stored in Redis."""
    state: SyncState = SyncState.IDLE
    task_id: Optional[str] = None
    started_at: Optional[str] = None
    progress_current: int = 0
    progress_total: int = 0

class SyncProgressUpdate(BaseModel):
    """Progress update during sync."""
    current: int
    total: int
```

---

## TypeScript Types (Bun API)

### TypeBox Schemas

```typescript
// src/types/ingestion.types.ts
import { Type, Static } from '@sinclair/typebox'

// ============================================
// Enums
// ============================================

export const SyncStateEnum = Type.Union([
  Type.Literal('idle'),
  Type.Literal('syncing_master'),
  Type.Literal('processing_suppliers'),
])

export const SupplierSyncStatusEnum = Type.Union([
  Type.Literal('success'),
  Type.Literal('error'),
  Type.Literal('pending'),
  Type.Literal('inactive'),
])

// ============================================
// Request Schemas
// ============================================

export const TriggerSyncRequestSchema = Type.Object({
  // No body required - triggers global sync
})

// ============================================
// Response Schemas
// ============================================

export const SyncProgressSchema = Type.Object({
  current: Type.Number(),
  total: Type.Number(),
})

export const SupplierStatusSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  name: Type.String(),
  source_type: Type.String(),
  last_sync_at: Type.Union([Type.String(), Type.Null()]),
  status: SupplierSyncStatusEnum,
  items_count: Type.Number(),
})

export const ParsingLogEntrySchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  task_id: Type.String(),
  supplier_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  supplier_name: Type.Union([Type.String(), Type.Null()]),
  error_type: Type.String(),
  error_message: Type.String(),
  row_number: Type.Union([Type.Number(), Type.Null()]),
  created_at: Type.String(),
})

export const TriggerSyncResponseSchema = Type.Object({
  task_id: Type.String(),
  status: Type.Literal('queued'),
  message: Type.String(),
})

export const IngestionStatusResponseSchema = Type.Object({
  sync_state: SyncStateEnum,
  progress: Type.Union([SyncProgressSchema, Type.Null()]),
  last_sync_at: Type.Union([Type.String(), Type.Null()]),
  next_scheduled_at: Type.String(),
  suppliers: Type.Array(SupplierStatusSchema),
  recent_logs: Type.Array(ParsingLogEntrySchema),
})

export const SyncAlreadyRunningResponseSchema = Type.Object({
  error: Type.Object({
    code: Type.Literal('SYNC_IN_PROGRESS'),
    message: Type.String(),
    current_task_id: Type.String(),
  }),
})

// ============================================
// Type Exports
// ============================================

export type SyncState = Static<typeof SyncStateEnum>
export type SupplierSyncStatus = Static<typeof SupplierSyncStatusEnum>
export type SyncProgress = Static<typeof SyncProgressSchema>
export type SupplierStatus = Static<typeof SupplierStatusSchema>
export type ParsingLogEntry = Static<typeof ParsingLogEntrySchema>
export type TriggerSyncResponse = Static<typeof TriggerSyncResponseSchema>
export type IngestionStatusResponse = Static<typeof IngestionStatusResponseSchema>
```

---

## TypeScript Types (Frontend)

### React Component Props

```typescript
// src/types/ingestion.ts

export type SyncState = 'idle' | 'syncing_master' | 'processing_suppliers'
export type SupplierSyncStatus = 'success' | 'error' | 'pending' | 'inactive'

export interface SyncProgress {
  current: number
  total: number
}

export interface SupplierStatus {
  id: string
  name: string
  source_type: string
  last_sync_at: string | null
  status: SupplierSyncStatus
  items_count: number
}

export interface ParsingLogEntry {
  id: string
  task_id: string
  supplier_id: string | null
  supplier_name: string | null
  error_type: string
  error_message: string
  row_number: number | null
  created_at: string
}

export interface IngestionStatus {
  sync_state: SyncState
  progress: SyncProgress | null
  last_sync_at: string | null
  next_scheduled_at: string
  suppliers: SupplierStatus[]
  recent_logs: ParsingLogEntry[]
}

// Component Props
export interface SyncControlCardProps {
  syncState: SyncState
  progress: SyncProgress | null
  lastSyncAt: string | null
  nextScheduledAt: string
  onSyncNow: () => void
  isSyncing: boolean
}

export interface LiveLogViewerProps {
  logs: ParsingLogEntry[]
  isLoading: boolean
}

export interface SupplierStatusTableProps {
  suppliers: SupplierStatus[]
  isLoading: boolean
}
```

---

## SQLAlchemy Query Patterns

### Get Supplier Status with Items Count

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

async def get_suppliers_with_status(session: AsyncSession):
    """Get all suppliers with items count and derived status."""
    from src.db.models import Supplier, SupplierItem, ParsingLog
    
    # Subquery for items count per supplier
    items_count_subq = (
        select(
            SupplierItem.supplier_id,
            func.count(SupplierItem.id).label('items_count')
        )
        .group_by(SupplierItem.supplier_id)
        .subquery()
    )
    
    # Subquery for latest log per supplier
    latest_log_subq = (
        select(
            ParsingLog.supplier_id,
            ParsingLog.error_type,
            func.max(ParsingLog.created_at).label('latest_log_at')
        )
        .group_by(ParsingLog.supplier_id, ParsingLog.error_type)
        .subquery()
    )
    
    # Main query
    stmt = (
        select(
            Supplier.id,
            Supplier.name,
            Supplier.source_type,
            Supplier.updated_at.label('last_sync_at'),
            func.coalesce(items_count_subq.c.items_count, 0).label('items_count'),
        )
        .outerjoin(items_count_subq, Supplier.id == items_count_subq.c.supplier_id)
        .order_by(Supplier.name)
    )
    
    result = await session.execute(stmt)
    return result.all()
```

### Get Recent Parsing Logs

```python
async def get_recent_parsing_logs(
    session: AsyncSession,
    limit: int = 50
) -> list:
    """Get recent parsing logs with supplier names."""
    from src.db.models import ParsingLog, Supplier
    
    stmt = (
        select(
            ParsingLog.id,
            ParsingLog.task_id,
            ParsingLog.supplier_id,
            Supplier.name.label('supplier_name'),
            ParsingLog.error_type,
            ParsingLog.error_message,
            ParsingLog.row_number,
            ParsingLog.created_at,
        )
        .outerjoin(Supplier, ParsingLog.supplier_id == Supplier.id)
        .order_by(ParsingLog.created_at.desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    return result.all()
```

---

## Drizzle Query Patterns (Bun API)

### Get Suppliers with Status

```typescript
// src/db/repositories/ingestion.repository.ts
import { db } from '../client'
import { suppliers, supplierItems, parsingLogs } from '../schema/schema'
import { eq, sql, desc } from 'drizzle-orm'

export async function getSuppliersWithStatus() {
  const result = await db
    .select({
      id: suppliers.id,
      name: suppliers.name,
      source_type: suppliers.sourceType,
      last_sync_at: suppliers.updatedAt,
      items_count: sql<number>`(
        SELECT COUNT(*) FROM supplier_items 
        WHERE supplier_items.supplier_id = ${suppliers.id}
      )`,
    })
    .from(suppliers)
    .orderBy(suppliers.name)

  return result
}

export async function getRecentParsingLogs(limit: number = 50) {
  const result = await db
    .select({
      id: parsingLogs.id,
      task_id: parsingLogs.taskId,
      supplier_id: parsingLogs.supplierId,
      supplier_name: suppliers.name,
      error_type: parsingLogs.errorType,
      error_message: parsingLogs.errorMessage,
      row_number: parsingLogs.rowNumber,
      created_at: parsingLogs.createdAt,
    })
    .from(parsingLogs)
    .leftJoin(suppliers, eq(parsingLogs.supplierId, suppliers.id))
    .orderBy(desc(parsingLogs.createdAt))
    .limit(limit)

  return result
}
```

---

## Redis Data Structures

### Sync Status Object

```json
{
  "state": "processing_suppliers",
  "task_id": "sync-manual-1701388800",
  "started_at": "2025-12-01T10:00:00Z",
  "progress_current": 5,
  "progress_total": 20
}
```

### Key Patterns

| Key | Type | TTL | Description |
|-----|------|-----|-------------|
| `sync:status` | String (JSON) | None | Current sync state |
| `sync:lock` | String | 3600s | Exclusive lock (task_id) |
| `sync:last_run` | String | None | ISO timestamp of last completed sync |

---

## State Machine: Sync States

```
                    ┌─────────────┐
                    │             │
         ┌──────────│    IDLE     │◄─────────────┐
         │          │             │              │
         │          └─────────────┘              │
         │                 │                     │
         │    Manual or    │                     │
         │    Scheduled    │                     │
         │    Trigger      ▼                     │
         │          ┌─────────────┐              │
         │          │   SYNCING   │              │
         │          │   MASTER    │              │
         │          └─────────────┘              │
         │                 │                     │
         │    Master       │                     │
         │    Complete     ▼                     │
         │          ┌─────────────┐              │
         │          │ PROCESSING  │──────────────┘
         │          │ SUPPLIERS   │  All Complete
         │          └─────────────┘
         │                 │
         │    Error        │
         └─────────────────┘
              (Reset)
```

---

## Validation Rules

### Master Sheet Row Validation

| Field | Rule | Error Type |
|-------|------|------------|
| supplier_name | Required, 1-255 chars | `VALIDATION_ERROR` |
| source_url | Required, valid URL | `VALIDATION_ERROR` |
| format | Must be valid enum | `VALIDATION_ERROR` |
| is_active | Boolean, defaults true | None (default) |

### Sync Trigger Validation

| Check | Error Code | HTTP Status |
|-------|------------|-------------|
| Not authenticated | `UNAUTHORIZED` | 401 |
| Not admin role | `FORBIDDEN` | 403 |
| Sync already running | `SYNC_IN_PROGRESS` | 409 |
| Redis unavailable | `REDIS_UNAVAILABLE` | 503 |

---

## Entity Relationships

```
┌─────────────────┐
│  Master Sheet   │  (External - Google Sheets)
│  - Suppliers    │
│  - Source URLs  │
└────────┬────────┘
         │ Reads
         ▼
┌─────────────────┐      ┌─────────────────┐
│    Supplier     │──────│  SupplierItem   │
│  - name         │ 1:N  │  - supplier_sku │
│  - source_type  │      │  - current_price│
│  - meta (JSONB) │      │  - product_id   │
└────────┬────────┘      └─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐
│   ParsingLog    │
│  - task_id      │
│  - error_type   │
│  - error_message│
└─────────────────┘
```

