# Feature Specification: Refactor Ingestion Pipeline & Integrate ML Service

**Version:** 1.0.0

**Last Updated:** 2025-12-03

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** `python-ingestion` becomes purely a data fetcher/scheduler; `ml-analyze` handles all parsing and matching logic
- **Separation of Concerns:** Clear boundary between acquisition (download files) and intelligence (parse/match); services communicate via REST API and shared volume
- **Strong Typing:** Pydantic models for inter-service contracts; TypeScript schemas for frontend state transitions
- **KISS:** File handoff via shared Docker volume (no complex streaming); polling-based status updates (no WebSocket)
- **DRY:** Reuse existing arq scheduler infrastructure; leverage Phase 6 Admin UI patterns

**Compliance Statement:**

This specification adheres to all constitutional principles. The refactoring reduces complexity in `python-ingestion` while consolidating intelligence in `ml-analyze`, creating cleaner service boundaries.

---

## Overview

### Purpose

Transform the data ingestion pipeline from a monolithic parsing system into a decoupled architecture where `python-ingestion` acts as a data courier (fetching/downloading files) and delegates all parsing intelligence to the `ml-analyze` service, enabling superior data extraction quality through AI-powered processing.

### Scope

**In Scope:**

- Remove complex parsing logic (regex strategies, column mappings) from `python-ingestion`
- Configure shared Docker volume for raw file handoff between services
- Implement REST API communication from `python-ingestion` to `ml-analyze`
- Update Admin UI with ML processing toggle and multi-phase status display
- Implement failure propagation from `ml-analyze` back to `python-ingestion`
- Maintain backward compatibility for existing scheduled sync jobs

**Out of Scope:**

- Modifications to the `ml-analyze` parsing algorithms (already complete in Phase 7)
- New data source types beyond existing (Google Sheets, CSV, Excel, PDF)
- Real-time processing or WebSocket integration (continues using polling)
- Vision/image processing (remains stubbed as per Phase 7)
- Historical data migration/reprocessing

---

## Functional Requirements

### FR-1: Refactor Python-Ingestion as Data Courier

**Priority:** Critical

**Description:** Transform `python-ingestion` service to focus exclusively on data acquisition: authenticating with sources, downloading raw files, and triggering ML processing. All parsing intelligence (regex, column detection, data extraction) must be removed or delegated.

**Acceptance Criteria:**

- [ ] AC-1.1: Google Sheets parser downloads raw spreadsheet content without applying column mappings or regex extraction
- [ ] AC-1.2: CSV/Excel parsers save raw files to shared volume without transformation
- [ ] AC-1.3: URL-based sources (HTTP links) download files verbatim to shared volume
- [ ] AC-1.4: Downloaded files preserve original format (no encoding/decoding manipulation)
- [ ] AC-1.5: File metadata (source URL, supplier ID, timestamp) is recorded alongside the raw file
- [ ] AC-1.6: Service logs download success/failure but does not interpret file contents

**Dependencies:** Shared Docker volume configuration (FR-2)

### FR-2: Shared Docker Volume Configuration

**Priority:** Critical

**Description:** Create a Docker volume mounted to both `python-ingestion` and `ml-analyze` containers for zero-copy file handoff. Files downloaded by the courier are immediately accessible to the ML service.

**Acceptance Criteria:**

- [ ] AC-2.1: New Docker volume `shared-files` is defined in docker-compose.yml
- [ ] AC-2.2: Volume is mounted at `/app/shared` in both `python-ingestion` and `ml-analyze` containers
- [ ] AC-2.3: Files written by `python-ingestion` are immediately readable by `ml-analyze`
- [ ] AC-2.4: File cleanup policy exists: files older than 24 hours are automatically purged
- [ ] AC-2.5: Volume permissions allow both services read/write access
- [ ] AC-2.6: Volume size limits prevent disk exhaustion (configurable via environment variable)

**Dependencies:** None

### FR-3: Inter-Service API Communication

**Priority:** Critical

**Description:** After downloading a file, `python-ingestion` triggers `ml-analyze` via REST API, passing the file location on the shared volume. Job status and results are retrieved via polling.

**Acceptance Criteria:**

- [ ] AC-3.1: `python-ingestion` calls `POST /analyze/file` with local file path, supplier ID, and file type
- [ ] AC-3.2: Job ID returned from `ml-analyze` is stored in Redis for status tracking
- [ ] AC-3.3: `python-ingestion` polls `GET /analyze/status/{job_id}` to monitor progress
- [ ] AC-3.4: Polling interval is configurable (default: 5 seconds) with exponential backoff on errors
- [ ] AC-3.5: HTTP client includes retry logic (3 retries with exponential backoff for 5xx errors)
- [ ] AC-3.6: Connection timeout of 30 seconds prevents blocking on unresponsive ML service

**Dependencies:** FR-2 (shared volume must exist for file paths)

### FR-4: Failure Propagation and Job Status Sync

**Priority:** Critical

**Description:** When `ml-analyze` encounters parsing failures, these must be reported back to `python-ingestion` to update Redis job state, ensuring accurate status reporting to the Admin UI and enabling retry logic.

**Acceptance Criteria:**

- [ ] AC-4.1: ML job failures update corresponding Redis job state to "failed" with error details
- [ ] AC-4.2: Partial failures (some rows succeeded, some failed) are recorded with success/error counts
- [ ] AC-4.3: Error messages from ML service are logged to `parsing_logs` table with job correlation
- [ ] AC-4.4: Critical failures (service unavailable, timeout) trigger automatic retry after configurable delay
- [ ] AC-4.5: Maximum retry count (default: 3) prevents infinite retry loops
- [ ] AC-4.6: Failed jobs can be manually re-triggered via Admin UI

**Dependencies:** FR-3 (API communication must exist)

### FR-5: Multi-Phase Status Display in Admin UI

**Priority:** High

**Description:** Update the Admin Dashboard to display distinct processing phases: "Downloading" (python-ingestion fetching file), "Analyzing" (ml-analyze parsing and matching), and "Complete/Failed" (final state). Existing sync control functionality is preserved.

**Acceptance Criteria:**

- [ ] AC-5.1: Status indicator shows phase-specific icons/colors: Download (blue), Analyzing (yellow), Complete (green), Failed (red)
- [ ] AC-5.2: Progress bar displays current phase and percentage within phase
- [ ] AC-5.3: "Downloading" phase shows bytes downloaded and total file size (when available)
- [ ] AC-5.4: "Analyzing" phase shows items processed vs total items
- [ ] AC-5.5: Elapsed time is displayed for each processing job
- [ ] AC-5.6: Completed jobs show summary: items extracted, matches found, errors encountered

**Dependencies:** FR-4 (status sync must exist for accurate display)

### FR-6: ML Processing Toggle for Manual Uploads

**Priority:** High

**Description:** Add a toggle/checkbox in the supplier add modal to enable ML-based processing for manually uploaded files. When enabled, uploaded files bypass legacy parsing and go directly to `ml-analyze`.

**Acceptance Criteria:**

- [ ] AC-6.1: "Process via ML" toggle appears in the file upload section of SupplierAddModal
- [ ] AC-6.2: Toggle is enabled by default for new file uploads
- [ ] AC-6.3: When enabled, uploaded file is saved to shared volume and triggers `ml-analyze`
- [ ] AC-6.4: When disabled, uploaded file follows existing (legacy) pipeline until fully deprecated
- [ ] AC-6.5: Toggle state is persisted per supplier in database (meta.use_ml_processing field)
- [ ] AC-6.6: Batch re-processing option to migrate existing suppliers to ML pipeline

**Dependencies:** FR-2, FR-3 (volume and API must exist)

### FR-7: Maintain Scheduled Sync Compatibility

**Priority:** High

**Description:** The existing arq scheduler and Admin API hooks from Phase 6 continue to function, with scheduled syncs now routing through the new ML pipeline. No changes to cron intervals or trigger mechanisms.

**Acceptance Criteria:**

- [ ] AC-7.1: `SYNC_INTERVAL_HOURS` environment variable continues to control sync frequency
- [ ] AC-7.2: Manual sync trigger via Admin UI works identically to before
- [ ] AC-7.3: Scheduled sync downloads files and triggers ML processing automatically
- [ ] AC-7.4: Sync status in Redis accurately reflects both download and ML processing phases
- [ ] AC-7.5: Existing arq task registration pattern is preserved
- [ ] AC-7.6: No breaking changes to existing Admin API endpoints

**Dependencies:** All prior FRs (full pipeline must work)

---

## User Scenarios & Testing

### Scenario 1: Admin Manually Uploads Excel File for ML Processing

**Actor:** Admin User

**Preconditions:** User is logged in with admin role; ML service is running

**Flow:**

1. Admin navigates to Ingestion page
2. Clicks "Add Supplier" button
3. In modal, enters supplier name and drags Excel file into upload zone
4. Ensures "Process via ML" toggle is enabled (default)
5. Clicks "Upload" button
6. UI shows "Uploading..." then "Downloading" phase
7. UI transitions to "Analyzing" phase with progress bar
8. UI shows "Complete" with summary: 150 items extracted, 120 matched, 30 in review queue
9. Admin navigates to Procurement Matching page and sees items in review queue

**Expected Result:** File is processed by ML service; items appear in database with proper match status

### Scenario 2: Scheduled Sync Processes Multiple Suppliers

**Actor:** System (Scheduled Task)

**Preconditions:** Master Sheet is configured with 5 active suppliers; sync is scheduled

**Flow:**

1. 8-hour sync interval triggers `scheduled_sync_task`
2. Master Sheet is fetched and parsed (legacy behavior)
3. For each active supplier, file is downloaded to shared volume
4. ML analyze is triggered for each file
5. Status in Redis updates: "syncing_master" → "downloading_suppliers" → "analyzing" → "complete"
6. Admin viewing dashboard sees progress for each supplier
7. Errors for one supplier do not block others

**Expected Result:** All 5 suppliers are processed; failures are isolated and logged

### Scenario 3: ML Service Failure During Processing

**Actor:** Admin User

**Preconditions:** ML service is temporarily unavailable

**Flow:**

1. Admin triggers manual sync
2. Files download successfully
3. `python-ingestion` attempts to call `ml-analyze` but receives 503 error
4. Retry logic kicks in (exponential backoff)
5. After 3 retries, job is marked as "failed"
6. Admin sees "Failed" status with error: "ML service unavailable"
7. Admin clicks "Retry" button after fixing ML service
8. Processing completes successfully

**Expected Result:** Graceful failure handling; retry capability; clear error messaging

### Scenario 4: Partial Processing Success

**Actor:** System

**Preconditions:** File contains 100 rows; 90 parse correctly, 10 have data issues

**Flow:**

1. File is downloaded and ML processing begins
2. ML service processes rows, logging errors for malformed data
3. 90 items are saved to `supplier_items` table
4. 10 errors are saved to `parsing_logs` table
5. Job status shows "Complete with warnings"
6. Admin sees summary: "90/100 items processed; 10 errors"
7. Admin can view error details in Live Log Viewer

**Expected Result:** Partial success does not fail entire job; errors are visible

---

## Success Criteria

**Measurable Outcomes:**

1. **Data Integrity:** 100% of raw files are delivered unmodified to ML service (byte-for-byte identical)
2. **Processing Success Rate:** ≥95% of file downloads complete successfully (network/auth issues excluded)
3. **End-to-End Latency:** File uploaded by admin is fully processed in under 5 minutes (for files <10MB)
4. **Failure Recovery:** 100% of failed jobs can be retried without manual intervention beyond clicking "Retry"
5. **Status Accuracy:** Admin UI status matches actual processing state within 10 seconds
6. **Backward Compatibility:** Existing scheduled syncs continue working with zero configuration changes

**Qualitative Goals:**

- Admins clearly understand which phase of processing is active
- Error messages are actionable (not generic "processing failed")
- System gracefully handles ML service outages without data loss
- Transition to new pipeline is seamless for existing users

---

## Data Models

### Key Entities

**Job (Redis - Enhanced)**
- Existing job structure extended with `phase` field
- Phases: `downloading`, `analyzing`, `matching`, `complete`, `failed`
- New fields: `ml_job_id`, `download_progress`, `analysis_progress`

**Supplier (Existing, Extended)**
- New meta field: `use_ml_processing` (boolean, default: true)
- Used to toggle between legacy and ML pipeline during transition

**Shared File Metadata (New - Ephemeral)**
- File path on shared volume
- Original filename
- MIME type
- Supplier ID
- Upload timestamp
- Checksum for integrity verification

---

## Error Handling

### Service-Level Error Strategy

**Download Failures (python-ingestion):**
- Google Sheets API errors: Log and retry with fresh OAuth token
- Network timeouts: Retry up to 3 times with exponential backoff
- File too large: Reject immediately with clear error message
- Invalid URL: Fail fast without retry; log as configuration error

**ML Service Communication Errors:**
- Connection refused: Retry after 30 seconds (ML service may be starting)
- 5xx errors: Retry with exponential backoff
- 4xx errors: Fail immediately (likely bad request, log details)
- Timeout waiting for completion: Mark as "stalled" after 30 minutes

**File System Errors (Shared Volume):**
- Write permission denied: Alert admin; fail job
- Disk full: Trigger cleanup of old files; retry
- File corruption detected (checksum mismatch): Re-download and retry

---

## Assumptions

1. **ML Service Availability:** `ml-analyze` service is running and accessible at configured URL during processing
2. **Docker Volume Performance:** Shared volume I/O is not a bottleneck for typical file sizes (<100MB)
3. **Network Stability:** Internal Docker network between services is reliable
4. **File Format Support:** All uploaded files are in formats supported by ml-analyze (PDF, XLSX, CSV)
5. **Admin UI Polling:** Frontend polling is acceptable for status updates (no real-time requirement)
6. **Transition Period:** Legacy parsing code remains available (disabled by toggle) during initial rollout

---

## Dependencies & Constraints

### Dependencies

- **Phase 7 (ML-Analyze):** Must be complete and stable before integration
- **Phase 6 (Admin Sync):** Admin UI and scheduler infrastructure reused
- **Docker Compose:** Shared volume feature requires docker-compose v2+
- **Redis:** Job state management continues using existing Redis infrastructure

### Constraints

- **Raw Data Only:** `python-ingestion` must NOT modify file contents; any transformation invalidates ML processing
- **Sequential Processing:** Each file is fully downloaded before ML processing begins (no streaming)
- **Single ML Instance:** Initial deployment assumes single ml-analyze instance (horizontal scaling deferred)
- **Volume Size:** Shared volume has size constraints; large files may fail

---

## Documentation

- [ ] Update CLAUDE.md with new architecture diagram
- [ ] Update docker-compose.yml with shared volume configuration
- [ ] Add ADR: Why we separated acquisition from parsing
- [ ] Update Admin user guide: How to use ML processing toggle
- [ ] Inline code documentation for new inter-service communication

---

## Rollback Plan

**Trigger Conditions:**

- ML processing success rate < 80% (significantly worse than legacy)
- End-to-end latency > 10 minutes for average files
- Data integrity issues (items not matching source data)
- Repeated service communication failures

**Rollback Steps:**

1. Disable "Process via ML" toggle globally (set default to false)
2. Re-enable legacy parsing code paths in `python-ingestion`
3. Update Admin UI to hide ML-specific status indicators
4. Investigate issues while legacy pipeline handles traffic
5. No database migration rollback needed (uses existing tables)

---

## Exceptions & Deviations

**Deviation 1: Technical Constraints in Spec**

- **Principle Affected:** Business-focused specification (avoid HOW)
- **Justification:** User explicitly provided technical requirements (Docker volume, REST API pattern). These are constraints that affect feasibility, not implementation details to be decided later.
- **Remediation Plan:** Planning phase will elaborate on these constraints; this spec documents them as boundaries.

---

## Appendix

### References

- Phase 1 (Data Ingestion): `/specs/001-data-ingestion-infra/spec.md`
- Phase 6 (Admin Sync): `/specs/006-admin-sync-scheduler/spec.md`
- Phase 7 (ML-Analyze): `/specs/007-ml-analyze/spec.md`
- Docker Volumes Documentation: https://docs.docker.com/storage/volumes/

### Glossary

- **Courier:** Service pattern where a component only transports data without transformation
- **Shared Volume:** Docker storage mounted to multiple containers for data exchange
- **Phase:** Distinct processing stage within a multi-step job pipeline
- **Forward Compatibility:** Ability to upgrade components independently without breaking integrations

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
