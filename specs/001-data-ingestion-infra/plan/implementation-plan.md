# Implementation Plan: Data Ingestion Infrastructure

**Feature ID:** 001-data-ingestion-infra  
**Date Created:** 2025-11-23  
**Status:** Ready for Implementation  
**Branch:** 001-data-ingestion-infra

---

## Executive Summary

This implementation plan defines the technical approach for building a foundational Data Ingestion Infrastructure that will:

1. **Ingest** supplier price list data from multiple sources (starting with Google Sheets)
2. **Normalize** and validate data using a pluggable parser architecture
3. **Store** structured data in PostgreSQL with flexible JSONB characteristics
4. **Process** tasks asynchronously via Redis-based queue
5. **Track** price history and parsing errors for data quality monitoring

**Architecture:** Python worker service + PostgreSQL 16 + Redis 7, orchestrated via Docker Compose

**Out of Scope:** User API (Bun), machine learning matching, frontend components

---

## Constitution Check

### ✅ Alignment with Project Principles

Based on the constitution analysis (see `.specify/memory/constitution.md` if available):

- **Modularity:** Parser interface enables easy addition of new data sources without core changes
- **Data Integrity:** Strong validation at application (Pydantic) and database (constraints) levels
- **Observability:** Structured logging to `parsing_logs` table for debugging and monitoring
- **Scalability:** Queue-based architecture supports horizontal scaling
- **Resilience:** Retry logic with dead letter queue prevents data loss on transient failures

### ⚠️ Gate Checks

**Required Approvals:**
- [x] Tech Lead: Schema review and ORM architecture
- [x] DevOps: Docker configuration and deployment strategy
- [ ] Security: Credentials management and database access controls

**Technical Gates:**
- [ ] Database schema passes migration validation
- [ ] Parser interface contract reviewed
- [ ] Error handling strategy approved
- [ ] Performance requirements validated (>1,000 items/min)

---

## Phase 0: Research & Technical Decisions ✅

**Status:** Complete  
**Document:** [research.md](./research.md)

### Key Decisions Made:

1. **SQLAlchemy AsyncIO** for ORM (better concurrency than sync)
2. **arq** for task queue (native asyncio, simpler than Celery)
3. **gspread** for Google Sheets (higher-level API than google-api-python-client)
4. **Pydantic v2** for data validation (type-safe, fast)
5. **Alembic** for migrations (SQLAlchemy standard)
6. **Dynamic column mapping** with fuzzy matching + manual overrides
7. **ParsingLogs table** for error tracking without crashing worker
8. **Product status enum** (draft/active/archived) for lifecycle management

### Technology Stack:

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Database | PostgreSQL | 16 | JSONB support, mature async drivers |
| Cache/Queue | Redis | 7-alpine | Lightweight, proven reliability |
| Runtime | Python | 3.12 | Performance improvements, modern features |
| ORM | SQLAlchemy | 2.0+ async | Mature async support, migration tooling |
| Task Queue | arq | latest | Native asyncio, Redis-optimized |
| Data Processing | pandas | 2.x | Industry standard for data manipulation |
| Validation | pydantic | 2.x | Type safety, Rust-core performance |
| Sheets API | gspread | 6.x | Simplified Sheets operations |

---

## Phase 1: Design & Contracts ✅

**Status:** Complete  
**Documents:** [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

### Database Schema

**Core Tables:**
- `suppliers` - External data sources
- `categories` - Product hierarchy (self-referential)
- `products` - Internal unified catalog with status (draft/active/archived)
- `supplier_items` - Raw supplier data with JSONB characteristics
- `price_history` - Time-series price tracking
- `parsing_logs` - **NEW:** Structured error logging

**Key Relationships:**
- One Supplier → Many SupplierItems (CASCADE delete)
- One Product → Many SupplierItems (SET NULL on delete)
- One SupplierItem → Many PriceHistory entries (CASCADE delete)

**Indexes:**
- GIN index on `supplier_items.characteristics` for JSONB queries
- Composite index on `(supplier_id, supplier_sku)` for uniqueness
- Descending indexes on timestamps for chronological queries

### Data Models

**SQLAlchemy ORM:**
- Full async models with type hints
- Mixins for UUID primary keys and timestamps
- Proper relationship configurations with cascade rules

**Pydantic Validation:**
- `ParsedSupplierItem` - Validates parsed data before DB insert
- `ParseTaskMessage` - Queue message schema with retry logic
- `GoogleSheetsConfig` - Parser-specific configuration

### API Contracts (JSON Schema)

1. **queue-message.schema.json** - Parse task message format
2. **parser-interface.schema.json** - Standard parser contract
3. **task-result.schema.json** - Processing result format

### Documentation

- **quickstart.md** - Complete setup guide with examples
- Includes Docker Compose configuration
- Sample scripts for enqueueing tasks and monitoring
- Troubleshooting section for common issues

---

## Implementation Roadmap

### Milestone 1: Infrastructure Setup (Week 1)

**Deliverables:**
- [ ] Docker Compose configuration
- [ ] PostgreSQL service with health checks
- [ ] Redis service with password authentication
- [ ] Python worker Dockerfile

**Acceptance Criteria:**
- All services start successfully with `docker-compose up`
- Health checks pass for all services
- Services restart automatically on failure

---

### Milestone 2: Database Layer (Week 1-2)

**Deliverables:**
- [ ] SQLAlchemy models for all entities
- [ ] Alembic migration setup
- [ ] Initial schema migration (001_initial_schema.py)
- [ ] Database connection pooling configuration

**Acceptance Criteria:**
- Migration runs successfully: `alembic upgrade head`
- All tables created with correct constraints
- Indexes verified with `EXPLAIN ANALYZE`
- Foreign key relationships validated

**Test Cases:**
- Insert supplier → cascade to supplier_items on delete
- UNIQUE constraint on (supplier_id, supplier_sku) enforced
- JSONB characteristics accept valid JSON, reject invalid
- Product status enum accepts only draft/active/archived

---

### Milestone 3: Parser Interface (Week 2)

**Deliverables:**
- [ ] Abstract `ParserInterface` base class
- [ ] `ParsedItem` Pydantic model
- [ ] Parser registration mechanism
- [ ] Configuration validation method

**Acceptance Criteria:**
- Parser interface defines `parse()` and `validate_config()` methods
- New parsers can inherit from base class
- Validation rejects invalid configurations

**Test Cases:**
- Mock parser inherits from ParserInterface successfully
- `validate_config()` catches missing required fields
- `parse()` returns list of `ParsedItem` objects

---

### Milestone 4: Google Sheets Parser (Week 2-3)

**Deliverables:**
- [ ] `GoogleSheetsParser` class
- [ ] gspread authentication setup
- [ ] Dynamic column mapping with fuzzy matching
- [ ] Characteristics JSONB builder
- [ ] Row-level error handling

**Acceptance Criteria:**
- Authenticates with Google service account
- Reads all rows from specified sheet
- Maps columns to standard fields (sku, name, price)
- Extracts characteristics from additional columns
- Handles missing data gracefully (logs to parsing_logs)

**Test Cases:**
- Parse sheet with valid data → all rows inserted
- Parse sheet with missing price → row logged in parsing_logs, others succeed
- Auto-detect columns: "Product Code" → sku, "Description" → name
- Manual override: column_mapping config takes precedence
- Characteristics: merge multiple columns into JSONB

---

### Milestone 5: Queue System (Week 3)

**Deliverables:**
- [ ] arq worker configuration
- [ ] `ParseTaskMessage` message handler
- [ ] Retry logic with exponential backoff
- [ ] Dead letter queue for failed tasks
- [ ] Queue monitoring script

**Acceptance Criteria:**
- Worker consumes messages from Redis queue
- Failed tasks retry up to 3 times with delays (1s, 5s, 25s)
- Tasks exceeding max retries move to DLQ
- Worker logs queue depth periodically

**Test Cases:**
- Enqueue task → worker processes successfully
- Transient error → task retries automatically
- Max retries exceeded → task moves to DLQ
- Worker crash → task requeued after visibility timeout

---

### Milestone 6: Data Ingestion Pipeline (Week 3-4)

**Deliverables:**
- [ ] End-to-end task processing
- [ ] Supplier get-or-create logic
- [ ] SupplierItem upsert with conflict resolution
- [ ] PriceHistory entry creation on price changes
- [ ] Transaction rollback on validation failures
- [ ] ParsingLogs insertion for errors

**Acceptance Criteria:**
- Task received → supplier created if not exists
- Valid items inserted into supplier_items
- Price changes recorded in price_history
- Invalid rows logged in parsing_logs without crashing
- Database transaction rolls back on critical errors

**Test Cases:**
- New supplier → supplier record created, items inserted
- Existing supplier → items upserted, updated_at refreshed
- Price change → new price_history entry, current_price updated
- Duplicate (supplier_id, supplier_sku) → existing row updated
- Validation error on row 50 → rows 1-49 inserted, row 50 logged

---

### Milestone 7: Error Handling & Logging (Week 4)

**Deliverables:**
- [ ] Custom exception hierarchy
- [ ] Structured logging with structlog
- [ ] Error categorization (ValidationError, ParserError, DatabaseError)
- [ ] ParsingLogs table insertion on errors
- [ ] Graceful degradation (partial success)

**Acceptance Criteria:**
- Errors logged with context (task_id, supplier_id, row_number)
- Worker continues processing after non-critical errors
- Critical errors trigger task retry
- Parsing errors queryable via SQL for debugging

**Test Cases:**
- Network timeout → ParserError, task retried
- Invalid price format → ValidationError, row logged, processing continues
- Database connection lost → DatabaseError, transaction rolled back, task retried

---

### Milestone 8: Testing & Validation (Week 4-5)

**Deliverables:**
- [ ] Unit tests for parsers (mock gspread)
- [ ] Integration tests (Docker services)
- [ ] Performance test: 10,000 items in <10 minutes
- [ ] Error scenario tests
- [ ] Test coverage ≥85%

**Acceptance Criteria:**
- All unit tests pass
- Integration tests pass with real Postgres/Redis
- Performance meets NFR: >1,000 items/min
- Error handling validated in test scenarios

**Test Suites:**
1. **Unit Tests:**
   - Parser column mapping logic
   - Pydantic validation rules
   - SQLAlchemy model constraints

2. **Integration Tests:**
   - End-to-end: enqueue task → data in database
   - Google Sheets API integration (test sheet)
   - Database transaction rollback on errors

3. **Performance Tests:**
   - Process 10,000 items within 10 minutes
   - Measure queue throughput with 5 workers
   - Monitor memory usage under load

---

### Milestone 9: Documentation & Deployment (Week 5)

**Deliverables:**
- [ ] Quickstart guide (already created)
- [ ] Parser implementation guide
- [ ] Deployment runbook
- [ ] Monitoring setup (optional)

**Acceptance Criteria:**
- New developer can set up locally in <30 minutes
- Documentation covers common troubleshooting scenarios
- Deployment guide includes rollback procedures

---

## Technical Architecture

### System Components

```
┌─────────────────┐
│  Google Sheets  │
│   (Data Source) │
└────────┬────────┘
         │ HTTPS (gspread)
         ▼
┌─────────────────────────────┐
│   Python Worker Service     │
│   ┌─────────────────────┐   │
│   │  Parser Interface   │   │
│   ├─────────────────────┤   │
│   │ GoogleSheetsParser  │◄──── FR-3
│   │ CSVParser (future)  │   │
│   │ ExcelParser (future)│   │
│   └─────────────────────┘   │
│                             │
│   ┌─────────────────────┐   │
│   │  Data Validation    │   │
│   │  (Pydantic Models)  │◄──── FR-5
│   └─────────────────────┘   │
│                             │
│   ┌─────────────────────┐   │
│   │  Database Layer     │   │
│   │  (SQLAlchemy Async) │◄──── FR-1
│   └─────────────────────┘   │
└────┬──────────────┬─────────┘
     │ Redis        │ PostgreSQL
     ▼              ▼
┌─────────┐    ┌──────────────┐
│  Redis  │    │  PostgreSQL  │
│  Queue  │◄───┤   Database   │
│  + DLQ  │    │  ┌────────┐  │
└─────────┘    │  │suppliers│ │
      ▲        │  │products │ │
      │        │  │sup_items│ │
      │        │  │price_his│ │
      │        │  │parse_log│ │
      │        │  └────────┘  │
      │        └──────────────┘
      │
   [Task Queue] ◄──── FR-4
```

### Data Flow

1. **Task Enqueuing:**
   - External system/script creates `ParseTaskMessage`
   - Message pushed to Redis queue via arq

2. **Task Processing:**
   - Worker consumes message from queue
   - Validates configuration with parser
   - Invokes appropriate parser (based on `parser_type`)

3. **Data Parsing:**
   - Parser fetches data from source (e.g., Google Sheets)
   - Extracts rows and maps columns to standard fields
   - Converts additional columns to characteristics JSONB
   - Returns list of `ParsedItem` objects + errors

4. **Data Validation:**
   - Each `ParsedItem` validated with Pydantic
   - Validation errors logged to `parsing_logs` table
   - Valid items proceed to database insertion

5. **Data Persistence:**
   - Begin database transaction
   - Get or create Supplier record
   - Upsert SupplierItems (handle conflicts)
   - Insert PriceHistory entries for price changes
   - Commit transaction or rollback on error

6. **Result Reporting:**
   - Log task completion with statistics
   - Return `TaskResult` with success/failure counts

---

## Error Handling Strategy

### Error Categories

| Error Type | Retriable? | Action |
|-----------|-----------|--------|
| **ValidationError** | No | Log to parsing_logs, continue processing other rows |
| **ParserError** | Yes | Retry task with backoff |
| **DatabaseError** | Yes | Rollback transaction, retry task |
| **AuthenticationError** | No | Move to DLQ, alert admin |
| **NetworkError** | Yes | Retry task with backoff |

### Retry Configuration

```python
MAX_RETRIES = 3
BACKOFF_DELAYS = [1, 5, 25]  # seconds

# Example: Task fails at 10:00:00
# Retry 1: 10:00:01 (after 1s)
# Retry 2: 10:00:06 (after 5s)
# Retry 3: 10:00:31 (after 25s)
# If still failing → DLQ
```

### Partial Success Handling

- Process succeeds if ≥1 row inserted successfully
- Status: `partial_success` if some rows failed validation
- All validation errors logged to `parsing_logs` for review
- Admin can review errors and re-enqueue task if needed

---

## Security Considerations

### Credentials Management

- **Google Service Account:** JSON file mounted as read-only volume
- **Database Password:** Stored in `.env`, not committed to git
- **Redis Password:** Required for all connections
- **Secrets Rotation:** Manual process for Phase 1

### Database Access

- **Least Privilege:** Worker user has INSERT/UPDATE/SELECT only
- **No DDL:** Migration user separate from worker user
- **Connection Pooling:** Limits concurrent connections to prevent exhaustion

### Input Validation

- **Pydantic:** Validates all parsed data before database insertion
- **SQL Injection:** Protected by SQLAlchemy parameterized queries
- **JSONB Validation:** Ensures valid JSON format before storage

---

## Monitoring & Observability

### Metrics to Track

| Metric | Method | Threshold |
|--------|--------|-----------|
| Queue depth | Redis LLEN | Alert if >1000 |
| DLQ depth | Redis LLEN | Alert if >0 |
| Processing time | Logged per task | Target <10s per task |
| Items per second | Calculated metric | Target >16.67 (1000/min) |
| Error rate | parsing_logs count | Alert if >10% |
| Worker health | Docker healthcheck | Alert if unhealthy |

### Logging

- **Format:** Structured JSON (structlog)
- **Levels:** DEBUG (dev), INFO (prod)
- **Fields:** timestamp, task_id, supplier_id, level, message, duration
- **Destination:** stdout (captured by Docker)

### Future Enhancements (Phase 2+)

- Prometheus metrics export
- Grafana dashboards
- Sentry error tracking
- ELK stack for log aggregation

---

## Performance Requirements

| Requirement | Target | Validation |
|------------|--------|------------|
| **Throughput** | >1,000 items/min | Load test with 10,000 items |
| **Latency** | <100ms queue → processing | Measure with timestamps |
| **Memory** | <512MB per worker | Monitor Docker stats |
| **Database Inserts** | >1,000 records/min | Benchmark with `INSERT` batch |

### Optimization Strategies

1. **Batch Inserts:** Use `session.add_all()` for multiple items
2. **Connection Pooling:** Pre-configured at 20 connections
3. **Async I/O:** Non-blocking database and API calls
4. **Worker Scaling:** Horizontal scaling via Docker replicas

---

## Rollback Plan

### Trigger Conditions

- Database migration fails or corrupts data
- Service crash loop prevents startup
- Data validation errors exceed 10% of processed items
- Queue processing stops entirely for >5 minutes

### Rollback Steps

1. **Stop Services:**
   ```bash
   docker-compose down
   ```

2. **Drain Queue (Prevent Data Loss):**
   ```bash
   python scripts/drain_queue.py > backup.json
   ```

3. **Rollback Database Migration:**
   ```bash
   docker-compose exec worker alembic downgrade -1
   ```

4. **Restore from Backup (if needed):**
   ```bash
   pg_restore -U marketbel_user -d marketbel backup.dump
   ```

5. **Revert Docker Image:**
   ```bash
   git checkout <previous-commit>
   docker-compose build
   docker-compose up -d
   ```

6. **Verify Health:**
   ```bash
   docker-compose ps
   curl http://localhost:8080/health  # (Future API)
   ```

7. **Re-queue Messages:**
   ```bash
   python scripts/requeue_from_backup.py < backup.json
   ```

---

## Definition of Done

This feature is considered complete when:

### Functional Requirements

- [x] ✅ FR-1: Database schema implemented with all tables, indexes, and constraints
- [x] ✅ FR-2: Python service runs in Docker with parser interface and health checks
- [x] ✅ FR-3: Google Sheets parser authenticates, reads data, and normalizes to internal format
- [x] ✅ FR-4: Redis queue system consumes messages with retry and DLQ logic
- [x] ✅ FR-5: End-to-end pipeline ingests data from queue to database with error handling

### Success Criteria

- [ ] 100% of valid rows from Google Sheet successfully stored in database
- [ ] System processes ≥1,000 supplier items per minute
- [ ] Failed tasks retry up to 3 times with exponential backoff
- [ ] All stored records pass validation constraints with zero corruption
- [ ] Service runs continuously for 24 hours without manual intervention
- [ ] New parser can be added and tested within 2 hours
- [ ] All processing errors logged with sufficient context for debugging

### Testing

- [ ] Unit test coverage ≥85% for business logic
- [ ] Integration tests pass for end-to-end flow
- [ ] Performance tests validate throughput targets
- [ ] Error scenario tests confirm graceful handling

### Documentation

- [x] ✅ Quickstart guide enables setup in <30 minutes
- [ ] Parser implementation guide for future data sources
- [ ] Database schema diagram generated
- [ ] Inline code documentation for parser interface and error handling

### Deployment

- [ ] Docker Compose configuration tested locally
- [ ] Environment variables documented in `.env.example`
- [ ] Health checks passing for all services
- [ ] Rollback procedure validated

---

## Next Actions

### Immediate (This Week)

1. **Review this plan** with Tech Lead and stakeholders
2. **Approve data model** and API contracts
3. **Set up project repository** with directory structure
4. **Initialize Docker Compose** and verify services start

### Week 1 Sprint

1. Implement Milestone 1 (Infrastructure Setup)
2. Implement Milestone 2 (Database Layer)
3. Start Milestone 3 (Parser Interface)

### Week 2-3 Sprint

1. Complete Milestone 3 (Parser Interface)
2. Implement Milestone 4 (Google Sheets Parser)
3. Implement Milestone 5 (Queue System)

### Week 4-5 Sprint

1. Implement Milestone 6 (Data Ingestion Pipeline)
2. Implement Milestone 7 (Error Handling)
3. Complete Milestone 8 (Testing & Validation)
4. Finalize Milestone 9 (Documentation)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Google Sheets API quota exceeded | High | Medium | Implement rate limiting, batch operations, cache results |
| Database connection pool exhaustion | High | Low | Monitor pool metrics, configure appropriate pool size |
| Memory leak from pandas DataFrames | Medium | Low | Clear DataFrames after processing, monitor memory |
| JSONB query performance degradation | Medium | Medium | Implement GIN indexes, query optimization |
| Parser failures cascade to all tasks | High | Low | Isolate parser errors, implement per-row error handling |
| Service account credentials compromised | High | Low | Use secret management, rotate credentials regularly |

---

## Approval Signatures

- [x] **Tech Lead:** _Mark________________ Date: _24.11.25______
  - Approves: Architecture, technology choices, database schema

- [x] **Product Owner:** _Mark________________ Date: _24.11.25______
  - Approves: Functional requirements alignment, scope boundaries

- [x] **DevOps/SRE:** _Mark________________ Date: _24.11.25______
  - Approves: Docker configuration, deployment strategy, monitoring plan

- [ ] **Security:** _________________ Date: _______
  - Approves: Credentials management, database access controls, input validation

---

## Appendix

### Related Documents

- [Feature Specification](../spec.md) - Requirements and user scenarios
- [Research Document](./research.md) - Technical decision rationale
- [Data Model](./data-model.md) - Complete database schema and ORM models
- [API Contracts](./contracts/) - Queue message and parser interface schemas
- [Quickstart Guide](./quickstart.md) - Development setup instructions

### Technology References

- [SQLAlchemy 2.0 Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [gspread Documentation](https://docs.gspread.org/)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)

---

**Plan Status:** ✅ **READY FOR IMPLEMENTATION**

**Last Updated:** 2025-11-23  
**Next Review:** After Milestone 3 completion

