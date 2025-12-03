# ADR-008: Courier Pattern for ML Integration

**Date:** 2025-12-03

**Status:** Accepted

**Deciders:** Development Team

**Technical Story:** Phase 8 - ML-Ingestion Integration

---

## Context

The Marketbel project completed Phase 7 with a powerful `ml-analyze` service capable of parsing complex supplier data (PDFs, Excel with merged cells) using AI-powered extraction. However, the existing `python-ingestion` service (Phase 1) contains duplicated parsing logic:

- **Regex-based column detection** for Google Sheets
- **Header detection heuristics** for CSV/Excel
- **Manual column mapping** configurations per supplier

This creates two problems:

1. **Duplication:** Similar parsing logic exists in two places, violating DRY
2. **Quality Gap:** `ml-analyze` produces better results but isn't utilized in the main ingestion pipeline
3. **Complexity:** `python-ingestion` has grown beyond its original scope

The goal is to refactor the architecture so that `python-ingestion` focuses on data acquisition while `ml-analyze` handles all parsing intelligence.

---

## Decision

**We adopt the "Courier Pattern" where `python-ingestion` acts as a data courier and delegates all parsing intelligence to `ml-analyze`.**

### Pattern Definition

The **Courier Pattern** separates data acquisition (authentication, download, transport) from data processing (parsing, matching, enrichment):

| Responsibility | Service | Examples |
|----------------|---------|----------|
| **Acquisition** | python-ingestion | OAuth, HTTP download, Google Sheets export |
| **Intelligence** | ml-analyze | PDF parsing, column detection, product matching |

### Communication Approach

| Mechanism | Use Case |
|-----------|----------|
| **Shared Volume** | File handoff (zero-copy via Docker volume) |
| **HTTP REST** | Triggering analysis, polling status |
| **Redis** | Job state management, queue tasks |

---

## Rationale

### Why Courier Pattern?

1. **Single Responsibility (SOLID-S):** Each service has one clear purpose:
   - `python-ingestion`: Get the data
   - `ml-analyze`: Understand the data

2. **Open/Closed (SOLID-O):** New data sources can be added without modifying `ml-analyze`; new parsing strategies don't require changes to `python-ingestion`.

3. **KISS:** Simple file-based handoff avoids complex streaming protocols. HTTP REST is debuggable with standard tools.

4. **Quality:** `ml-analyze` uses LLM-powered extraction which significantly outperforms regex-based approaches for messy real-world data.

### Why Shared Volume (Not Object Storage)?

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| S3/MinIO | Scalable, durable | Network latency, complexity | ❌ Rejected |
| Redis Pub/Sub | Real-time | Size limits, memory pressure | ❌ Rejected |
| HTTP File Upload | Simple | Large files problematic | ❌ Rejected |
| **Shared Volume** | **Zero-copy, simple** | **Single-host only** | ✅ Selected |

**Rationale:** For single-host deployment, shared volume is the simplest approach with no network overhead. S3 migration path exists if multi-host deployment is needed later.

### Why HTTP REST (Not Redis Queue)?

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| gRPC | Type-safe, efficient | Protobuf complexity | ❌ Rejected |
| Redis Queue | Async, existing infra | ML service would need polling | ❌ Rejected |
| **HTTP REST** | **Simple, debuggable** | **Synchronous** | ✅ Selected |

**Rationale:** HTTP REST allows immediate response with job_id; standard tooling (curl, Postman) for debugging; existing pattern in ml-analyze.

---

## Implementation

### Data Flow

```
[Admin UI] → [Bun API] → [Redis queue] → [python-ingestion]
                                              │
                                              ├── 1. Download file
                                              │      (Google Sheets → XLSX, HTTP → local)
                                              │
                                              ├── 2. Save to /shared/uploads/
                                              │      + metadata sidecar (.meta.json)
                                              │
                                              ├── 3. HTTP POST /analyze/file
                                              │      → ml-analyze
                                              │
                                              └── 4. Poll /analyze/status/{job_id}
                                                     → Update Redis job state
                                                           │
                                                           ▼
                                                    [ml-analyze]
                                                        │
                                                        ├── Read file from volume
                                                        ├── Parse (PDF/Excel)
                                                        ├── Generate embeddings
                                                        ├── Match products
                                                        └── Save to PostgreSQL
```

### Job State Phases

| Phase | Description | Actor |
|-------|-------------|-------|
| `downloading` | File being fetched from source | python-ingestion |
| `analyzing` | File being parsed by ML service | ml-analyze |
| `matching` | Products being matched | ml-analyze |
| `complete` | Successfully finished | ml-analyze |
| `failed` | Error occurred (retryable) | Either |

### Feature Flag

Legacy pipeline preserved via feature flag:

```python
# Per-supplier
supplier.meta["use_ml_processing"] = True  # default

# Global override
USE_ML_PROCESSING=false  # environment variable
```

---

## Consequences

### Positive

- **Cleaner Architecture:** Clear separation of concerns between services
- **Better Quality:** ML-powered parsing handles edge cases regex can't
- **Maintainability:** Parsing logic centralized in one service
- **Debuggability:** Files saved to shared volume for inspection
- **Gradual Migration:** Feature flag allows per-supplier rollout

### Negative

- **Added Latency:** HTTP call + file I/O adds ~100-500ms per job
- **Single Point of Failure:** If ml-analyze is down, no parsing occurs
- **Disk Space:** Temporary files require cleanup cron (24h TTL)
- **Complexity:** Two services must coordinate job state

### Mitigations

| Risk | Mitigation |
|------|------------|
| ML service down | Retry logic (3 attempts), health check, legacy fallback |
| Disk full | Cleanup cron every 6 hours, MAX_FILE_SIZE_MB limit |
| Stale status | Timeout after 30 minutes, mark as stalled |
| Data corruption | MD5 checksum in metadata sidecar |

---

## Alternatives Considered

### Alternative 1: Keep Separate Pipelines

**Approach:** Keep both legacy parsing and ML parsing, let user choose.

**Pros:**
- No migration risk
- Fallback always available

**Cons:**
- Permanent code duplication
- Maintenance burden for two pipelines
- Confusing UX

**Rejection Reason:** Violates DRY; ML pipeline is demonstrably better.

### Alternative 2: Move All Parsing to python-ingestion

**Approach:** Port ml-analyze parsing logic into python-ingestion.

**Pros:**
- Single service for all ingestion
- Simpler architecture

**Cons:**
- python-ingestion becomes monolithic
- LLM/embedding dependencies add complexity
- Violates single responsibility

**Rejection Reason:** Goes against service separation goals; would create a god service.

### Alternative 3: Event-Driven via Redis Streams

**Approach:** Use Redis Streams for async communication between services.

**Pros:**
- Fully async
- Better decoupling
- Event replay capability

**Cons:**
- More complex than HTTP
- Requires stream consumer in ml-analyze
- Overkill for request-response pattern

**Rejection Reason:** HTTP REST is simpler and sufficient for our needs.

---

## Validation

### Success Criteria

| Metric | Target | Validation Method |
|--------|--------|-------------------|
| Data Integrity | 100% files unmodified | MD5 checksum comparison |
| Processing Success | ≥95% files parsed | Job completion rate |
| End-to-End Latency | <5 min for <10MB files | E2E timing logs |
| Retry Success | 100% recoverable | Retry test scenario |
| Status Accuracy | Within 10s of actual | Frontend polling test |

### Testing Performed

- [x] Upload Excel file → observe phase transitions → verify items in DB
- [x] Stop ml-analyze → trigger upload → observe retry → restart → verify completion
- [x] Scheduled sync → multiple suppliers → verify isolated failures
- [x] Check file cleanup after 24 hours

---

## References

- Phase 8 Specification: `/specs/008-ml-ingestion-integration/spec.md`
- Phase 8 Plan: `/specs/008-ml-ingestion-integration/plan.md`
- Phase 8 Research: `/specs/008-ml-ingestion-integration/plan/research.md`
- Phase 7 ML-Analyze: `/specs/007-ml-analyze/spec.md`
- Constitution: `/.specify/memory/constitution.md` (SOLID, KISS, DRY principles)

---

## Related Decisions

- **ADR-001:** Bun + ElysiaJS for API Layer
- **Phase 7:** ML-Analyze Service (establishes intelligence layer)
- **Phase 6:** Admin Sync Scheduler (provides scheduling infrastructure)

---

**Author:** Development Team

**Last Updated:** 2025-12-03

