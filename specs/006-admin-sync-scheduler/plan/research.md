# Research: Admin Control Panel & Master Sync Scheduler

**Date:** 2025-12-01

**Status:** Complete

---

## Technology Decisions

### 1. Scheduler Implementation (arq cron)

**Decision:** Use arq's built-in `cron()` function for periodic scheduling with configurable hour interval.

**Rationale:**
- Already using arq for task queue - no new dependencies
- `cron()` supports `run_at_startup=True` for immediate first run
- `unique=True` prevents duplicate executions across multiple workers
- Simple hour-based scheduling via sets: `hour={0, 8, 16}` for 8-hour intervals

**Implementation Pattern:**
```python
from arq import cron

async def scheduled_sync_task(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Scheduled master sync job."""
    return await trigger_master_sync(ctx, scheduled=True)

# Calculate hours based on SYNC_INTERVAL_HOURS (default 8)
# 24/8 = 3 runs per day at hours {0, 8, 16}
def get_sync_hours(interval: int = 8) -> set:
    return set(range(0, 24, interval))

class WorkerSettings:
    cron_jobs = [
        cron(
            scheduled_sync_task,
            hour=get_sync_hours(int(os.getenv('SYNC_INTERVAL_HOURS', '8'))),
            minute=0,
            run_at_startup=False,  # Don't run immediately on worker start
            unique=True,  # Only one execution across workers
        ),
    ]
```

**Alternatives Considered:**
- APScheduler: Adds external dependency, more complex
- Celery Beat: Overkill, would require replacing arq
- Redis-based custom scheduler: Reinventing the wheel

---

### 2. Master Sheet Parser Design

**Decision:** Create `MasterSheetIngestor` extending existing `GoogleSheetsParser` with specialized parsing logic.

**Rationale:**
- Reuses Google Sheets authentication (Phase 1 infrastructure)
- Different output (supplier configs) vs data items
- Single responsibility: discover suppliers, not parse item data

**Implementation Pattern:**
```python
class MasterSheetIngestor:
    """Specialized ingestor for Master Google Sheet containing supplier configuration."""
    
    def __init__(self):
        self._parser = GoogleSheetsParser()  # Reuse auth
    
    async def ingest(self, master_sheet_url: str) -> List[SupplierConfig]:
        """Parse master sheet and return supplier configurations."""
        pass
    
    async def sync_suppliers(self, configs: List[SupplierConfig]) -> SyncResult:
        """Upsert suppliers to database."""
        pass
```

**Alternatives Considered:**
- Inherit from `GoogleSheetsParser`: Wrong abstraction (different output types)
- Separate service: Too much indirection for simple use case

---

### 3. Sync State Management

**Decision:** Use Redis for ephemeral sync state, PostgreSQL for persistent state.

**Rationale:**
- Sync status (idle/running/progress) changes frequently - Redis is ideal
- Last sync timestamp needs persistence - PostgreSQL
- Avoids database writes during active sync progress updates

**State Storage:**
| State | Storage | Key/Column |
|-------|---------|------------|
| Current sync status | Redis | `sync:status` (JSON) |
| Sync progress (N/M) | Redis | `sync:progress` (JSON) |
| Last successful sync | PostgreSQL | `suppliers.last_sync_at` |
| Next scheduled sync | Calculated | Based on cron schedule |

**Redis Keys:**
```
sync:status = {"state": "idle" | "syncing_master" | "processing_suppliers", "started_at": "ISO"}
sync:progress = {"current": 5, "total": 20}
sync:lock = "task-id-or-empty" (for single-execution guarantee)
```

**Alternatives Considered:**
- PostgreSQL only: Too many writes for progress updates
- Redis only: Lose last sync timestamp on restart

---

### 4. API Design for Status Endpoint

**Decision:** Single combined status endpoint returning all ingestion info.

**Rationale:**
- Reduces frontend polling complexity (1 request vs multiple)
- Efficient for 3-5 second polling interval
- Returns structured data with explicit types

**Response Structure:**
```typescript
interface IngestionStatus {
  sync_state: 'idle' | 'syncing_master' | 'processing_suppliers'
  progress: { current: number; total: number } | null
  last_sync_at: string | null
  next_scheduled_at: string
  suppliers: SupplierStatus[]
  recent_logs: ParsingLogEntry[]
}
```

**Alternatives Considered:**
- Separate endpoints for status/logs/suppliers: More network overhead
- WebSockets: Explicitly out of scope (KISS)

---

### 5. Supplier Status Derivation

**Decision:** Derive status from `parsing_logs` table, not stored column.

**Rationale:**
- Single source of truth (logs already capture success/error)
- No redundant data to keep in sync
- Efficient query with index on `(supplier_id, created_at DESC)`

**Status Logic:**
```python
def derive_supplier_status(supplier_id: UUID) -> str:
    last_log = query_latest_log(supplier_id)
    if not last_log:
        return "pending"
    if last_log.error_type == "SUCCESS":  # We'll add SUCCESS type for completion
        return "success"
    return "error"
```

**Alternatives Considered:**
- Stored `status` column: Requires trigger/sync logic, potential inconsistency
- Aggregated materialized view: Overkill for <100 suppliers

---

### 6. Concurrency Control (Single Sync Guarantee)

**Decision:** Redis distributed lock with task ID.

**Rationale:**
- Multiple workers may receive sync request simultaneously
- Lock prevents duplicate Master Sheet parses
- Task ID in lock enables "already running" response

**Implementation:**
```python
async def acquire_sync_lock(redis: ArqRedis, task_id: str) -> bool:
    """Acquire exclusive sync lock. Returns False if already held."""
    result = await redis.set("sync:lock", task_id, nx=True, ex=3600)  # 1hr TTL
    return result is not None

async def release_sync_lock(redis: ArqRedis):
    """Release sync lock."""
    await redis.delete("sync:lock")

async def get_lock_holder(redis: ArqRedis) -> Optional[str]:
    """Get task ID holding lock, or None if unlocked."""
    return await redis.get("sync:lock")
```

**Alternatives Considered:**
- PostgreSQL advisory locks: Adds database load
- arq's `unique` on regular jobs: Doesn't prevent enqueue, only dedupes

---

### 7. Frontend Polling Strategy

**Decision:** `useInterval` hook with 3-second polling, pause when tab hidden.

**Rationale:**
- 3 seconds provides responsive UX without excessive requests
- Visibility API prevents background tab resource waste
- TanStack Query refetch on window focus handles tab switches

**Implementation:**
```typescript
function useIngestionStatus() {
  const { data, refetch } = useQuery({
    queryKey: ['ingestion-status'],
    queryFn: fetchIngestionStatus,
    refetchInterval: 3000,
    refetchIntervalInBackground: false,  // Pause when hidden
  })
  return data
}
```

**Alternatives Considered:**
- 5-second polling: Noticeable lag for fast operations
- 1-second polling: Unnecessary load
- Long polling: More complex server implementation

---

### 8. Environment Variable Design

**Decision:** Single `SYNC_INTERVAL_HOURS` environment variable with sensible default.

**Rationale:**
- Simple configuration
- Default of 8 hours matches spec
- Integer hours is granular enough for this use case

**Variable:**
```bash
# Python Worker .env
SYNC_INTERVAL_HOURS=8  # Default: sync every 8 hours
MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/xxx
```

**Alternatives Considered:**
- Cron expression: More flexible but overkill
- Multiple variables (hour/minute/second): Unnecessary complexity
- Database-stored config: Over-engineering for MVP

---

## Best Practices Applied

### From Phase 1 (Python Worker)
- Use `async with session.begin()` for atomic transactions
- Log to `parsing_logs` table, don't crash worker
- Pydantic models for all queue messages
- Structured logging with structlog

### From Phase 2 (Bun API)
- TypeBox schemas for request/response validation
- Rate limiting on mutation endpoints
- Admin role check via RBAC middleware
- Error codes for specific failure types

### From Phase 3 (Frontend)
- TanStack Query for server state
- Feature-sliced component architecture
- i18n for all user-facing text
- Tailwind v4.1 CSS-first styling

---

## Dependencies Confirmed

**Python Service (no new packages):**
- arq (cron already available)
- gspread (already configured)
- SQLAlchemy (already configured)

**Bun API (no new packages):**
- ioredis (already configured)
- drizzle-orm (already configured)

**Frontend (no new packages):**
- @tanstack/react-query (already installed)
- react-router-dom (already installed)

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| How to handle partial supplier sync failures? | Continue processing, log errors, report in status |
| Where to store sync state? | Redis for ephemeral, PostgreSQL for persistent |
| How to calculate next scheduled sync? | Compute from current time + interval |
| Should we add CSV parser? | Out of scope - defer to separate feature |
| How to handle Master Sheet access revoked? | Log error, status shows "Error", admin investigates |

---

## References

- [arq cron documentation](https://arq-docs.helpmanual.io/)
- [Phase 1 Parser Infrastructure](/specs/001-data-ingestion-infra/)
- [Phase 2 API Layer](/specs/002-api-layer/)
- [Phase 3 Frontend App](/specs/003-frontend-app/)

