# Feature Plan: Admin Control Panel & Master Sync Scheduler

**Date:** 2025-12-01

**Status:** Complete

**Owner:** AI Assistant

---

## Overview

Enable administrators to manage and monitor the entire supplier data ingestion pipeline from a centralized control panel, with automated scheduled synchronization from a Master Google Sheet that serves as the single source of truth for supplier configuration.

This feature implements:
1. **Master Sheet Parser** - Reads supplier configurations from a central Google Sheet
2. **Scheduled Sync** - Automatic 8-hour interval sync with arq cron jobs
3. **Manual Sync API** - POST endpoint to trigger immediate sync
4. **Status API** - GET endpoint for real-time sync state and logs
5. **Admin UI** - React-based control panel with live updates

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility (SOLID-S):** 
  - MasterSheetIngestor: Only reads/parses master sheet
  - SyncService: Only coordinates sync pipeline
  - IngestionController: Only handles HTTP
  
- **Separation of Concerns:**
  - Bun API: HTTP endpoints, auth, queue publishing
  - Python Worker: Master sheet parsing, supplier sync, task scheduling
  - Frontend: UI rendering, polling, state display
  
- **Strong Typing:**
  - Pydantic models for all Python data structures
  - TypeBox schemas for all API payloads
  - TypeScript interfaces for React components
  
- **KISS:**
  - Polling over WebSockets (simpler, more reliable)
  - arq cron over custom scheduler (existing infrastructure)
  - Redis for ephemeral state, PostgreSQL for persistent
  
- **DRY:**
  - Reuses GoogleSheetsParser authentication
  - Reuses existing RBAC middleware
  - Shares error response patterns

**Violations/Exceptions:** None

---

## Goals

- [x] Define technical architecture for master sync pipeline
- [x] Design API contracts for sync trigger and status endpoints
- [x] Plan database and Redis data structures
- [x] Document component architecture for frontend
- [ ] Implementation (see `/speckit.tasks`)

---

## Non-Goals

- WebSocket-based real-time updates
- Sync cancellation mid-flight
- Per-supplier custom scheduling
- PDF parser implementation
- Multi-tenant support

---

## Success Metrics

- **Metric 1:** Sync trigger to first supplier parse <30 seconds
- **Metric 2:** Status API response time <200ms
- **Metric 3:** Frontend log refresh perceived latency <5 seconds
- **Metric 4:** Zero data loss on worker restart mid-sync

---

## User Stories

### Story 1: Manual Sync Trigger

**As an** Administrator
**I want** to immediately refresh all supplier data
**So that** I can respond to urgent price list updates

**Acceptance Criteria:**
- [x] "Sync Now" button visible on ingestion page
- [x] Button disabled while sync in progress
- [x] Status shows "Syncing Master Sheet" → "Processing Suppliers"
- [x] Completion returns status to "Idle"

### Story 2: Monitor Scheduled Sync

**As an** Administrator
**I want** to verify that automatic syncs run correctly
**So that** I can trust the system operates unattended

**Acceptance Criteria:**
- [x] "Next Scheduled" timestamp displays correctly
- [x] Last sync timestamp updates after each run
- [x] Log entries appear for scheduled sync activity

### Story 3: Diagnose Failures

**As an** Administrator
**I want** to identify which suppliers have sync errors
**So that** I can take corrective action

**Acceptance Criteria:**
- [x] Supplier table shows status column (Success/Error/Pending)
- [x] Log stream shows error messages with context
- [x] Error status persists until next successful sync

---

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ SyncControlCard │  │SupplierTable    │  │ LiveLogViewer   │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
│           └────────────────────┴────────────────────┘           │
│                           │ Polls every 3s                      │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Bun API (ElysiaJS)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Admin Controller                        │   │
│  │  POST /api/v1/admin/ingestion/sync  (trigger)           │   │
│  │  GET  /api/v1/admin/ingestion/status (poll)             │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────┴───────────────────────────────┐   │
│  │              Ingestion Service                           │   │
│  │  - Check/acquire sync lock (Redis)                      │   │
│  │  - Enqueue trigger_master_sync_task                     │   │
│  │  - Query status from Redis + PostgreSQL                 │   │
│  └─────────────────────────┬───────────────────────────────┘   │
└────────────────────────────┼────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │           Redis             │
              │  sync:status (state JSON)   │
              │  sync:lock (task_id)        │
              │  arq:queue:* (task queue)   │
              └──────────────┬──────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Worker (arq)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           trigger_master_sync_task                       │   │
│  │  1. Acquire sync lock                                   │   │
│  │  2. Update status: syncing_master                       │   │
│  │  3. Parse Master Sheet (MasterSheetIngestor)            │   │
│  │  4. Upsert suppliers to PostgreSQL                      │   │
│  │  5. Update status: processing_suppliers                 │   │
│  │  6. Enqueue parse_task for each active supplier         │   │
│  │  7. Release lock, status: idle                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           scheduled_sync_task (cron)                     │   │
│  │  - Runs every 8 hours (configurable)                    │   │
│  │  - Calls trigger_master_sync_task internally            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │  - suppliers    │
                    │  - parsing_logs │
                    └─────────────────┘
```

**Bun Service (API/User Logic):**

- **Responsibilities:**
  - HTTP endpoint handling for sync trigger and status
  - JWT authentication and admin role authorization
  - Redis operations for sync state and lock checking
  - Queue publishing for sync tasks

- **Endpoints:**
  - `POST /api/v1/admin/ingestion/sync` - Trigger master sync
  - `GET /api/v1/admin/ingestion/status` - Get current status

- **Data flow:**
  1. Receive request → Validate auth/role
  2. Check Redis sync lock → Return 409 if locked
  3. Publish task to Redis queue → Return 202 with task_id

**Python Service (Data Processing):**

- **Responsibilities:**
  - Master Sheet parsing and supplier discovery
  - Supplier table synchronization (create/update/deactivate)
  - Cascading parse task enqueue for active suppliers
  - Scheduled cron job execution
  - Sync state management in Redis

- **Processing logic:**
  1. Acquire exclusive sync lock
  2. Read Master Google Sheet via gspread
  3. Match rows to supplier records (name-based)
  4. Upsert suppliers, track created/updated counts
  5. Enqueue parse_task for each active supplier
  6. Update progress in Redis during processing
  7. Release lock on completion

- **Data flow:**
  ```
  Cron/Manual Trigger → MasterSheetIngestor → Supplier Sync → Parse Tasks
  ```

**Redis Queue Communication:**

- **Queue names:**
  - `arq:queue:price-ingestion-queue` (existing)
  
- **Message formats:**
  - `trigger_master_sync`: `{task_id, triggered_by, triggered_at}`
  - Status updates via direct Redis SET operations

- **Error handling:**
  - Task retry with exponential backoff (existing)
  - Sync errors logged to parsing_logs table
  - Lock auto-expires after 1 hour (safety)

**PostgreSQL Schema:**

- **Tables affected:**
  - `suppliers` - Read/write for sync
  - `supplier_items` - Read for count aggregation
  - `parsing_logs` - Read for log display

- **Migration plan:** No schema changes required

**Frontend (React + Vite + Tailwind v4.1):**

- **Components:**
  - `SyncControlCard.tsx` - Sync button, status display, timestamps
  - `LiveLogViewer.tsx` - Scrollable log list with auto-refresh
  - `SupplierStatusTable.tsx` - Sortable supplier table

- **State management:**
  - TanStack Query for server state with 3s polling
  - Local state for UI interactions (button disabled)

- **API integration:**
  - `useIngestionStatus()` - Polls GET /status
  - `useTriggerSync()` - Mutation for POST /sync

### Design System

- [x] Consulted `mcp 21st-dev/magic` for UI design elements
- [x] Collected documentation via `mcp context7`
- [x] Tailwind v4.1 CSS-first approach confirmed (no `tailwind.config.js`)

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **Initial Implementation:** 
  - arq cron for scheduling (built-in)
  - Redis SET NX for distributed lock
  - Polling for UI updates (3 second interval)

- **Scalability Path:**
  - WebSocket support if polling becomes bottleneck
  - Dedicated sync state service if complexity grows

### Data Flow

```
┌─────────┐    POST /sync     ┌──────────┐    LPUSH task    ┌─────────────┐
│ Admin   │ ─────────────────►│ Bun API  │ ────────────────►│   Redis     │
│ (React) │                   │          │                  │   Queue     │
└────┬────┘                   └──────────┘                  └──────┬──────┘
     │                                                             │
     │    GET /status (poll)                                       │ BRPOP
     │ ◄──────────────────────────────────────────────────────────►│
     │                                                             │
     │                                                             ▼
     │                                                      ┌─────────────┐
     │                                                      │   Python    │
     │    Status JSON                                       │   Worker    │
     │ ◄─────────────────── sync:status ◄──────────────────│             │
     │                                                      └──────┬──────┘
     │                                                             │
     │                                                             │ Upsert
     │                                                             ▼
     │                                                      ┌─────────────┐
     │    Supplier/Log data                                │  PostgreSQL │
     └──────────────────────────────────────────────────────│             │
                                                            └─────────────┘
```

---

## Type Safety

### TypeScript Types

See: `plan/data-model.md` for complete TypeBox schemas

Key types:
```typescript
interface IngestionStatusResponse {
  sync_state: 'idle' | 'syncing_master' | 'processing_suppliers'
  progress: { current: number; total: number } | null
  last_sync_at: string | null
  next_scheduled_at: string
  suppliers: SupplierStatus[]
  recent_logs: ParsingLogEntry[]
}
```

### Python Types

See: `plan/data-model.md` for complete Pydantic models

Key types:
```python
class SyncState(str, Enum):
    IDLE = "idle"
    SYNCING_MASTER = "syncing_master"
    PROCESSING_SUPPLIERS = "processing_suppliers"

class TriggerMasterSyncMessage(BaseModel):
    task_id: str
    triggered_by: Literal["manual", "scheduled"]
    triggered_at: str
```

---

## Testing Strategy

- **Unit Tests:**
  - MasterSheetIngestor.ingest() - Mock gspread responses
  - MasterSheetIngestor.sync_suppliers() - Test upsert logic
  - IngestionService.triggerSync() - Mock Redis lock
  - SyncControlCard rendering - Snapshot tests

- **Integration Tests:**
  - Full sync pipeline with test Google Sheet
  - API endpoint auth/authz validation
  - Redis lock acquire/release

- **E2E Tests:**
  - Manual sync trigger from UI
  - Status polling updates UI
  - Error handling and display

**Coverage Target:** ≥80% for business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Master Sheet access revoked | High | Low | Log error, display in UI, alert admin |
| Redis unavailable | Medium | Low | Return 503, frontend shows error state |
| Worker crash mid-sync | Medium | Low | Lock expires, next sync recovers |
| Rate limit on Google API | Medium | Medium | Batch reads, implement backoff |
| Concurrent sync attempts | Low | Medium | Redis distributed lock |

---

## Dependencies

- **Bun Packages:** None new (ioredis, drizzle-orm existing)
- **Python Packages:** None new (arq, gspread, SQLAlchemy existing)
- **External Services:** 
  - Google Sheets API (existing)
  - Redis (existing)
  - PostgreSQL (existing)
- **Infrastructure:**
  - New env vars: `MASTER_SHEET_URL`, `SYNC_INTERVAL_HOURS`
  - No Docker changes required

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| Phase 1 | Python: MasterSheetIngestor + sync task | 2-3 hours | Day 1 |
| Phase 2 | Python: Cron scheduler + state management | 1-2 hours | Day 1 |
| Phase 3 | Bun API: Endpoints + service | 1-2 hours | Day 1 |
| Phase 4 | Frontend: Components + page | 2-3 hours | Day 2 |
| Phase 5 | Integration testing | 1-2 hours | Day 2 |
| Phase 6 | Documentation + polish | 1 hour | Day 2 |

**Total Estimated:** 8-13 hours

---

## Open Questions

- [x] ~~Where to store sync state?~~ → Redis for ephemeral, PostgreSQL for persistent
- [x] ~~How to handle partial failures?~~ → Continue processing, log errors
- [x] ~~Polling interval?~~ → 3 seconds with visibility API pause

---

## References

- [Feature Spec](./spec.md)
- [Research](./plan/research.md)
- [Data Model](./plan/data-model.md)
- [API Contract](./plan/contracts/admin-ingestion-api.json)
- [Quickstart](./plan/quickstart.md)
- [Phase 1 Parser Infrastructure](/specs/001-data-ingestion-infra/)
- [arq Documentation](https://arq-docs.helpmanual.io/)

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
