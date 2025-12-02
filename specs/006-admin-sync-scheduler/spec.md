# Feature Specification: Admin Control Panel & Master Sync Scheduler

**Version:** 1.0.0

**Last Updated:** 2025-12-01

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Master Parser handles only sheet reading and supplier discovery; existing parsers handle data ingestion
- **Separation of Concerns:** API layer handles HTTP/authentication; Worker handles scheduling and processing
- **Strong Typing:** All queue messages and API payloads will use validated schemas
- **KISS:** Polling-based UI updates instead of WebSockets; simple cron-style scheduling
- **DRY:** Reuses existing parser infrastructure and supplier management patterns

**Compliance Statement:**

This specification adheres to all constitutional principles. Any deviations are documented in the Exceptions section below.

---

## Overview

### Purpose

Enable administrators to manage and monitor the entire supplier data ingestion pipeline from a centralized control panel, with automated scheduled synchronization from a Master Google Sheet that serves as the single source of truth for supplier configuration.

### Scope

**In Scope:**

- Master Google Sheet parsing to discover and configure suppliers
- Automated supplier table synchronization (create/update)
- Scheduled periodic sync execution (configurable interval)
- Admin-only web interface for manual sync triggering
- Real-time status monitoring with polling-based updates
- Live parsing log viewer
- Supplier status dashboard with health indicators

**Out of Scope:**

- WebSocket-based real-time updates (use polling instead)
- Sync cancellation mid-flight (deferred to future enhancement)
- Multi-tenant support (single organization assumed)
- Custom scheduling per supplier (global interval only)
- Supplier deletion from UI (manual database operation)
- PDF parser implementation (format noted but parsing deferred)

---

## User Scenarios & Testing

### Primary User

**Administrator (Admin Role):** System administrator responsible for maintaining supplier integrations and ensuring data freshness.

### User Scenario 1: Manual Sync Trigger

**Goal:** Administrator needs to immediately refresh all supplier data after receiving updated price lists.

**Flow:**
1. Administrator navigates to the Ingestion Control Panel
2. Administrator views current sync status (Idle)
3. Administrator clicks "Sync Now" button
4. System displays status change to "Syncing Master Sheet"
5. Status updates to "Processing Suppliers (X/Y)" as work progresses
6. Live log stream shows parsing activity in real-time
7. Upon completion, status returns to "Idle" and supplier table reflects new timestamps

**Acceptance Test:**
- [ ] Clicking "Sync Now" immediately initiates the sync pipeline
- [ ] Status indicator accurately reflects current pipeline stage
- [ ] Supplier table shows updated "Last Sync" timestamps after completion
- [ ] Log stream displays relevant parsing events during sync

### User Scenario 2: Monitoring Scheduled Sync

**Goal:** Administrator wants to verify that automatic syncs are running correctly overnight.

**Flow:**
1. Administrator opens the Ingestion Control Panel next morning
2. Administrator sees status is "Idle"
3. Administrator checks supplier table "Last Sync" column
4. All suppliers show timestamps from the scheduled overnight sync
5. Administrator reviews recent log entries to verify no errors

**Acceptance Test:**
- [ ] Scheduled sync runs automatically at configured interval
- [ ] Supplier timestamps reflect scheduled sync execution time
- [ ] Log entries exist for scheduled sync activity

### User Scenario 3: Diagnosing Sync Failures

**Goal:** Administrator notices a supplier shows "Error" status and needs to investigate.

**Flow:**
1. Administrator views supplier table and identifies supplier with "Error" status
2. Administrator reviews live log stream filtered to that time period
3. Administrator identifies the error type from log messages
4. Administrator takes corrective action (updates source URL, contacts supplier)
5. Administrator triggers manual sync to retry

**Acceptance Test:**
- [ ] Failed syncs clearly indicate error status in supplier table
- [ ] Log stream contains error details with timestamps
- [ ] Error status is recoverable via subsequent successful sync

### User Scenario 4: New Supplier Onboarding

**Goal:** Administrator adds a new supplier to the Master Google Sheet and verifies it appears in the system.

**Flow:**
1. Administrator adds new row to Master Google Sheet with supplier details
2. Administrator triggers "Sync Now" from control panel
3. System reads Master Sheet and discovers new supplier entry
4. New supplier appears in supplier table with "Pending" or "Success" status
5. Parsing task is automatically enqueued for the new supplier

**Acceptance Test:**
- [ ] New suppliers in Master Sheet are automatically created in database
- [ ] New supplier parsing is immediately triggered after discovery
- [ ] Supplier table reflects all suppliers from Master Sheet

---

## Functional Requirements

### FR-1: Master Sheet Parser

**Priority:** Critical

**Description:** Create a specialized parser that reads the Master Google Sheet containing the list of all suppliers and their configuration. This sheet acts as the single source of truth for which suppliers exist and where their data resides.

**Master Sheet Expected Columns:**
- Supplier Name (required) - Unique identifier for the supplier
- Source URL (required) - URL to the supplier's price list (Google Sheet, CSV endpoint)
- Format (required) - Data format: "google_sheets", "csv", "excel", "pdf"
- Active (optional) - Boolean flag, defaults to true if not present
- Notes (optional) - Administrative notes, not processed

**Acceptance Criteria:**

- [ ] AC-1: Parser successfully reads all rows from the Master Google Sheet
- [ ] AC-2: Parser extracts Supplier Name, Source URL, and Format for each row
- [ ] AC-3: Parser skips rows with missing required fields and logs warnings
- [ ] AC-4: Parser handles both header row and data rows correctly
- [ ] AC-5: Invalid format values are logged and row is skipped
- [ ] AC-6: Duplicate supplier names are detected and logged as warnings

**Dependencies:** Existing Google Sheets authentication infrastructure (Phase 1)

---

### FR-2: Supplier Table Synchronization

**Priority:** Critical

**Description:** After parsing the Master Sheet, synchronize the discovered supplier configurations with the database. Create new supplier records for previously unknown suppliers; update existing supplier records when URLs or formats change.

**Synchronization Logic:**
- Match suppliers by Name (case-insensitive)
- **New Supplier:** Insert record with discovered configuration, set status to "active"
- **Existing Supplier:** Update Source URL and Format if changed
- **Missing from Sheet:** Do NOT delete; mark as "inactive" (soft disable)

**Acceptance Criteria:**

- [ ] AC-1: New suppliers discovered in Master Sheet are created in database
- [ ] AC-2: Existing suppliers have their configuration updated when Master Sheet changes
- [ ] AC-3: Suppliers removed from Master Sheet are marked inactive, not deleted
- [ ] AC-4: Supplier creation timestamp ("created_at") is preserved on updates
- [ ] AC-5: Supplier "updated_at" timestamp reflects sync time for all touched records
- [ ] AC-6: Synchronization is atomic - either all changes apply or none

**Dependencies:** FR-1 (Master Sheet Parser)

---

### FR-3: Cascading Parse Trigger

**Priority:** Critical

**Description:** After supplier synchronization completes, automatically enqueue parsing tasks for all active suppliers. This ensures fresh data is pulled from all supplier sources whenever the Master Sheet is synced.

**Trigger Logic:**
- Queue one parsing task per active supplier
- Include supplier ID and source configuration in task payload
- Tasks execute with existing parser infrastructure (Phase 1)
- Failed individual parses do not block other suppliers

**Acceptance Criteria:**

- [ ] AC-1: All active suppliers have parsing tasks enqueued after sync
- [ ] AC-2: Inactive suppliers are skipped (no parsing tasks created)
- [ ] AC-3: Parsing tasks include correct supplier configuration
- [ ] AC-4: Task enqueue failures are logged but do not fail overall sync
- [ ] AC-5: Duplicate tasks for same supplier are prevented within single sync

**Dependencies:** FR-2 (Supplier Table Synchronization), Phase 1 Parser Infrastructure

---

### FR-4: Scheduled Automatic Sync

**Priority:** High

**Description:** Implement automatic periodic execution of the Master Sync Pipeline. The system runs unattended, ensuring supplier data stays fresh without manual intervention.

**Scheduling Behavior:**
- Default interval: 8 hours
- Configurable via environment variable `SYNC_INTERVAL_HOURS`
- Schedule starts from worker startup, not fixed clock times
- Missed schedules (worker downtime) do not "catch up" - next run at normal interval
- Only one sync runs at a time (skip if previous still running)

**Acceptance Criteria:**

- [ ] AC-1: Sync pipeline executes automatically at configured interval
- [ ] AC-2: Default interval is 8 hours when environment variable not set
- [ ] AC-3: `SYNC_INTERVAL_HOURS` environment variable changes interval
- [ ] AC-4: Concurrent sync requests are prevented (single execution guarantee)
- [ ] AC-5: Scheduler logs each scheduled execution with timestamp
- [ ] AC-6: Worker restart resets schedule countdown

**Dependencies:** FR-1, FR-2, FR-3 (Complete Sync Pipeline)

---

### FR-5: Manual Sync Trigger API

**Priority:** High

**Description:** Expose an API endpoint that allows administrators to manually trigger the Master Sync Pipeline on demand, independent of the automatic schedule.

**API Behavior:**
- Requires authentication with admin role
- Returns immediately after queueing (does not wait for completion)
- Response includes job ID for status tracking
- Rejects request if sync already in progress

**Acceptance Criteria:**

- [ ] AC-1: Authenticated admin users can trigger sync via API
- [ ] AC-2: Non-admin users receive authorization error
- [ ] AC-3: Unauthenticated requests receive authentication error
- [ ] AC-4: Successful trigger returns job identifier
- [ ] AC-5: Request during active sync returns "already running" status
- [ ] AC-6: API response time is under 500ms (queues work, doesn't execute)

**Dependencies:** Phase 2 Authentication System, FR-1-3 (Sync Pipeline)

---

### FR-6: Sync Status API

**Priority:** High

**Description:** Provide an API endpoint for querying the current state of the sync pipeline, including global status, progress information, and recent log entries.

**Status Information Returned:**
- Global state: "idle", "syncing_master", "processing_suppliers"
- Progress: Current/Total supplier count when processing
- Last sync timestamp
- Next scheduled sync timestamp
- Recent parsing log entries (last 50)

**Acceptance Criteria:**

- [ ] AC-1: API returns current sync state accurately
- [ ] AC-2: Progress counter updates as suppliers are processed
- [ ] AC-3: Last sync timestamp reflects most recent completed sync
- [ ] AC-4: Next scheduled timestamp is calculated correctly
- [ ] AC-5: Log entries include timestamp, level, message, and supplier context
- [ ] AC-6: API requires admin authentication
- [ ] AC-7: Response time under 200ms for status queries

**Dependencies:** Phase 2 Authentication System, FR-4 (Scheduler)

---

### FR-7: Admin Ingestion Control Panel

**Priority:** High

**Description:** Create a dedicated administrative interface for monitoring and controlling the data ingestion pipeline. This "cockpit" provides visibility into sync status, supplier health, and system activity.

**Interface Elements:**

**Status Section:**
- Current sync state indicator with visual distinction (idle/active/error)
- Progress display when sync is active
- Last sync and next scheduled sync timestamps

**Controls Section:**
- "Sync Now" button to trigger manual sync
- Button disabled state when sync is in progress

**Supplier Table:**
- List of all suppliers with sortable columns
- Columns: Name, Last Sync Time, Status (Success/Error/Pending), Items Count
- Visual indicators for status (color coding)

**Live Log Stream:**
- Display last 50 parsing log entries
- Auto-refresh every 3-5 seconds
- Log entry format: timestamp, level, message
- Optional: supplier name context when available

**Acceptance Criteria:**

- [ ] AC-1: Page is accessible only to authenticated admin users
- [ ] AC-2: Status section accurately reflects current pipeline state
- [ ] AC-3: "Sync Now" button triggers sync and updates UI state
- [ ] AC-4: Supplier table displays all known suppliers
- [ ] AC-5: Log stream auto-refreshes without full page reload
- [ ] AC-6: UI is responsive and works on desktop browsers
- [ ] AC-7: Error states are clearly indicated with appropriate messaging

**Dependencies:** FR-5 (Trigger API), FR-6 (Status API), Phase 3 Frontend Infrastructure

---

### FR-8: Supplier Status Tracking

**Priority:** Medium

**Description:** Track and display the sync status for individual suppliers, enabling administrators to quickly identify which suppliers have issues.

**Status Values:**
- **Success:** Last parse completed without errors
- **Error:** Last parse encountered errors
- **Pending:** Never synced or sync in progress
- **Inactive:** Removed from Master Sheet (soft disabled)

**Status Determination:**
- Based on most recent parsing_log entry for each supplier
- Error status when any ERROR level log exists for last parse session
- Success status when parse completes without errors
- Pending status for new suppliers or active parsing

**Acceptance Criteria:**

- [ ] AC-1: Each supplier displays correct current status
- [ ] AC-2: Status updates after each sync cycle completes
- [ ] AC-3: Error status persists until next successful sync
- [ ] AC-4: Inactive suppliers are visually distinguished
- [ ] AC-5: Status values are queryable via API

**Dependencies:** FR-2 (Supplier Sync), Phase 1 parsing_logs table

---

## Non-Functional Requirements

### NFR-1: Performance

- Master Sheet parsing completes within 30 seconds for up to 100 suppliers
- Status API responds in under 200ms
- Log stream query returns within 500ms for 50 entries
- Supplier table loads within 1 second for up to 100 suppliers

### NFR-2: Reliability

- Scheduled sync runs with 99.9% reliability when worker is healthy
- Failed individual supplier parses do not block overall sync pipeline
- Worker crashes during sync allow clean restart and retry
- Database transactions ensure atomic state changes

### NFR-3: Security

- Admin endpoints require valid authentication token
- Admin role authorization enforced at API layer
- Google credentials stored securely, never exposed in logs
- Audit trail of sync trigger events (who, when)

### NFR-4: Observability

- All sync operations logged with structured format
- Error conditions include actionable context
- Sync duration metrics captured for each run
- Queue depth and processing time observable

---

## Success Criteria

1. **Operational Efficiency:** Administrators spend less than 5 minutes per day on supplier data management tasks (down from manual process)

2. **Data Freshness:** Supplier price data is never more than 9 hours old during normal operation (8-hour sync + 1-hour processing buffer)

3. **System Visibility:** Administrators can determine the current sync status and recent activity within 10 seconds of opening the control panel

4. **Error Detection:** Failed supplier syncs are identified within one sync cycle, with clear error indication in the UI

5. **Automation Success Rate:** 95% or more of scheduled syncs complete successfully without manual intervention

6. **Onboarding Speed:** New suppliers added to Master Sheet appear in the system within 1 sync cycle (maximum 8 hours, or immediately with manual sync)

7. **User Satisfaction:** Administrators can complete common tasks (trigger sync, check status, identify errors) without consulting documentation

---

## Key Entities

### Existing Entities (Referenced)

- **Supplier:** Existing table from Phase 1, extended with status tracking
- **SupplierItem:** Raw supplier data, populated by existing parsers
- **ParsingLog:** Error and activity logging, used for log stream display

### New/Extended Entity Attributes

**Supplier (Extended):**
- `source_format`: Type of data source (google_sheets, csv, excel, pdf)
- `is_active`: Boolean flag for soft-disable functionality
- `last_sync_at`: Timestamp of last successful sync completion

---

## Assumptions

1. The Master Google Sheet structure is stable and follows the expected column layout
2. Supplier names in the Master Sheet are unique identifiers
3. The existing Google Sheets authentication (Phase 1) works for the Master Sheet
4. A single global sync interval is sufficient (no per-supplier scheduling needed)
5. 50 log entries provide sufficient visibility for typical debugging
6. PDF format suppliers are noted but actual parsing is handled separately
7. The admin user base is small (single-digit administrators)
8. Browser compatibility: Modern browsers (Chrome, Firefox, Safari, Edge - latest 2 versions)

---

## Appendix

### Master Sheet Structure Example

| Supplier Name | Source URL | Format | Active | Notes |
|---------------|------------|--------|--------|-------|
| Acme Corp | https://docs.google.com/spreadsheets/d/xxx | google_sheets | TRUE | Main supplier |
| Beta Inc | https://example.com/prices.csv | csv | TRUE | Updates weekly |
| Gamma LLC | https://docs.google.com/spreadsheets/d/yyy | google_sheets | FALSE | On hold |

### Glossary

- **Master Sheet:** The central Google Spreadsheet containing the list of all supplier configurations
- **Sync Pipeline:** The complete process: parse master → sync suppliers → trigger parses
- **Cascade:** Automatic triggering of subsequent operations (supplier parses after master sync)
- **Polling:** Periodic client-side requests to check for updates (vs. server-push)

---

**Approval:**

- [ ] Tech Lead: _______________ - ____
- [ ] Product: _______________ - ____
- [ ] QA: _______________ - ____
