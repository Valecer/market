# Feature Plan: Refactor Ingestion Pipeline & Integrate ML Service

**Date:** 2025-12-03

**Status:** Draft

**Owner:** Development Team

---

## Overview

Transform the data ingestion architecture from a monolithic parsing system into a decoupled courier pattern. `python-ingestion` downloads raw files to a shared Docker volume and triggers `ml-analyze` for intelligent parsing. This enables superior data extraction quality through AI-powered processing while maintaining backward compatibility.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility (SOLID-S):** `python-ingestion` has one job (download/schedule); `ml-analyze` has one job (parse/match). Clear separation.
- **Open/Closed (SOLID-O):** New ML pipeline extends capabilities without modifying ml-analyze internals. Legacy path preserved via feature flag.
- **Dependency Inversion (SOLID-D):** Services communicate via contracts (REST API); no direct coupling to implementation details.
- **KISS:** HTTP for inter-service calls (not gRPC/queues); polling for status (not WebSocket). Simplest viable approach.
- **Separation of Concerns:** Clear boundary between data acquisition and intelligence layers. Services communicate via defined APIs.
- **Strong Typing:** Pydantic models for all inter-service contracts; TypeScript interfaces for frontend.

**Violations/Exceptions:** 

- **Constitution Principle 8 (Redis-only communication):** This feature adds HTTP communication between services. **Justification:** Direct HTTP is appropriate for synchronous handoff where response is needed immediately. Redis queues remain for async batch processing. This is an extension, not violation.

---

## Goals

- [x] Define shared storage mechanism (researched: existing volume works)
- [ ] Implement download-only parsers in python-ingestion
- [ ] Create ML client for inter-service HTTP communication
- [ ] Add job phase tracking to Redis state
- [ ] Update Bun API to expose enhanced status endpoints
- [ ] Add multi-phase UI components to frontend
- [ ] Add file cleanup cron task
- [ ] Maintain backward compatibility via feature flags

---

## Non-Goals

- Modify ml-analyze parsing algorithms (Phase 7 complete)
- Add WebSocket for real-time updates (polling is sufficient)
- Migrate historical data (only new uploads)
- Support new file formats beyond PDF/XLSX/CSV
- Horizontal scaling of ml-analyze (single instance for now)

---

## Success Metrics

- **Data Integrity:** 100% of raw files delivered unmodified (byte-for-byte via MD5)
- **Processing Success Rate:** ≥95% download success rate
- **End-to-End Latency:** <5 minutes for files <10MB
- **Failure Recovery:** 100% of failed jobs retryable via UI
- **Status Accuracy:** UI matches actual state within 10s

---

## User Stories

### Story 1: Admin Uploads File for ML Processing

**As an** admin user  
**I want** to upload a supplier price list and have it processed by the ML service  
**So that** I get accurate product matching without manual column mapping

**Acceptance Criteria:**

- [ ] Upload dialog shows "Process via ML" toggle (default on)
- [ ] Progress shows distinct phases: Downloading → Analyzing → Complete
- [ ] Summary shows items extracted, matches found, errors
- [ ] Items appear in review queue for uncertain matches

### Story 2: Scheduled Sync Uses ML Pipeline

**As a** system administrator  
**I want** scheduled syncs to automatically use the ML pipeline  
**So that** all supplier data benefits from improved parsing

**Acceptance Criteria:**

- [ ] Scheduled sync downloads files to shared volume
- [ ] Each file triggers ML analysis automatically
- [ ] Errors for one supplier don't block others
- [ ] Status dashboard shows progress per supplier

### Story 3: Retry Failed Jobs

**As an** admin user  
**I want** to retry failed processing jobs  
**So that** I can recover from temporary failures without re-uploading

**Acceptance Criteria:**

- [ ] Failed jobs show "Retry" button
- [ ] Clicking retry restarts from download phase
- [ ] Retry count is tracked (max 3)
- [ ] Original file is reused if still available

---

## Technical Approach

### Architecture

```
┌─────────────────┐     HTTP POST      ┌─────────────────┐
│ python-ingestion│ ──────────────────► │   ml-analyze    │
│   (Courier)     │     /analyze/file   │   (Intelligence)│
└────────┬────────┘                     └────────┬────────┘
         │                                       │
         │ Download                              │ Parse/Match
         ▼                                       ▼
┌─────────────────┐                     ┌─────────────────┐
│ Shared Volume   │◄────────────────────│   PostgreSQL    │
│ /shared/uploads │  Read Files         │   (Results)     │
└─────────────────┘                     └─────────────────┘
         │                                       ▲
         │                                       │
         └───────────────────────────────────────┘
                    Job State (Redis)
```

**Python Service (Data Courier):**

- **Responsibilities:**
  - Authenticate with data sources (Google Sheets API, HTTP)
  - Download raw files to `/shared/uploads`
  - Create metadata sidecar JSON
  - Trigger ML analysis via HTTP
  - Poll ML status and update Redis
  - Schedule cleanup of old files

- **Key Files:**
  - `src/services/ml_client.py` - HTTP client for ml-analyze
  - `src/tasks/download_tasks.py` - Download + trigger logic
  - `src/tasks/cleanup_tasks.py` - File cleanup cron

**ML Service (Intelligence):**

- **Responsibilities:** (No changes - Phase 7 complete)
  - Parse files (PDF, XLSX, CSV)
  - Generate embeddings
  - Match products
  - Update database

**Bun Service (API/User Logic):**

- **Responsibilities:**
  - Proxy enhanced status to frontend
  - New endpoint: `POST /admin/jobs/:id/retry`
  - Extended response with `phase`, `download_progress`, `analysis_progress`

**Redis Job State:**

- **Key:** `job:{job_id}`
- **Fields:** `phase`, `ml_job_id`, `download_progress`, `analysis_progress`, `error`
- **TTL:** 7 days

**Frontend (React + Vite + Tailwind v4.1):**

- **Components:**
  - `JobPhaseIndicator.tsx` - Phase-aware progress display
  - Update `SyncControlCard` for multi-phase status
  - Update `SupplierAddModal` with ML toggle

### Design System

- [x] Consulted `mcp 21st-dev/magic` for UI design elements (deferred - using existing patterns)
- [x] Collected documentation via `mcp context7` (existing ml-analyze API documented)
- [x] Tailwind v4.1 CSS-first approach confirmed (no `tailwind.config.js`)

### Algorithm Choice

Following KISS principle:

- **File Handoff:** Direct file system (shared volume) - simplest approach
- **Inter-Service:** HTTP REST - debuggable, well-understood
- **Status Tracking:** Redis hash - fast, existing pattern
- **Scalability Path:** Object storage (S3) if multi-node deployment needed

### Data Flow

```
[Admin Upload] → [Bun API] → [Redis: job created] → [Worker picks up]
                                                           │
                                                           ▼
[Google Sheets API] ← authenticate ← [Worker: download_task]
         │                                    │
         │ export XLSX                        │ save file
         ▼                                    ▼
[/shared/uploads/file.xlsx]           [Redis: phase=downloading]
         │                                    │
         │                                    │ trigger ML
         ▼                                    ▼
[ml-analyze reads file] ← HTTP POST ← [Worker: ml_client]
         │                                    │
         │ parse + match                      │ poll status
         ▼                                    ▼
[PostgreSQL: supplier_items] → [Redis: phase=complete] → [Frontend polls]
```

---

## Type Safety

### Python Types (python-ingestion)

```python
# src/services/ml_client.py
from pydantic import BaseModel
from uuid import UUID
from typing import Literal

class MLAnalyzeRequest(BaseModel):
    file_url: str
    supplier_id: UUID
    file_type: Literal["pdf", "excel", "csv"]

class MLJobStatus(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    progress_percentage: int
    items_processed: int
    items_total: int
    errors: list[str]
```

### TypeScript Types (Frontend)

```typescript
// src/types/ingestion.ts
export type JobPhase = 'downloading' | 'analyzing' | 'matching' | 'complete' | 'failed';

export interface IngestionJob {
  job_id: string;
  phase: JobPhase;
  download_progress: { percentage: number; bytes_downloaded: number } | null;
  analysis_progress: { items_processed: number; items_total: number } | null;
  error: string | null;
  can_retry: boolean;
}
```

---

## Testing Strategy

- **Unit Tests:**
  - ML client HTTP methods (mock httpx)
  - Download task file operations
  - Job state updates
  - Phase transitions

- **Integration Tests:**
  - Worker → ml-analyze HTTP communication
  - Shared volume file access
  - Redis state synchronization
  - Bun API status aggregation

- **E2E Tests:**
  - Upload file → complete processing → verify database
  - Failed ML service → retry → success
  - Scheduled sync with multiple suppliers

- **Coverage Target:** ≥80% for business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ML service unavailable | High | Low | Health check + retry + legacy fallback |
| Disk full from files | Medium | Low | 24h cleanup cron + size limits |
| Network partition | Medium | Very Low | Docker internal network reliable; timeouts |
| Data corruption | High | Very Low | MD5 checksums; verify before processing |
| Legacy code conflicts | Medium | Medium | Feature flag per supplier; global override |

---

## Dependencies

- **Python Packages:** httpx, tenacity (retry logic)
- **Bun Packages:** None new (existing stack sufficient)
- **External Services:** None new (existing Ollama, Redis, PostgreSQL)
- **Infrastructure:**
  - Shared volume already exists: `./uploads:/shared/uploads`
  - Docker network already exists: `marketbel-network`
  - New env vars: `ML_ANALYZE_URL`, `USE_ML_PROCESSING`

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| Phase 1 | ML client + download tasks | 2 days | Day 2 |
| Phase 2 | Job state + sync task updates | 1 day | Day 3 |
| Phase 3 | Bun API enhancements | 1 day | Day 4 |
| Phase 4 | Frontend components | 1 day | Day 5 |
| Phase 5 | Testing + polish | 2 days | Day 7 |

**Total:** 7 days

---

## Open Questions

- [x] How to handle Google Sheets? → Export as XLSX
- [x] What if ML service is down? → Retry 3x + fallback
- [x] How to clean up files? → 24h TTL cron task
- [x] Coordinate job IDs? → Worker creates, passes to ML

---

## References

- [Research Document](./plan/research.md) - Technical decisions
- [Data Model](./plan/data-model.md) - Redis/Pydantic schemas
- [Inter-Service API Contract](./plan/contracts/inter-service-api.json)
- [Frontend API Contract](./plan/contracts/frontend-api.json)
- [Quickstart Guide](./plan/quickstart.md) - Implementation walkthrough
- [Phase 7 Spec](../007-ml-analyze/spec.md) - ML service reference
- [Phase 6 Spec](../006-admin-sync-scheduler/spec.md) - Scheduler reference

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
