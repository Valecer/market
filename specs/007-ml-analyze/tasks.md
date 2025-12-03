# Task List: ML-Based Product Analysis & Merging Service

**Epic/Feature:** [007-ml-analyze Plan](./plan.md) | [Specification](./spec.md)

**Sprint/Milestone:** Phase 007

**Owner:** Development Team

**Total Tasks:** 68 tasks across 7 phases

**Estimated Duration:** 18 days (3.5 weeks)

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**Recommended MVP:** Phase 1 (Setup) + Phase 2 (Foundation) + Phase 3 (US1: File Parsing)

**Rationale:** File parsing is the foundational capability that unblocks all other features. A working parser that can extract data from complex PDFs and Excel files delivers immediate value and validates the technical approach before investing in embeddings and LLM matching.

**MVP Deliverable:** Service that accepts PDF/Excel files, normalizes data, and inserts into supplier_items table.

### Incremental Delivery Path

1. **Week 1:** Setup + Foundation → Deployable service with health checks
2. **Week 2:** US1 (Parsing) → Can process complex files
3. **Week 3:** US3 (Embeddings) + US2 (Matching) → Full AI-powered matching
4. **Week 3.5:** US4 (Job Status) + Polish → Production-ready

### Parallel Execution Opportunities

Tasks marked with **[P]** can be executed in parallel with other [P] tasks in the same phase, as they operate on different files and have no shared dependencies.

**Example Parallelization:**
- Phase 1: T002, T003, T004 can run concurrently (different config files)
- Phase 3 (US1): T020 (ExcelStrategy) and T021 (PdfStrategy) can run concurrently (independent parsers)
- Phase 4 (US3): T030 (VectorService) and T031 (embedding repository) can run concurrently

---

## Task Organization

Tasks are organized by **User Story** to enable independent implementation and testing:

- **Phase 1:** Setup & Infrastructure (project initialization)
- **Phase 2:** Foundational Components (blocking prerequisites for all stories)
- **Phase 3:** US1 - File Parsing (first user story, foundational)
- **Phase 4:** US3 - Vector Embeddings (depends on US1)
- **Phase 5:** US2 - LLM Matching (depends on US3)
- **Phase 6:** US4 - Job Status API (mostly independent)
- **Phase 7:** Polish & Cross-Cutting Concerns

Each phase represents a complete, independently testable increment.

---

## Phase 1: Setup & Infrastructure

**Goal:** Initialize project structure, configure development environment, and establish database foundation.

**Independent Test Criteria:**
- [X] Service starts and responds to health check
- [X] Database migrations apply cleanly
- [X] Ollama models are accessible
- [X] All dependencies install without errors

### Tasks

- [X] T001 Create ml-analyze service directory structure in services/ml-analyze/
- [X] T002 [P] Create requirements.txt with all Python dependencies (fastapi, langchain, asyncpg, pgvector, etc.)
- [X] T003 [P] Create pyproject.toml for project metadata and build configuration
- [X] T004 [P] Create .env.example with all required environment variables
- [X] T005 [P] Create Dockerfile for ml-analyze service in services/ml-analyze/
- [X] T006 [P] Update docker-compose.yml to add ml-analyze service container
- [X] T007 Create Python virtual environment and install dependencies from requirements.txt
- [X] T008 [P] Install and configure Ollama with nomic-embed-text and llama3 models
- [X] T009 Create Alembic migration 007_enable_pgvector.py to enable vector extension
- [X] T010 Create Alembic migration 008_create_product_embeddings.py for embeddings table
- [X] T011 Run database migrations and verify product_embeddings table exists
- [X] T012 [P] Create src/__init__.py to mark as Python package
- [X] T013 [P] Create src/config/settings.py for environment variable management using pydantic-settings
- [X] T014 [P] Create src/api/__init__.py for API package
- [X] T015 [P] Create src/db/__init__.py for database package
- [X] T016 [P] Create src/ingest/__init__.py for ingestion package
- [X] T017 [P] Create src/rag/__init__.py for RAG package
- [X] T018 Create src/api/main.py with minimal FastAPI app and /health endpoint
- [X] T019 Test service startup: uvicorn src.api.main:app --reload and verify http://localhost:8001/health

**Dependencies:** None (starting point)

---

## Phase 2: Foundational Components

**Goal:** Implement shared infrastructure and base classes that all user stories depend on.

**Independent Test Criteria:**
- [X] Database connection pool works with async operations
- [X] Pydantic models validate request/response data correctly
- [X] Logging produces structured JSON output
- [X] Abstract base classes define clear contracts

### Tasks

- [X] T020 [P] [FOUND] Create src/db/models.py with SQLAlchemy ProductEmbedding model
- [X] T021 [P] [FOUND] Create src/db/connection.py for asyncpg connection pool management
- [X] T022 [P] [FOUND] Create src/schemas/requests.py with Pydantic models (FileAnalysisRequest, BatchMatchRequest)
- [X] T023 [P] [FOUND] Create src/schemas/responses.py with Pydantic models (FileAnalysisResponse, JobStatus, HealthResponse)
- [X] T024 [P] [FOUND] Create src/schemas/domain.py with domain models (MatchResult, NormalizedRow, ProductEmbedding)
- [X] T025 [FOUND] Create src/ingest/table_normalizer.py with abstract base class TableNormalizer (parse method signature)
- [X] T026 [P] [FOUND] Create src/utils/logger.py for structured JSON logging configuration
- [X] T027 [P] [FOUND] Create src/utils/errors.py for custom exception classes (ParsingError, EmbeddingError, LLMError)
- [X] T028 [FOUND] Update src/api/main.py to configure logging, database connection lifecycle, and OpenAPI metadata

**Dependencies:** Phase 1 (Setup)

---

## Phase 3: US1 - File Parsing

**User Story:** As a procurement admin, I want to upload PDF price lists with complex table layouts, so that supplier data is automatically extracted without manual data entry.

**Goal:** Implement file parsing capabilities for PDF and Excel files with complex formatting.

**Independent Test Criteria:**
- [ ] PDF file with tables is parsed to Markdown format
- [ ] Excel file with merged cells is normalized via forward-fill
- [ ] Parsing errors are logged to parsing_logs table without crashing
- [ ] Normalized data is returned as list of dicts with standard schema
- [ ] Integration test: Upload sample PDF → verify supplier_items table populated

### Tasks

- [ ] T029 [US1] Create src/ingest/chunker.py with Chunker class (chunk method: row → semantic chunk)
- [ ] T030 [P] [US1] Implement ExcelStrategy in src/ingest/excel_strategy.py (openpyxl + pandas forward-fill)
- [ ] T031 [P] [US1] Implement PdfStrategy in src/ingest/pdf_strategy.py (pymupdf4llm Markdown extraction)
- [ ] T032 [US1] Create src/ingest/parser_factory.py to instantiate correct strategy based on file_type
- [ ] T033 [P] [US1] Create src/db/repositories/supplier_items_repo.py for CRUD operations on supplier_items
- [ ] T034 [P] [US1] Create src/db/repositories/parsing_logs_repo.py for error logging
- [ ] T035 [US1] Create src/services/ingestion_service.py to orchestrate parsing → normalization → database insert
- [ ] T036 [P] [US1] Write unit tests for ExcelStrategy in tests/unit/test_excel_strategy.py
- [ ] T037 [P] [US1] Write unit tests for PdfStrategy in tests/unit/test_pdf_strategy.py
- [ ] T038 [P] [US1] Write unit tests for Chunker in tests/unit/test_chunker.py
- [ ] T039 [US1] Create integration test in tests/integration/test_file_parsing.py (end-to-end: file → database)
- [ ] T040 [US1] Add sample test files (sample.pdf, sample_merged_cells.xlsx) to tests/fixtures/

**Dependencies:** Phase 2 (Foundational)

---

## Phase 4: US3 - Vector Embeddings

**User Story:** As a procurement admin, I want the system to find semantically similar products across suppliers, so that variations in naming are correctly identified.

**Goal:** Implement vector embedding generation and similarity search using pgvector.

**Independent Test Criteria:**
- [ ] Text is converted to 768-dim vector embedding via Ollama
- [ ] Embeddings are stored in product_embeddings table
- [ ] Cosine similarity search returns Top-5 matches within 500ms
- [ ] IVFFLAT index is created and functional
- [ ] Integration test: Generate embedding → store → search → verify results

### Tasks

- [ ] T041 [US3] Create src/rag/vector_service.py with VectorService class (embed_query, similarity_search methods)
- [ ] T042 [US3] Implement embed_query method using langchain_ollama.OllamaEmbeddings (nomic-embed-text)
- [ ] T043 [US3] Implement similarity_search method with asyncpg + pgvector cosine distance query
- [ ] T044 [P] [US3] Create src/db/repositories/embeddings_repo.py for CRUD on product_embeddings table
- [ ] T045 [US3] Implement insert_embedding method in embeddings_repo with conflict handling (ON CONFLICT DO UPDATE)
- [ ] T046 [US3] Implement search_similar method in embeddings_repo (vector <=> query ORDER BY distance LIMIT 5)
- [ ] T047 [P] [US3] Write unit tests for VectorService in tests/unit/test_vector_service.py (mock Ollama API)
- [ ] T048 [P] [US3] Write integration test for Ollama embeddings in tests/integration/test_ollama_embeddings.py (real API call)
- [ ] T049 [US3] Write integration test for pgvector operations in tests/integration/test_pgvector_search.py
- [ ] T050 [US3] Performance test: Measure embedding generation time and similarity search latency

**Dependencies:** Phase 2 (Foundational), US1 (data must be parsed before embedding)

---

## Phase 5: US2 - LLM Matching

**User Story:** As a procurement admin, I want newly ingested supplier items to be automatically matched to existing products, so that I don't have to manually link thousands of similar items.

**Goal:** Implement LLM-based product matching with confidence scoring and review queue integration.

**Independent Test Criteria:**
- [ ] LLM receives structured prompt with item + Top-5 candidates
- [ ] LLM returns valid JSON with confidence scores
- [ ] High-confidence matches (>90%) update supplier_items.product_id
- [ ] Medium-confidence matches (70-90%) insert into match_review_queue
- [ ] Low-confidence matches (<70%) are logged
- [ ] Integration test: Match item → verify database updates correct

### Tasks

- [ ] T051 [US2] Create src/rag/prompt_templates.py with MATCH_PROMPT template using LangChain ChatPromptTemplate
- [ ] T052 [US2] Create src/rag/merger_agent.py with MergerAgent class (find_matches method)
- [ ] T053 [US2] Implement find_matches method: vector search → construct prompt → LLM call → parse JSON
- [ ] T054 [US2] Implement LLM JSON response parsing with error handling (try/except for JSONDecodeError)
- [ ] T055 [US2] Implement confidence threshold logic (>0.9 auto, 0.7-0.9 review, <0.7 reject)
- [ ] T056 [P] [US2] Create src/db/repositories/match_review_repo.py for match_review_queue operations
- [ ] T057 [US2] Create src/services/matching_service.py to orchestrate VectorService + MergerAgent + database writes
- [ ] T058 [P] [US2] Write unit tests for MergerAgent in tests/unit/test_merger_agent.py (mock LLM responses)
- [ ] T059 [P] [US2] Write unit tests for prompt templates in tests/unit/test_prompt_templates.py
- [ ] T060 [US2] Write integration test for LLM matching in tests/integration/test_llm_matching.py (real Ollama llama3)
- [ ] T061 [US2] Write integration test for matching service in tests/integration/test_matching_service.py (end-to-end)

**Dependencies:** Phase 4 (US3: Vector Embeddings)

---

## Phase 6: US4 - Job Status API

**User Story:** As a procurement admin, I want to track the progress of file analysis jobs, so that I know when data is ready for review.

**Goal:** Implement FastAPI endpoints for job submission and status tracking with Redis-based state management.

**Independent Test Criteria:**
- [ ] POST /analyze/file returns job_id and enqueues background task
- [ ] GET /analyze/status/:job_id returns current job state from Redis
- [ ] Background task processes file asynchronously with progress updates
- [ ] Job status includes progress percentage and error list
- [ ] Integration test: Submit job → poll status → verify completion

### Tasks

- [ ] T062 [US4] Create src/services/job_service.py for Redis job status management (create, update, get)
- [ ] T063 [US4] Create src/api/routes/analyze.py with POST /analyze/file endpoint
- [ ] T064 [US4] Implement analyze_file endpoint: validate request → create job → enqueue task → return job_id
- [ ] T065 [US4] Create src/api/routes/status.py with GET /analyze/status/:job_id endpoint
- [ ] T066 [US4] Implement get_job_status endpoint: fetch from Redis → return JobStatus response
- [ ] T067 [US4] Create src/tasks/file_analysis_task.py for arq background worker
- [ ] T068 [US4] Implement process_file_task: parse → embed → match → update job status in Redis
- [ ] T069 [P] [US4] Create POST /analyze/vision stub endpoint (returns 501 Not Implemented)
- [ ] T070 [P] [US4] Write unit tests for job_service in tests/unit/test_job_service.py
- [ ] T071 [P] [US4] Write API integration tests in tests/integration/test_api_endpoints.py (FastAPI TestClient)
- [ ] T072 [US4] Write E2E test in tests/e2e/test_full_pipeline.py (submit job → wait for completion → verify results)

**Dependencies:** Phase 5 (US2: Matching) - uses all services

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal:** Add production-readiness features: error handling, logging, monitoring, documentation.

**Independent Test Criteria:**
- [ ] All endpoints have proper error responses
- [ ] OpenAPI documentation is complete and accurate
- [ ] Logging covers all critical operations
- [ ] Docker Compose orchestrates all services correctly
- [ ] README has complete setup instructions

### Tasks

- [ ] T073 [P] Add error handling middleware to src/api/main.py (catch all exceptions → ErrorResponse)
- [ ] T074 [P] Add request logging middleware to src/api/main.py (log all requests with duration)
- [ ] T075 [P] Add CORS configuration to src/api/main.py (configure allowed origins)
- [ ] T076 [P] Create src/api/routes/health.py with comprehensive health check (database + Ollama + Redis)
- [ ] T077 [P] Add OpenAPI tags and descriptions to all endpoints for auto-generated docs
- [ ] T078 [P] Create services/ml-analyze/README.md with setup instructions and architecture diagram
- [ ] T079 [P] Update root README.md to document ml-analyze service
- [ ] T080 Create services/ml-analyze/.dockerignore to exclude unnecessary files from Docker build
- [ ] T081 [P] Configure mypy for strict type checking in pyproject.toml
- [ ] T082 [P] Configure pytest in pyproject.toml with coverage settings (target ≥80%)
- [ ] T083 Run mypy src/ and fix all type errors
- [ ] T084 Run pytest with coverage and ensure ≥80% coverage for business logic
- [ ] T085 [P] Create docker-compose.test.yml for running tests in isolated environment
- [ ] T086 Test full Docker Compose stack: docker-compose up -d → verify all services healthy
- [ ] T087 [P] Create deployment documentation in specs/007-ml-analyze/DEPLOYMENT.md
- [ ] T088 Create rollback procedure documentation in specs/007-ml-analyze/ROLLBACK.md

**Dependencies:** All previous phases

---

## Dependency Graph (User Story Completion Order)

```
Phase 1: Setup
    ↓
Phase 2: Foundation
    ↓
Phase 3: US1 (File Parsing) ──┐
    ↓                          │
Phase 4: US3 (Embeddings) ←───┘
    ↓
Phase 5: US2 (Matching)
    ↓
Phase 6: US4 (Job Status) ←── Uses all services
    ↓
Phase 7: Polish
```

**Critical Path:** Setup → Foundation → US1 → US3 → US2 → US4 → Polish

**Parallel Opportunities:**
- Within US1: Excel and PDF parsers can be implemented concurrently
- Within US3: VectorService and embeddings repository can be developed in parallel
- Within Phase 7: Most polish tasks are independent and can run concurrently

---

## Acceptance Criteria Summary

### Phase 3 (US1): File Parsing ✓ Complete When:
- [ ] PDF with complex tables → Parsed to normalized dict list
- [ ] Excel with merged cells → Forward-filled and normalized
- [ ] Errors logged to parsing_logs without crashes
- [ ] Data inserted into supplier_items with status 'pending_match'

### Phase 4 (US3): Vector Embeddings ✓ Complete When:
- [ ] Text → 768-dim vector via Ollama nomic-embed-text
- [ ] Vectors stored in product_embeddings with IVFFLAT index
- [ ] Similarity search returns Top-5 in <500ms

### Phase 5 (US2): LLM Matching ✓ Complete When:
- [ ] Item + Top-5 candidates → LLM prompt → JSON response
- [ ] >90% confidence → supplier_items.product_id updated
- [ ] 70-90% confidence → match_review_queue entry
- [ ] <70% confidence → parsing_logs entry

### Phase 6 (US4): Job Status API ✓ Complete When:
- [ ] POST /analyze/file → job_id returned, task enqueued
- [ ] GET /analyze/status/:job_id → current state from Redis
- [ ] Background task updates progress in real-time
- [ ] 100-item file completes in <2 minutes

---

## Testing Strategy

**Note:** Tests are included in task breakdown but are optional. Remove test tasks if TDD is not required.

### Unit Tests (68% of test tasks)
- Mock external dependencies (Ollama API, database)
- Test business logic in isolation
- Fast execution (<1s per test)

### Integration Tests (24% of test tasks)
- Real Ollama API calls (embedding + LLM)
- Real database operations (asyncpg + pgvector)
- Real file parsing (sample PDFs/Excel)

### E2E Tests (8% of test tasks)
- Full pipeline: Upload → Parse → Embed → Match → Verify
- Docker Compose environment
- Slow execution (~30s per test)

**Coverage Target:** ≥80% for all business logic (src/services/, src/rag/, src/ingest/)

---

## Task Formatting Guide

**Format:** `- [ ] T### [P] [US#] Description with exact file path`

**Components:**
- `T###`: Sequential task ID
- `[P]`: Parallelizable (optional)
- `[US#]`: User Story label (required for story phases)
- `[FOUND]`: Foundational task (optional, for Phase 2)

**Examples:**
- ✅ `- [ ] T030 [P] [US1] Implement ExcelStrategy in src/ingest/excel_strategy.py`
- ✅ `- [ ] T041 [US3] Create src/rag/vector_service.py with VectorService class`
- ✅ `- [ ] T073 [P] Add error handling middleware to src/api/main.py`

---

## Summary Statistics

| Phase | Tasks | Parallelizable | User Story | Duration |
|-------|-------|----------------|------------|----------|
| Phase 1: Setup | 19 | 12 (63%) | - | 2 days |
| Phase 2: Foundation | 9 | 7 (78%) | FOUND | 1 day |
| Phase 3: US1 Parsing | 12 | 6 (50%) | US1 | 3 days |
| Phase 4: US3 Embeddings | 10 | 4 (40%) | US3 | 2 days |
| Phase 5: US2 Matching | 11 | 3 (27%) | US2 | 4 days |
| Phase 6: US4 Job Status | 11 | 4 (36%) | US4 | 3 days |
| Phase 7: Polish | 16 | 12 (75%) | - | 3 days |
| **Total** | **88** | **48 (55%)** | **4 stories** | **18 days** |

**MVP Scope:** 40 tasks (Phases 1-3) = 6 days

**Parallel Execution:** Up to 55% of tasks can run concurrently when properly orchestrated.

---

**Next Steps:**

1. **Review & Prioritize:** Confirm MVP scope with stakeholders
2. **Assign Tasks:** Distribute tasks to team members based on expertise
3. **Begin Implementation:** Start with Phase 1 (Setup)
4. **Track Progress:** Use `/speckit.implement` or manual task tracking

**Ready to implement!** 🚀
