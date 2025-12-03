# Research: Refactor Ingestion-to-ML Handover

**Date:** 2025-12-03

**Feature:** 008-ml-ingestion-integration

---

## Executive Summary

This document captures technical decisions for refactoring the `python-ingestion` service to act as a data courier, delegating all parsing logic to `ml-analyze`. Research confirms the existing infrastructure already supports most requirements.

---

## Technical Decisions

### TD-1: Shared Storage Mechanism

**Decision:** Use existing Docker volume `./uploads:/shared/uploads`

**Rationale:**
- Volume already mounted in both `worker` (python-ingestion) and `ml-analyze` containers
- Path: `/shared/uploads` inside containers
- No infrastructure changes needed - only code changes to use this path consistently
- File permissions already configured (both services can read/write)

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| New dedicated volume | Clean separation | Unnecessary complexity; existing volume works | ❌ Rejected |
| Object storage (S3/MinIO) | Scalable, durable | Adds latency, complexity for local dev | ❌ Rejected |
| Redis Pub/Sub with file refs | Real-time | Overkill for file handoff; polling sufficient | ❌ Rejected |
| **Existing uploads volume** | **Already works, no changes** | **None** | ✅ **Selected** |

**Implementation Notes:**
- File path format: `/shared/uploads/{supplier_id}_{timestamp}_{original_filename}`
- Add file metadata JSON sidecar: `{filepath}.meta.json`
- Cleanup cron: Delete files older than 24 hours (new task)

---

### TD-2: Inter-Service Communication Protocol

**Decision:** HTTP REST via Docker internal network

**Rationale:**
- Both services already on `marketbel-network`
- `ml-analyze` reachable at `http://ml-analyze:8001` from `worker` container
- Existing `/analyze/file` endpoint accepts local file paths
- Simpler than queue-based approach for synchronous handoff

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Redis Queue (arq) | Async, resilient | ML service would need to poll queue; adds complexity | ❌ Rejected |
| gRPC | Type-safe, efficient | Overkill; adds protobuf dependency | ❌ Rejected |
| **HTTP REST** | **Simple, already works, debuggable** | **Slightly slower than binary** | ✅ **Selected** |

**Implementation Notes:**
- Use `httpx` async client for HTTP calls
- Timeout: 30 seconds for initial request, 30 minutes max for job completion
- Retry: 3 attempts with exponential backoff (1s, 2s, 4s)
- Health check before processing: `GET http://ml-analyze:8001/health`

---

### TD-3: Job State Synchronization

**Decision:** Unified Redis job state with phase tracking

**Rationale:**
- Both services already use Redis for job state
- Extend existing `sync:status:{task_id}` key structure
- Add `phase` field to track: `downloading`, `analyzing`, `matching`, `complete`, `failed`
- `python-ingestion` creates job; `ml-analyze` updates progress; frontend polls single source

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Separate job tables (DB) | Persistent | Query overhead; not real-time | ❌ Rejected |
| Webhook callbacks | Real-time | Adds complexity; worker may not be listening | ❌ Rejected |
| **Redis unified state** | **Fast, existing pattern, single source of truth** | **Ephemeral (acceptable)** | ✅ **Selected** |

**Implementation Notes:**
- Key: `job:{job_id}` with TTL 7 days
- Fields: `phase`, `ml_job_id`, `download_progress`, `analysis_progress`, `error`, `created_at`, `updated_at`
- `python-ingestion` writes: `phase=downloading`, `download_progress`
- `ml-analyze` writes: `phase=analyzing`, `analysis_progress`, `phase=complete`

---

### TD-4: File Download Approach for Google Sheets

**Decision:** Export as XLSX via Google Sheets API

**Rationale:**
- Google Sheets cannot be "downloaded" as-is; must export to file format
- XLSX preserves formatting, merged cells, multiple sheets
- `ml-analyze` ExcelStrategy handles XLSX parsing
- Consistent with CSV/Excel upload path

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Export as CSV | Simpler | Loses formatting, merged cells, multiple sheets | ❌ Rejected |
| JSON via API | Structured | Loses visual structure; different parsing path | ❌ Rejected |
| **Export as XLSX** | **Preserves all data; unified parsing path** | **Larger file size** | ✅ **Selected** |

**Implementation Notes:**
- Use `gspread` export_xlsx method
- Save to shared volume with `.xlsx` extension
- Set `file_type: "excel"` in ML trigger request

---

### TD-5: Legacy Pipeline Preservation

**Decision:** Feature flag per supplier + global environment variable

**Rationale:**
- Gradual rollout without big-bang migration
- Individual suppliers can be moved to ML pipeline one at a time
- Emergency rollback via global flag: `USE_ML_PROCESSING=false`
- Legacy code remains but is not executed unless flag is off

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Immediate removal | Clean codebase | No rollback; risky | ❌ Rejected |
| A/B testing | Data-driven | Complex infrastructure | ❌ Rejected |
| **Feature flag** | **Safe rollout, easy rollback** | **Temporary code branches** | ✅ **Selected** |

**Implementation Notes:**
- Supplier meta field: `use_ml_processing` (boolean, default: true)
- Environment variable: `USE_ML_PROCESSING` (default: "true")
- Logic: If global=false, use legacy. If supplier flag=false, use legacy. Otherwise, use ML.

---

### TD-6: File Cleanup Strategy

**Decision:** Arq cron task with 24-hour TTL

**Rationale:**
- Prevent disk exhaustion from accumulated files
- 24 hours provides buffer for debugging/retries
- Arq already has cron capabilities (used in Phase 6)
- Simple glob + mtime check

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Immediate deletion after processing | Saves space | No debugging capability | ❌ Rejected |
| tmpfs volume | Auto-cleanup on restart | Lose files on container restart | ❌ Rejected |
| **Scheduled cleanup task** | **Balanced; debuggable; manageable** | **Requires cron setup** | ✅ **Selected** |

**Implementation Notes:**
- New task: `cleanup_shared_files_task`
- Runs every 6 hours
- Deletes files + meta.json older than 24 hours
- Logs deleted file count to structlog

---

### TD-7: Frontend Status Display

**Decision:** Extend existing polling mechanism with phase-aware rendering

**Rationale:**
- Existing `useIngestionStatus` hook polls `/admin/sync/status`
- Add `phase` field to response
- Frontend already handles `sync_state` transitions
- Minimal frontend changes; mostly rendering logic

**Alternatives Considered:**

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| WebSocket | Real-time | Adds complexity; not needed for MVP | ❌ Rejected |
| Server-Sent Events | Simpler than WS | Still adds complexity | ❌ Rejected |
| **Polling** | **Works, simple, existing pattern** | **5s delay** | ✅ **Selected** |

**Implementation Notes:**
- New response fields: `phase`, `download_progress`, `analysis_progress`
- Phase-specific icons: Download (📥), Analyzing (🔬), Complete (✅), Failed (❌)
- Progress bar shows current phase percentage

---

## Dependencies Confirmation

| Dependency | Status | Notes |
|------------|--------|-------|
| Phase 7 (ml-analyze) | ✅ Complete | Service running, API tested |
| Phase 6 (Admin Sync) | ✅ Complete | Scheduler and UI working |
| Docker shared volume | ✅ Exists | `./uploads:/shared/uploads` |
| Docker network | ✅ Exists | `marketbel-network` |
| Redis job state | ✅ Exists | Extend existing patterns |

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| How to handle Google Sheets? | Export as XLSX to shared volume |
| What if ML service is down? | Retry 3x with backoff; then mark failed |
| How to coordinate job IDs? | python-ingestion creates ID; passes to ML; ML updates same Redis key |
| How to clean up files? | Cron task every 6 hours; 24-hour TTL |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| ML service unavailable | Health check before processing; retry logic; fallback to legacy |
| Disk full from large files | 24-hour cleanup; `MAX_FILE_SIZE_MB` environment variable |
| Network partition | Docker internal network is reliable; 30s timeout |
| Data corruption in transit | MD5 checksum in meta.json; verify before ML processing |

---

## Next Steps

1. **Create data-model.md** - Define enhanced Redis job schema
2. **Create contracts/** - Document inter-service API contracts
3. **Create quickstart.md** - Developer setup guide
4. **Update plan.md** - Full implementation plan with tasks

