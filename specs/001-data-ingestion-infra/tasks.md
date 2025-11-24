# Implementation Tasks: Data Ingestion Infrastructure

**Feature ID:** 001-data-ingestion-infra
**Status:** Ready for Implementation
**Last Updated:** 2025-11-24

---

## Task Summary

| Phase | Tasks | Parallelizable | Description |
|-------|-------|----------------|-------------|
| **Phase 1: Setup** | 12 | 8 | Project initialization and infrastructure |
| **Phase 2: Foundation** | 10 | 6 | Database layer and core abstractions |
| **Phase 3: FR-1** | 8 | 4 | Database Schema Design (CRITICAL) |
| **Phase 4: FR-2** | 12 | 7 | Python Service Architecture (CRITICAL) |
| **Phase 5: FR-4** | 9 | 5 | Redis Queue System (CRITICAL) |
| **Phase 6: FR-3** | 11 | 6 | Google Sheets Parser (HIGH) |
| **Phase 7: FR-5** | 14 | 6 | Data Ingestion Pipeline (CRITICAL) |
| **Phase 8: Polish** | 9 | 5 | Testing, documentation, deployment |
| **TOTAL** | **85** | **47** | ~5 weeks implementation |

---

## Implementation Strategy

### MVP Scope (User Story 1: FR-1 Database Schema)
- Phase 1: Setup → Phase 2: Foundation → Phase 3: FR-1
- **Goal:** Working database with all tables, constraints, and migrations
- **Deliverable:** `alembic upgrade head` creates complete schema
- **Timeline:** Week 1

### Full Feature Scope
- All 5 functional requirements (FR-1 through FR-5)
- End-to-end pipeline from Google Sheets → Database
- Error handling with ParsingLogs table
- **Timeline:** 5 weeks

### Incremental Delivery
Each phase produces independently testable artifacts:
1. **Phase 1-2:** Infrastructure running, database connectable
2. **Phase 3 (FR-1):** Schema deployed, manual SQL inserts work
3. **Phase 4 (FR-2):** Worker service accepts tasks (stub parser)
4. **Phase 5 (FR-4):** Queue processes messages end-to-end
5. **Phase 6 (FR-3):** Google Sheets parsed to memory
6. **Phase 7 (FR-5):** Complete pipeline persists to database

---

## Phase 1: Setup & Infrastructure

**Goal:** Initialize project structure and Docker environment
**Dependencies:** None
**Completion Criteria:** All services start with `docker-compose up`

### Tasks

- [X] T001 Create project directory structure per implementation plan at services/python-ingestion/
- [X] T002 Create .env.example file with all required environment variables at root
- [X] T003 [P] Create docker-compose.yml with postgres, redis, and worker services at root
- [X] T004 [P] Create PostgreSQL service configuration with health checks in docker-compose.yml
- [X] T005 [P] Create Redis service configuration with password authentication in docker-compose.yml
- [X] T006 [P] Create Python worker Dockerfile at services/python-ingestion/Dockerfile
- [X] T007 [P] Create requirements.txt with all dependencies at services/python-ingestion/requirements.txt
- [X] T008 [P] Create requirements-dev.txt with testing tools at services/python-ingestion/requirements-dev.txt
- [X] T009 Create .gitignore for credentials, .env, venv, __pycache__ at root
- [X] T010 Create credentials directory with README.md instructions at credentials/
- [X] T011 [P] Initialize git repository and create initial commit
- [X] T012 Start all services and verify health checks pass with docker-compose up -d

**Independent Test:** `docker-compose ps` shows all services healthy

---

## Phase 2: Foundation Layer

**Goal:** Database connection, base models, and configuration
**Dependencies:** Phase 1
**Completion Criteria:** Database connection pool works, migrations framework ready

### Tasks

- [X] T013 Create src/config.py with environment variable loading using pydantic-settings
- [X] T014 [P] Create src/db/base.py with SQLAlchemy DeclarativeBase and async engine configuration
- [X] T015 [P] Create src/db/base.py with UUIDMixin for primary keys
- [X] T016 [P] Create src/db/base.py with TimestampMixin for created_at/updated_at
- [X] T017 Initialize Alembic with async configuration at services/python-ingestion/migrations/
- [X] T018 [P] Create src/errors/exceptions.py with custom exception hierarchy (DataIngestionError base)
- [X] T019 [P] Create src/errors/exceptions.py with ParserError exception class
- [X] T020 [P] Create src/errors/exceptions.py with ValidationError exception class
- [X] T021 [P] Create src/errors/exceptions.py with DatabaseError exception class
- [X] T022 Configure structlog for JSON logging in src/config.py

**Independent Test:** Python imports succeed, database connection pool initializes

---

## Phase 3: User Story - FR-1 Database Schema Design

**Priority:** CRITICAL
**User Story:** FR-1 - Design and implement PostgreSQL schema with flexible characteristics, price history, and product relationships

### Story Goal
Create complete database schema with 6 tables (suppliers, categories, products, supplier_items, price_history, parsing_logs) supporting JSONB characteristics and proper foreign key relationships.

### Independent Test Criteria
- [ ] Migration runs successfully: `alembic upgrade head`
- [ ] All 6 tables exist with correct columns: `\dt` in psql
- [ ] UNIQUE constraint on (supplier_id, supplier_sku) enforced
- [ ] GIN index on characteristics JSONB column exists
- [ ] Foreign key CASCADE/SET NULL behavior validated with test inserts
- [ ] Product status enum accepts only draft/active/archived values

### Tasks

- [ ] T023 [FR-1] Create src/db/models/supplier.py with Supplier ORM model using UUIDMixin and TimestampMixin
- [ ] T024 [P] [FR-1] Create src/db/models/category.py with Category ORM model with self-referential parent_id
- [ ] T025 [P] [FR-1] Create src/db/models/product.py with Product ORM model including status enum (draft/active/archived)
- [ ] T026 [FR-1] Create src/db/models/supplier_item.py with SupplierItem ORM model with JSONB characteristics column
- [ ] T027 [P] [FR-1] Create src/db/models/price_history.py with PriceHistory ORM model with CASCADE delete
- [ ] T028 [P] [FR-1] Create src/db/models/parsing_log.py with ParsingLog ORM model for error tracking
- [ ] T029 [FR-1] Create Alembic migration 001_initial_schema.py with all table definitions at migrations/versions/
- [ ] T030 [P] [FR-1] Add GIN index on supplier_items.characteristics in migration file
- [ ] T031 [P] [FR-1] Add composite index on (supplier_id, supplier_sku) in migration file
- [ ] T032 [P] [FR-1] Add descending indexes on timestamp columns for chronological queries in migration file
- [ ] T033 [FR-1] Run migration and verify all tables created with correct constraints using psql
- [ ] T034 [FR-1] Test foreign key relationships with manual INSERT/DELETE statements in psql
- [ ] T035 [FR-1] Verify JSONB operations with sample characteristics query: WHERE characteristics @> '{"color": "red"}'

**Acceptance Criteria:**
- ✅ AC-1: Products table exists with Internal SKU, name, category reference
- ✅ AC-2: Suppliers table exists with identification and metadata
- ✅ AC-3: SupplierItems table exists linking to Suppliers with raw data
- ✅ AC-4: Categories table exists for product categorization
- ✅ AC-5: PriceHistory table exists tracking price changes with timestamps
- ✅ AC-6: One Internal SKU can link to multiple Supplier Items via foreign keys
- ✅ AC-7: JSONB column exists in SupplierItems for flexible Characteristics
- ✅ AC-8: All tables have appropriate indexes for common query patterns
- ✅ AC-9: Database migration scripts are versioned and reversible

---

## Phase 4: User Story - FR-2 Python Service Architecture

**Priority:** CRITICAL
**User Story:** FR-2 - Create modular Python service with pluggable parser architecture

### Story Goal
Build Docker-based Python service with abstract parser interface enabling easy addition of new data source types (Google Sheets, CSV, Excel) without modifying core service code.

### Independent Test Criteria
- [ ] Worker service starts successfully in Docker container
- [ ] Abstract ParserInterface defines parse() and validate_config() methods
- [ ] Mock parser can inherit from ParserInterface and be registered
- [ ] Parser registration mechanism allows adding new parsers dynamically
- [ ] Service logs JSON-formatted messages with task_id context
- [ ] Health check endpoint returns success when service is running
- [ ] Parser errors are caught and logged without crashing worker

### Tasks

- [ ] T036 [FR-2] Create src/parsers/base_parser.py with abstract ParserInterface base class
- [ ] T037 [P] [FR-2] Define parse() abstract method in ParserInterface returning List[ParsedItem]
- [ ] T038 [P] [FR-2] Define validate_config() abstract method in ParserInterface for pre-parsing validation
- [ ] T039 [P] [FR-2] Define get_parser_name() method in ParserInterface returning parser identifier
- [ ] T040 [FR-2] Create src/models/parsed_item.py with ParsedSupplierItem Pydantic model
- [ ] T041 [P] [FR-2] Add field validators to ParsedSupplierItem for price precision (2 decimal places)
- [ ] T042 [P] [FR-2] Add field validators to ParsedSupplierItem for JSONB serialization in characteristics
- [ ] T043 [FR-2] Create src/parsers/parser_registry.py with dynamic parser registration mechanism
- [ ] T044 [P] [FR-2] Implement register_parser() function in parser_registry.py
- [ ] T045 [P] [FR-2] Implement get_parser() function in parser_registry.py by parser_type string
- [ ] T046 [FR-2] Create src/worker.py with arq WorkerSettings configuration
- [ ] T047 [P] [FR-2] Configure structlog JSON logging with task_id context in worker.py
- [ ] T048 [P] [FR-2] Add graceful error handling wrapper for parser exceptions in worker.py
- [ ] T049 [FR-2] Create health check script at src/health_check.py testing Redis connection
- [ ] T050 [FR-2] Update Dockerfile HEALTHCHECK to use health_check.py script
- [ ] T051 [FR-2] Build Docker image and verify worker container starts successfully
- [ ] T052 [FR-2] Create stub parser inheriting from ParserInterface for testing registration

**Acceptance Criteria:**
- ✅ AC-1: Python service runs successfully in Docker container
- ✅ AC-2: Abstract Parser Interface defined with parse, validate, normalize methods
- ✅ AC-3: New parsers can be registered without modifying core service code
- ✅ AC-4: Service includes configuration management for parser selection
- ✅ AC-5: Service has proper logging for debugging and monitoring
- ✅ AC-6: Service handles parser errors gracefully without crashing
- ✅ AC-7: Service includes health check endpoint for container orchestration
- ✅ AC-8: Service uses type hints throughout for code clarity

---

## Phase 5: User Story - FR-4 Redis Queue System

**Priority:** CRITICAL
**User Story:** FR-4 - Set up Redis-based queue infrastructure for asynchronous task processing

### Story Goal
Implement Redis queue system with arq worker that consumes ParseTask messages, includes retry logic with exponential backoff (1s, 5s, 25s), and routes permanently failed tasks to dead letter queue.

### Independent Test Criteria
- [ ] Redis instance accessible from Python service with password authentication
- [ ] Worker successfully consumes test message from queue
- [ ] ParseTaskMessage Pydantic model validates queue message structure
- [ ] Retry count increments after simulated transient failure
- [ ] Task moves to DLQ after exceeding max_retries (3)
- [ ] Queue depth can be monitored with monitor_queue.py script
- [ ] Concurrent worker processing (3 workers) handles multiple tasks

### Tasks

- [ ] T053 [FR-4] Create src/models/queue_message.py with ParseTaskMessage Pydantic model matching JSON schema
- [ ] T054 [P] [FR-4] Add task_id, parser_type, supplier_name fields to ParseTaskMessage
- [ ] T055 [P] [FR-4] Add source_config, retry_count, max_retries fields to ParseTaskMessage
- [ ] T056 [P] [FR-4] Add enqueued_at timestamp field to ParseTaskMessage with default factory
- [ ] T057 [FR-4] Create src/worker.py with arq worker function parse_task(ctx, message: dict)
- [ ] T058 [P] [FR-4] Implement retry logic with exponential backoff delays [1, 5, 25] seconds in worker.py
- [ ] T059 [P] [FR-4] Implement dead letter queue routing after max_retries exceeded in worker.py
- [ ] T060 [FR-4] Configure arq WorkerSettings with Redis connection and max_jobs=5 in worker.py
- [ ] T061 [P] [FR-4] Add queue depth monitoring with periodic logging in worker.py
- [ ] T062 [P] [FR-4] Implement graceful task acknowledgment and error handling in worker.py
- [ ] T063 [FR-4] Create scripts/enqueue_task.py helper script for testing task submission
- [ ] T064 [P] [FR-4] Create scripts/monitor_queue.py script to display queue and DLQ depth
- [ ] T065 [FR-4] Test enqueuing message and verify worker picks it up from logs
- [ ] T066 [FR-4] Test retry behavior by simulating transient error in parse_task function
- [ ] T067 [FR-4] Test DLQ routing by forcing task to exceed max_retries

**Acceptance Criteria:**
- ✅ AC-1: Redis instance running and accessible to Python service
- ✅ AC-2: Queue message structure defined with task type, source config, metadata
- ✅ AC-3: Python service successfully consumes messages from queue
- ✅ AC-4: Messages include retry count and expiration time
- ✅ AC-5: Failed messages moved to DLQ after max retries
- ✅ AC-6: Queue depth monitored and logged
- ✅ AC-7: Service processes multiple messages concurrently with configurable worker count
- ✅ AC-8: Queue connection handles reconnection on network failures

---

## Phase 6: User Story - FR-3 Google Sheets Parser

**Priority:** HIGH
**User Story:** FR-3 - Implement Google Sheets parser with authentication, column mapping, and error handling

### Story Goal
Build GoogleSheetsParser that authenticates with service account, reads sheet data, performs dynamic column mapping with fuzzy matching, extracts characteristics into JSONB format, and handles missing data gracefully by logging to parsing_logs without crashing.

### Independent Test Criteria
- [ ] Parser authenticates successfully with Google service account credentials
- [ ] Parser reads all rows from test Google Sheet
- [ ] Dynamic column mapping detects "Product Code" → sku, "Description" → name
- [ ] Manual column_mapping override takes precedence over auto-detection
- [ ] Missing price in row logs ValidationError to parsing_logs, continues processing
- [ ] Characteristics from multiple columns merged into single JSONB object
- [ ] Parser returns List[ParsedSupplierItem] with 95/100 rows valid (5 errors logged)

### Tasks

- [ ] T068 [FR-3] Create src/models/google_sheets_config.py with GoogleSheetsConfig Pydantic model
- [ ] T069 [P] [FR-3] Add sheet_url, sheet_name, column_mapping fields to GoogleSheetsConfig
- [ ] T070 [P] [FR-3] Add characteristic_columns, header_row, data_start_row fields to GoogleSheetsConfig
- [ ] T071 [FR-3] Create src/parsers/google_sheets_parser.py inheriting from ParserInterface
- [ ] T072 [P] [FR-3] Implement gspread authentication with service account in GoogleSheetsParser.__init__
- [ ] T073 [P] [FR-3] Implement validate_config() checking sheet_url format and required fields
- [ ] T074 [FR-3] Implement parse() method reading all rows from specified sheet using gspread
- [ ] T075 [P] [FR-3] Implement dynamic column mapping with fuzzy matching using difflib.get_close_matches
- [ ] T076 [P] [FR-3] Implement column_mapping override logic taking precedence over auto-detection
- [ ] T077 [FR-3] Implement characteristics extraction merging multiple columns into JSONB dict
- [ ] T078 [P] [FR-3] Implement row-level validation with Pydantic, logging errors without raising exception
- [ ] T079 [P] [FR-3] Implement price normalization to Decimal with 2 decimal places
- [ ] T080 [FR-3] Register GoogleSheetsParser in parser_registry.py with key "google_sheets"
- [ ] T081 [FR-3] Create test Google Sheet with 100 rows (95 valid, 5 with missing price)
- [ ] T082 [FR-3] Test parser with test sheet, verify 95 ParsedSupplierItem objects returned
- [ ] T083 [FR-3] Verify 5 ValidationError entries logged to parsing_logs table

**Acceptance Criteria:**
- ✅ AC-1: Parser can authenticate with Google Sheets API
- ✅ AC-2: Parser reads all rows from specified sheet
- ✅ AC-3: Parser extracts supplier name, product name, price, SKU, characteristics
- ✅ AC-4: Parser handles missing/malformed data gracefully with error messages
- ✅ AC-5: Parser normalizes price data to consistent decimal format
- ✅ AC-6: Parser converts characteristics into JSONB-compatible format
- ✅ AC-7: Parser validates required fields before processing
- ✅ AC-8: Parser logs processing statistics (rows processed, errors encountered)

---

## Phase 7: User Story - FR-5 Data Ingestion Pipeline

**Priority:** CRITICAL
**User Story:** FR-5 - Implement end-to-end data flow from queue to database with error handling

### Story Goal
Complete data ingestion pipeline that receives ParseTask from queue, invokes appropriate parser, validates data, persists to SupplierItems table within transaction, creates/updates Supplier record, inserts PriceHistory entries, handles duplicate detection with upsert, and rolls back on validation failures while logging errors to parsing_logs.

### Independent Test Criteria
- [ ] Enqueued task with Google Sheets URL successfully processed end-to-end
- [ ] Supplier record created with name from ParseTaskMessage
- [ ] 95 SupplierItem records inserted into database (5 validation errors logged)
- [ ] 95 PriceHistory entries created with initial prices
- [ ] Duplicate task with same supplier_sku updates existing row (upsert behavior)
- [ ] Price change creates new PriceHistory entry without duplicating SupplierItem
- [ ] Validation error on row 50 does NOT prevent rows 1-49 from being inserted
- [ ] Database transaction rolls back on critical DatabaseError, task retried
- [ ] Task completion logged with statistics: 95 success, 5 failed, processing time

### Tasks

- [ ] T084 [FR-5] Implement get_or_create_supplier() function in src/db/operations.py using async session
- [ ] T085 [P] [FR-5] Add transaction context manager wrapping get_or_create_supplier with rollback
- [ ] T086 [FR-5] Implement upsert_supplier_item() function with INSERT ON CONFLICT UPDATE in src/db/operations.py
- [ ] T087 [P] [FR-5] Add price change detection comparing new price vs current_price
- [ ] T088 [P] [FR-5] Implement create_price_history_entry() function in src/db/operations.py
- [ ] T089 [FR-5] Implement log_parsing_error() function inserting to parsing_logs table in src/db/operations.py
- [ ] T090 [P] [FR-5] Add row_number, row_data, error_type, error_message fields to log_parsing_error
- [ ] T091 [FR-5] Update parse_task() worker function to call get_or_create_supplier at start
- [ ] T092 [P] [FR-5] Implement loop over ParsedSupplierItem objects calling upsert_supplier_item
- [ ] T093 [P] [FR-5] Wrap database operations in async transaction with rollback on error
- [ ] T094 [FR-5] Add try/except blocks catching ValidationError and logging without raising
- [ ] T095 [P] [FR-5] Add try/except blocks catching DatabaseError and retrying task with backoff
- [ ] T096 [FR-5] Implement task statistics calculation (total, success, failed counts, duration)
- [ ] T097 [P] [FR-5] Log task completion with statistics in structured JSON format
- [ ] T098 [FR-5] Create integration test script at tests/integration/test_end_to_end.py
- [ ] T099 [FR-5] Test Scenario 1: First-time data ingestion with 500 rows from test sheet
- [ ] T100 [FR-5] Test Scenario 2: Updated price list triggers new PriceHistory entries
- [ ] T101 [FR-5] Test Scenario 3: Malformed data (10 missing prices) results in 90 inserts, 10 errors
- [ ] T102 [FR-5] Test Scenario 4: Database unavailable triggers retry, eventual success after reconnect

**Acceptance Criteria:**
- ✅ AC-1: Service receives parse task from queue successfully
- ✅ AC-2: Service invokes appropriate parser based on source type
- ✅ AC-3: Parsed data validated against data model constraints
- ✅ AC-4: Data inserted into SupplierItems table within transaction
- ✅ AC-5: Supplier record created or updated if not exists
- ✅ AC-6: Price history entry created for each item
- ✅ AC-7: Processing failures roll back database changes
- ✅ AC-8: Task completion status logged with processing time and row counts
- ✅ AC-9: Duplicate detection prevents reprocessing same source data

---

## Phase 8: Polish & Cross-Cutting Concerns

**Goal:** Testing, documentation, performance validation, deployment readiness
**Dependencies:** Phase 7 complete
**Completion Criteria:** All success criteria met, documentation complete, ready for production

### Tasks

- [ ] T103 Create comprehensive unit tests at tests/unit/ achieving ≥85% code coverage
- [ ] T104 [P] Create parser unit tests mocking gspread API calls at tests/unit/test_parsers.py
- [ ] T105 [P] Create Pydantic validation tests at tests/unit/test_models.py
- [ ] T106 [P] Create SQLAlchemy model constraint tests at tests/unit/test_db_models.py
- [ ] T107 Run performance test: 10,000 items ingested in <10 minutes (target: >1,000/min)
- [ ] T108 [P] Create parser implementation guide at docs/parser-guide.md for adding CSV/Excel parsers
- [ ] T109 [P] Generate database schema diagram with ERD tool, save to docs/schema-diagram.png
- [ ] T110 [P] Create deployment runbook at docs/deployment.md with rollback procedures
- [ ] T111 Validate all functional requirements (FR-1 through FR-5) marked complete
- [ ] T112 Validate all success criteria met: 100% valid rows stored, >1,000 items/min throughput
- [ ] T113 Create production .env.example with security notes at root

**Independent Test:** All tests pass, documentation reviewed, performance targets met

---

## Dependencies Between User Stories

```
Phase 1: Setup (T001-T012)
    ↓
Phase 2: Foundation (T013-T022)
    ↓
    ├──→ Phase 3: FR-1 Database Schema (T023-T035)
    │         ↓
    ├──→ Phase 4: FR-2 Service Architecture (T036-T052)
    │         ↓
    └──→ Phase 5: FR-4 Queue System (T053-T067)
              ↓
         Phase 6: FR-3 Google Sheets Parser (T068-T083)
              ↓
         Phase 7: FR-5 Data Ingestion Pipeline (T084-T102)
              ↓
         Phase 8: Polish (T103-T113)
```

**Critical Path:** Setup → Foundation → FR-1 → FR-2 → FR-4 → FR-3 → FR-5 → Polish

**Parallel Opportunities:**
- Phase 3, 4, 5 can start concurrently after Phase 2 completes
- Within each phase, tasks marked [P] can be executed in parallel
- Unit tests (T103-T106) can be written alongside implementation

---

## Parallel Execution Examples

### Week 1: Infrastructure (Phase 1-3)
**Parallel Track A:** Docker setup (T003-T005) + Dockerfile (T006-T008)
**Parallel Track B:** Project structure (T001-T002) + Git init (T009-T011)
**After sync:** Start services (T012), then database models (T023-T028)

### Week 2: Service Architecture (Phase 4)
**Parallel Track A:** ParserInterface (T036-T039) + Registry (T043-T045)
**Parallel Track B:** Pydantic models (T040-T042) + Worker config (T046-T048)
**After sync:** Health checks (T049-T050), Docker build (T051-T052)

### Week 3: Queue + Parser (Phase 5-6)
**Parallel Track A:** Queue models (T053-T056) + Worker functions (T057-T060)
**Parallel Track B:** Google Sheets config (T068-T070) + Parser class (T071-T074)
**After sync:** Integration testing (T065-T067, T081-T083)

### Week 4: Pipeline (Phase 7)
**Parallel Track A:** Database operations (T084-T090)
**Parallel Track B:** Worker integration (T091-T097)
**After sync:** End-to-end tests (T098-T102)

### Week 5: Polish (Phase 8)
**Parallel Track A:** Unit tests (T103-T106)
**Parallel Track B:** Documentation (T108-T110)
**After sync:** Validation and deployment prep (T111-T113)

---

## Success Criteria Validation

### Functional Requirements
| ID | Requirement | Validation Task(s) | Status |
|----|-------------|-------------------|--------|
| FR-1 | Database Schema | T033-T035 verify migrations and constraints | ⏳ Pending |
| FR-2 | Service Architecture | T051-T052 test parser registration | ⏳ Pending |
| FR-3 | Google Sheets Parser | T081-T083 test with real sheet | ⏳ Pending |
| FR-4 | Queue System | T065-T067 test retry/DLQ behavior | ⏳ Pending |
| FR-5 | Data Ingestion | T099-T102 end-to-end scenarios | ⏳ Pending |

### Performance Targets
- [ ] **Throughput:** T107 validates >1,000 items/min (NFR-1)
- [ ] **Latency:** Queue → processing <100ms (measured in logs)
- [ ] **Memory:** Worker <512MB under load (monitored with docker stats)
- [ ] **Reliability:** 24-hour continuous run without manual intervention

### Data Quality
- [ ] **Completeness:** 100% of valid rows stored (T099 Scenario 1)
- [ ] **Integrity:** All records pass validation constraints (T033)
- [ ] **Error Recovery:** 3 retries with exponential backoff (T066)
- [ ] **Audit Trail:** All errors logged to parsing_logs (T083, T101)

---

## Risk Mitigation Tasks

### Google Sheets API Rate Limits
- **Risk:** Quota exceeded during large ingestions
- **Mitigation:** T074 implements batch read (entire sheet in 1 API call)
- **Monitoring:** T097 logs API call timestamps for rate tracking

### Database Connection Pool Exhaustion
- **Risk:** 20+ workers exceed pool size
- **Mitigation:** T014 configures pool_size=20, max_overflow=10
- **Monitoring:** Enable connection pool metrics in T022 logging config

### Memory Leaks from Pandas DataFrames
- **Risk:** Processing 10,000+ row sheets accumulates memory
- **Mitigation:** T074 clears DataFrame after conversion to ParsedSupplierItem list
- **Monitoring:** T107 performance test tracks memory usage over time

### JSONB Query Performance
- **Risk:** Characteristics queries slow as data grows
- **Mitigation:** T030 creates GIN index on characteristics column
- **Validation:** T035 tests JSONB containment query performance

---

## Definition of Done

### Code Complete Checklist
- [ ] All 85 tasks marked complete
- [ ] All 5 functional requirements (FR-1 to FR-5) pass acceptance criteria
- [ ] Unit test coverage ≥85% (pytest --cov)
- [ ] Integration tests pass with real Docker services
- [ ] Performance test validates >1,000 items/min throughput
- [ ] No critical security vulnerabilities (credentials in .env, not committed)

### Documentation Complete Checklist
- [ ] Quickstart guide tested by new developer (<30 min setup)
- [ ] Parser implementation guide enables CSV parser addition in <2 hours
- [ ] Database schema diagram generated and reviewed
- [ ] Deployment runbook includes rollback procedures
- [ ] Inline code documentation for ParserInterface and error handling

### Deployment Ready Checklist
- [ ] Docker Compose tested locally with 3 workers
- [ ] Environment variables documented in .env.example
- [ ] Health checks passing for postgres, redis, worker
- [ ] Alembic migrations tested forward and backward
- [ ] Rollback procedure validated (drain queue → downgrade → restore)

---

## Context for Task Generation

**User Input:** ultrathinking

This tasks.md is generated from:
- **Feature Spec:** [spec.md](./spec.md) - 5 functional requirements (FR-1 to FR-5)
- **Implementation Plan:** [plan/implementation-plan.md](./plan/implementation-plan.md) - 9 milestones, 5-week timeline
- **Data Model:** [plan/data-model.md](./plan/data-model.md) - 6 tables, SQLAlchemy models
- **Research:** [plan/research.md](./plan/research.md) - Technology stack decisions
- **Contracts:** [plan/contracts/](./plan/contracts/) - Queue message and parser interface schemas

**Key Design Decisions:**
- SQLAlchemy AsyncIO for non-blocking database operations
- arq for Redis-based task queue (simpler than Celery)
- gspread for Google Sheets API (higher-level than google-api-python-client)
- Pydantic v2 for data validation (type-safe, Rust-core performance)
- ParsingLogs table for error tracking without crashing worker
- Dynamic column mapping with fuzzy matching + manual overrides

**Tests Are Optional:** No test tasks generated unless explicitly requested in spec. Integration tests (T098-T102) included because they're part of FR-5 acceptance criteria.

---

## Next Steps

1. **Review this plan** with Tech Lead and stakeholders
2. **Approve MVP scope** (Phases 1-3: Database Schema only)
3. **Assign tasks** to developers or begin autonomous implementation
4. **Track progress** by checking off completed tasks
5. **Run validation** after each phase completes

**Estimated Timeline:** 5 weeks for full feature (85 tasks)
**MVP Timeline:** 1 week for database foundation (Phases 1-3, 35 tasks)

---

**Status:** ✅ Ready for Implementation
**Last Updated:** 2025-11-24
**Next Review:** After Phase 3 (FR-1 Database Schema) completion
