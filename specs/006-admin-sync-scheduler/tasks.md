# Task List: Admin Control Panel & Master Sync Scheduler

**Epic/Feature:** [spec.md](./spec.md) | [plan.md](./plan.md)

**Sprint/Milestone:** Phase 6

**Owner:** AI Assistant

---

## Overview

This task list implements the Admin Control Panel & Master Sync Scheduler feature, organized by user stories for independent implementation and testing.

**User Stories (from spec.md):**
- **US1:** Manual Sync Trigger (Priority: Critical)
- **US2:** Monitor Scheduled Sync (Priority: High)
- **US3:** Diagnose Failures (Priority: Medium)

---

## Phase 1: Setup

**Goal:** Configure environment for new feature with no breaking changes.

**Independent Test:** Environment variables are set and services start successfully.

- [X] T001 Add MASTER_SHEET_URL and SYNC_INTERVAL_HOURS to services/python-ingestion/.env.example
- [X] T002 Add environment variables documentation to services/python-ingestion/README.md

---

## Phase 2: Foundational (Python Worker - Core Sync Pipeline)

**Goal:** Create the core sync infrastructure that all user stories depend on.

**Independent Test:** `trigger_master_sync_task` can be manually enqueued and executes without error (even with empty/mock Master Sheet).

**Dependencies:** Must complete before Phase 3-5.

### Pydantic Models

- [X] T003 [P] Create Pydantic models for Master Sheet config in services/python-ingestion/src/models/master_sheet_config.py
- [X] T004 [P] Create Pydantic models for sync messages in services/python-ingestion/src/models/sync_messages.py

### MasterSheetIngestor Service

- [X] T005 Create MasterSheetIngestor class with ingest() method in services/python-ingestion/src/services/master_sheet_ingestor.py
- [X] T006 Implement sync_suppliers() method for database upsert in services/python-ingestion/src/services/master_sheet_ingestor.py
- [X] T007 Implement column mapping and row parsing logic in services/python-ingestion/src/services/master_sheet_ingestor.py

### Redis State Management

- [X] T008 Create sync state helper functions in services/python-ingestion/src/services/sync_state.py
- [X] T009 Implement acquire_sync_lock() with Redis SET NX in services/python-ingestion/src/services/sync_state.py
- [X] T010 Implement release_sync_lock() and get_sync_status() in services/python-ingestion/src/services/sync_state.py
- [X] T011 Implement update_sync_progress() for UI feedback in services/python-ingestion/src/services/sync_state.py

### Sync Tasks

- [X] T012 Create trigger_master_sync_task arq function in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T013 Implement sync pipeline orchestration: lock → parse → upsert → enqueue in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T014 Add cascading parse_task enqueue for active suppliers in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T015 Register trigger_master_sync_task in WorkerSettings.functions in services/python-ingestion/src/worker.py

---

## Phase 3: User Story 1 - Manual Sync Trigger

**Goal:** Administrator can trigger sync from UI and see immediate status feedback.

**Independent Test:**
1. Navigate to /admin/ingestion
2. Click "Sync Now" button
3. Status changes to "Syncing Master Sheet"
4. Button becomes disabled while syncing
5. Status returns to "Idle" after completion

**Dependencies:** Phase 2 complete.

### Bun API - Types & Schemas

- [X] T016 [P] [US1] Create TypeBox schemas for ingestion types in services/bun-api/src/types/ingestion.types.ts
- [X] T017 [P] [US1] Export ingestion types from services/bun-api/src/types/ingestion.types.ts

### Bun API - Service Layer

- [X] T018 [US1] Create IngestionService class skeleton in services/bun-api/src/services/ingestion.service.ts
- [X] T019 [US1] Implement triggerSync() method with Redis lock check in services/bun-api/src/services/ingestion.service.ts
- [X] T020 [US1] Implement getStatus() method for polling in services/bun-api/src/services/ingestion.service.ts

### Bun API - Controller

- [X] T021 [US1] Add POST /api/v1/admin/ingestion/sync endpoint in services/bun-api/src/controllers/admin/index.ts
- [X] T022 [US1] Add GET /api/v1/admin/ingestion/status endpoint in services/bun-api/src/controllers/admin/index.ts
- [X] T023 [US1] Add admin role guard and rate limiting to sync endpoint in services/bun-api/src/controllers/admin/index.ts

### Frontend - Types

- [X] T024 [P] [US1] Create ingestion types in services/frontend/src/types/ingestion.ts

### Frontend - Hooks

- [X] T025 [US1] Create useIngestionStatus hook with 3s polling in services/frontend/src/hooks/useIngestionStatus.ts
- [X] T026 [US1] Create useTriggerSync mutation hook in services/frontend/src/hooks/useTriggerSync.ts
- [X] T027 [US1] Export hooks from services/frontend/src/hooks/index.ts

### Frontend - Components

- [X] T028 [US1] Create SyncControlCard component skeleton in services/frontend/src/components/admin/SyncControlCard.tsx
- [X] T029 [US1] Implement sync state display (idle/syncing_master/processing_suppliers) in services/frontend/src/components/admin/SyncControlCard.tsx
- [X] T030 [US1] Implement "Sync Now" button with loading state in services/frontend/src/components/admin/SyncControlCard.tsx
- [X] T031 [US1] Add progress display for processing_suppliers state in services/frontend/src/components/admin/SyncControlCard.tsx
- [X] T032 [US1] Export SyncControlCard from services/frontend/src/components/admin/index.ts

### Frontend - Page & Routing

- [X] T033 [US1] Create IngestionPage component in services/frontend/src/pages/admin/IngestionPage.tsx
- [X] T034 [US1] Add /admin/ingestion route in services/frontend/src/routes.tsx
- [X] T035 [US1] Add navigation link to ingestion page in services/frontend/src/components/shared/AdminLayout.tsx

### Frontend - i18n

- [X] T036 [P] [US1] Add English translations for ingestion page in services/frontend/public/locales/en/translation.json
- [X] T037 [P] [US1] Add Russian translations for ingestion page in services/frontend/public/locales/ru/translation.json

---

## Phase 4: User Story 2 - Monitor Scheduled Sync

**Goal:** Automatic syncs run every 8 hours and administrator can verify they occurred.

**Independent Test:**
1. Set SYNC_INTERVAL_HOURS=1 (for testing)
2. Verify cron job registered in worker logs
3. After 1 hour (or manual trigger), verify last_sync_at timestamp updates
4. Verify next_scheduled_at displays correctly

**Dependencies:** Phase 3 complete.

### Python Worker - Cron Job

- [X] T038 [US2] Create scheduled_sync_task cron wrapper function in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T039 [US2] Implement get_sync_hours() helper for dynamic hour calculation in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T040 [US2] Register cron job in WorkerSettings.cron_jobs in services/python-ingestion/src/worker.py
- [X] T041 [US2] Add SYNC_INTERVAL_HOURS to Settings class in services/python-ingestion/src/config.py

### Bun API - Schedule Calculation

- [X] T042 [US2] Implement calculateNextScheduledSync() helper in services/bun-api/src/services/ingestion.service.ts
- [X] T043 [US2] Add next_scheduled_at to getStatus() response in services/bun-api/src/services/ingestion.service.ts

### Frontend - Timestamp Display

- [X] T044 [US2] Add last sync timestamp display to SyncControlCard in services/frontend/src/components/admin/SyncControlCard.tsx
- [X] T045 [US2] Add next scheduled timestamp display to SyncControlCard in services/frontend/src/components/admin/SyncControlCard.tsx

---

## Phase 5: User Story 3 - Diagnose Failures

**Goal:** Administrator can identify failed suppliers and view error logs.

**Independent Test:**
1. Trigger sync with a misconfigured supplier (invalid URL)
2. Verify supplier shows "Error" status in table
3. Verify error message appears in log stream
4. Verify log entries include timestamp and supplier name

**Dependencies:** Phase 3 complete (can run in parallel with Phase 4).

### Bun API - Repository Layer

- [X] T046 [P] [US3] Create ingestion repository in services/bun-api/src/db/repositories/ingestion.repository.ts
- [X] T047 [P] [US3] Implement getSuppliersWithStatus() with items count in services/bun-api/src/db/repositories/ingestion.repository.ts
- [X] T048 [P] [US3] Implement getRecentParsingLogs() with supplier join in services/bun-api/src/db/repositories/ingestion.repository.ts
- [X] T049 [US3] Implement deriveSupplierStatus() from parsing logs in services/bun-api/src/db/repositories/ingestion.repository.ts

### Bun API - Service Integration

- [X] T050 [US3] Integrate repository methods into IngestionService.getStatus() in services/bun-api/src/services/ingestion.service.ts

### Frontend - Log Viewer Component

- [X] T051 [US3] Create LiveLogViewer component skeleton in services/frontend/src/components/admin/LiveLogViewer.tsx
- [X] T052 [US3] Implement scrollable log list with timestamp/level/message in services/frontend/src/components/admin/LiveLogViewer.tsx
- [X] T053 [US3] Add visual distinction for ERROR level logs in services/frontend/src/components/admin/LiveLogViewer.tsx
- [X] T054 [US3] Export LiveLogViewer from services/frontend/src/components/admin/index.ts

### Frontend - Supplier Table Component

- [X] T055 [US3] Create SupplierStatusTable component skeleton in services/frontend/src/components/admin/SupplierStatusTable.tsx
- [X] T056 [US3] Implement sortable columns (Name, Last Sync, Status, Items) in services/frontend/src/components/admin/SupplierStatusTable.tsx
- [X] T057 [US3] Add status color coding (success=green, error=red, pending=yellow) in services/frontend/src/components/admin/SupplierStatusTable.tsx
- [X] T058 [US3] Add inactive supplier visual distinction in services/frontend/src/components/admin/SupplierStatusTable.tsx
- [X] T059 [US3] Export SupplierStatusTable from services/frontend/src/components/admin/index.ts

### Frontend - Page Integration

- [X] T060 [US3] Integrate LiveLogViewer into IngestionPage in services/frontend/src/pages/admin/IngestionPage.tsx
- [X] T061 [US3] Integrate SupplierStatusTable into IngestionPage in services/frontend/src/pages/admin/IngestionPage.tsx
- [X] T062 [US3] Implement responsive layout for log viewer and table in services/frontend/src/pages/admin/IngestionPage.tsx

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal:** Ensure feature is production-ready with proper error handling and documentation.

**Independent Test:** Full E2E flow works with proper error messages and i18n.

### Error Handling

- [X] T063 Add SYNC_IN_PROGRESS error code to error types in services/bun-api/src/types/errors.ts
- [X] T064 Add user-friendly error messages for sync failures in frontend in services/frontend/src/pages/admin/IngestionPage.tsx

### Logging & Observability

- [X] T065 Add structured logging for sync pipeline events in services/python-ingestion/src/tasks/sync_tasks.py
- [X] T066 Add INFO-level log entries for successful sync completion in services/python-ingestion/src/tasks/sync_tasks.py

### Final Verification

- [X] T067 Verify all Pydantic models pass mypy --strict in services/python-ingestion/
- [X] T068 Verify all TypeScript types pass tsc --noEmit in services/bun-api/
- [X] T069 Verify frontend builds without errors in services/frontend/

---

## Dependencies Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational - Python Core)
    │
    ├─────────────────────────────┐
    ▼                             ▼
Phase 3 (US1: Manual Sync)    Phase 4 (US2: Scheduled) ──┐
    │                             │                       │
    ├─────────────────────────────┤                       │
    ▼                             ▼                       │
Phase 5 (US3: Diagnose)       [Can run parallel]         │
    │                                                     │
    ├─────────────────────────────────────────────────────┘
    ▼
Phase 6 (Polish)
```

---

## Parallel Execution Opportunities

### Within Phase 2:
- T003 and T004 (Pydantic models) can run in parallel

### Within Phase 3:
- T016-T017 (TypeBox schemas) can run in parallel with T024 (Frontend types)
- T036-T037 (i18n translations) can run in parallel with component implementation

### Between Phases:
- Phase 4 and Phase 5 can run in parallel after Phase 3 foundation is complete
- T046-T048 (Repository methods) can run in parallel

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)
**Phases 1-3 only (Tasks T001-T037)**

Delivers:
- Manual sync trigger via UI
- Status display (idle/syncing/processing)
- Progress indicator
- Basic page structure

Can be deployed and tested before scheduling and error diagnosis features.

### Incremental Delivery
1. **Day 1 AM:** Phase 1-2 (Setup + Python Core) - 3-4 hours
2. **Day 1 PM:** Phase 3 (Manual Sync UI) - 3-4 hours
3. **Day 2 AM:** Phase 4 (Scheduling) - 1-2 hours
4. **Day 2 PM:** Phase 5 (Error Diagnosis) - 2-3 hours
5. **Day 2 EOD:** Phase 6 (Polish) - 1 hour

**Total: 10-14 hours**

---

## Task Summary

| Phase | Description | Task Count | Parallelizable |
|-------|-------------|------------|----------------|
| Phase 1 | Setup | 2 | 0 |
| Phase 2 | Foundational (Python) | 13 | 2 |
| Phase 3 | US1: Manual Sync | 22 | 5 |
| Phase 4 | US2: Scheduled Sync | 8 | 0 |
| Phase 5 | US3: Diagnose Failures | 17 | 4 |
| Phase 6 | Polish | 7 | 0 |
| **Total** | | **69** | **11** |

### By User Story:
- **US1 (Manual Sync):** 22 tasks
- **US2 (Scheduled Sync):** 8 tasks
- **US3 (Diagnose Failures):** 17 tasks
- **Shared/Foundational:** 22 tasks

---

## Notes

- All task IDs follow the format `- [ ] TXXX [P?] [US?] Description with file path`
- `[P]` indicates parallelizable tasks (no dependencies on incomplete tasks)
- `[US1/2/3]` indicates which user story the task belongs to
- Tasks without story labels are foundational or cross-cutting
- File paths are relative to repository root
- Estimated total effort: **10-14 hours**

