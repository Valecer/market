# Task List: Semantic ETL Pipeline Refactoring

**Epic/Feature:** Phase 9 - Semantic ETL with LLM-Based Extraction

**Sprint/Milestone:** Phase 9 Implementation

**Owner:** Development Team

**Spec Reference:** `/specs/009-semantic-etl/spec.md`

---

## Overview

This task list implements the Semantic ETL pipeline refactoring, organized by user story to enable independent implementation and testing. The feature eliminates fragile rule-based parsing by using LLM-based extraction, intelligent category matching, and within-file deduplication.

**User Stories (Priority Order):**
- **US1 (P1):** Admin Uploads Standard Supplier File - Core extraction pipeline
- **US2 (P2):** Admin Uploads Multi-Sheet File - Smart sheet selection
- **US3 (P3):** Admin Reviews New Categories - Category governance UI

---

## Implementation Strategy

### MVP Scope
**US1 only** - Get standard single-sheet extraction working end-to-end before adding multi-sheet and review features.

### Parallel Execution Opportunities
- Within each user story, tasks marked `[P]` can run in parallel (different files, no dependencies)
- Setup and foundational tasks can run in parallel where indicated
- Frontend and backend work within a story can proceed in parallel after contracts are defined

### Independent Test Criteria
Each user story phase includes test criteria that can validate completion independently of other stories.

---

## Phase 1: Setup & Infrastructure ✅ COMPLETE

**Goal:** Prepare environment and install dependencies

**Independent Test Criteria:**
- [X] All services start with `docker-compose up`
- [X] Database migrations apply cleanly
- [X] LangChain imports work in Python
- [X] Environment variables loaded correctly

### Tasks

- [X] T001 Run database migrations in services/ml-analyze/migrations/009_add_category_hierarchy.sql
- [X] T002 Run database migrations in services/ml-analyze/migrations/009_validate_supplier_items.sql
- [X] T003 Run database migrations in services/ml-analyze/migrations/009_enhance_parsing_logs.sql
- [X] T004 [P] Install Python dependencies: langchain-core==0.3.21, langchain-ollama==0.2.0, openpyxl==3.1.5 in services/ml-analyze/requirements.txt
- [X] T005 [P] Add environment variables to docker-compose.yml: USE_SEMANTIC_ETL, FUZZY_MATCH_THRESHOLD, CHUNK_SIZE_ROWS, CHUNK_OVERLAP_ROWS, OLLAMA_MODEL_LLM
- [X] T006 Verify Ollama llama3 model availability via docker exec ollama ollama list
- [X] T007 Add feature flag column to suppliers table: ALTER TABLE suppliers ADD COLUMN use_semantic_etl BOOLEAN DEFAULT false

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ COMPLETE

**Goal:** Create shared data models and type definitions used across all user stories

**Independent Test Criteria:**
- [X] Pydantic models validate sample data without errors
- [X] TypeScript types compile with strict mode
- [X] SQLAlchemy models reflect database schema

### Tasks

- [X] T008 [P] Create Pydantic schema ExtractedProduct in services/ml-analyze/src/schemas/extraction.py with validation
- [X] T009 [P] Create Pydantic schema ExtractionResult in services/ml-analyze/src/schemas/extraction.py with success_rate property
- [X] T010 [P] Create Pydantic schema CategoryMatchResult in services/ml-analyze/src/schemas/category.py
- [X] T011 [P] Create TypeScript JobPhase type with semantic ETL phases in services/bun-api/src/types/job.types.ts
- [X] T012 [P] Create TypeScript CategoryReviewItem interface in services/bun-api/src/types/category.types.ts
- [X] T013 [P] Create TypeScript CategoryApprovalRequest interface in services/bun-api/src/types/category.types.ts
- [X] T014 Update SQLAlchemy Category model to add parent_id, needs_review, is_active, supplier_id in services/ml-analyze/src/db/models.py
- [X] T015 Write unit tests for Pydantic validators in services/ml-analyze/tests/schemas/test_extraction.py

---

## Phase 3: User Story 1 - Standard File Upload (P1) ✅ COMPLETE

**User Story:** As a Marketbel admin, I want to upload an Excel file with a sheet named "Upload to site" so that products are automatically extracted and added to the catalog.

**Goal:** Implement end-to-end semantic extraction for standard single-sheet files

**Independent Test Criteria:**
- [X] Upload test Excel file with 300 products
- [X] All 300 products extracted with Name, Price, Category
- [X] Categories matched with >85% fuzzy threshold
- [X] New categories created with needs_review=true
- [X] Job completes in <2 minutes
- [X] supplier_items table contains all extracted products
- [X] parsing_logs table contains detailed error entries for any failures

**Test Files:**
- `/specs/009-semantic-etl/test_data/standard_supplier_300rows.xlsx`
- `/specs/009-semantic-etl/test_data/performance_test_500rows.xlsx`
- `/specs/009-semantic-etl/test_data/test_metadata.json`
- `/specs/009-semantic-etl/test_data/generate_test_data.py`

### Markdown Conversion (Parallel Group A)

- [X] T016 [P] [US1] Create MarkdownConverter class in services/ml-analyze/src/services/smart_parser/markdown_converter.py
- [X] T017 [P] [US1] Implement convert_excel_to_markdown method using openpyxl in services/ml-analyze/src/services/smart_parser/markdown_converter.py
- [X] T018 [P] [US1] Implement handle_merged_cells logic (repeat values) in services/ml-analyze/src/services/smart_parser/markdown_converter.py
- [X] T019 [P] [US1] Write unit tests for MarkdownConverter in services/ml-analyze/tests/services/test_markdown_converter.py

### LLM Extraction (Parallel Group A)

- [X] T020 [P] [US1] Create LangChainExtractor class in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [X] T021 [P] [US1] Initialize ChatOllama with structured output in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [X] T022 [P] [US1] Implement chunk_markdown method (250 rows, 40 overlap) in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [X] T023 [P] [US1] Design extraction prompt template with column semantics in services/ml-analyze/src/services/smart_parser/prompts.py
- [X] T024 [US1] Implement extract_chunk method with retry logic in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [X] T025 [US1] Add validation error handling with tenacity in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [X] T026 [P] [US1] Write unit tests for LangChainExtractor with mocked LLM in services/ml-analyze/tests/services/test_langchain_extractor.py

### Category Normalization (Parallel Group B)

- [X] T027 [P] [US1] Create CategoryNormalizer class in services/ml-analyze/src/services/category_normalizer.py
- [X] T028 [P] [US1] Implement fuzzy_match_category using RapidFuzz token_set_ratio (85% threshold) in services/ml-analyze/src/services/category_normalizer.py
- [X] T029 [P] [US1] Implement create_category_hierarchy method (parent-first creation) in services/ml-analyze/src/services/category_normalizer.py
- [X] T030 [US1] Add category caching layer for performance in services/ml-analyze/src/services/category_normalizer.py
- [X] T031 [P] [US1] Write unit tests for CategoryNormalizer in services/ml-analyze/tests/services/test_category_normalizer.py

### Deduplication (Parallel Group B)

- [X] T032 [P] [US1] Create DeduplicationService class in services/ml-analyze/src/services/deduplication_service.py
- [X] T033 [P] [US1] Implement hash-based dedup on normalized name + price (1% tolerance) in services/ml-analyze/src/services/deduplication_service.py
- [X] T034 [P] [US1] Write unit tests for DeduplicationService in services/ml-analyze/tests/services/test_deduplication_service.py

### Service Orchestration (Sequential After Groups A & B)

- [X] T035 [US1] Create SmartParserService class in services/ml-analyze/src/services/smart_parser/service.py
- [X] T036 [US1] Implement parse_file orchestration method in services/ml-analyze/src/services/smart_parser/service.py
- [X] T037 [US1] Add progress tracking and Redis job state updates in services/ml-analyze/src/services/smart_parser/service.py
- [X] T038 [US1] Implement partial success handling (80% threshold) in services/ml-analyze/src/services/smart_parser/service.py
- [X] T039 [US1] Add error logging to parsing_logs table in services/ml-analyze/src/services/smart_parser/service.py

### API Integration

- [X] T040 [US1] Update POST /analyze/file endpoint to call SmartParserService in services/ml-analyze/src/api/routes/analyze.py
- [X] T041 [US1] Update GET /analyze/status/:job_id to return semantic ETL metrics in services/ml-analyze/src/api/routes/status.py
- [X] T042 [US1] Add request validation using MLAnalyzeRequest schema in services/ml-analyze/src/schemas/requests.py
- [X] T043 [P] [US1] Write integration tests for /analyze/file endpoint in services/ml-analyze/tests/api/test_analyze_routes.py

### Python Worker Cleanup

- [X] T044 [US1] Remove legacy parsers directory (src/parsers/) - courier pattern complete
- [X] T045 [US1] Remove legacy services (extraction, classification, aggregation, llm) - now in ml-analyze
- [X] T046 [US1] Verify download_and_trigger_ml task only handles file download (verified)
- [X] T047 [US1] Update poll_ml_status task to handle semantic ETL phases (done)

### Testing & Validation

- [X] T048 [US1] Create test data file: standard_supplier_300rows.xlsx with known products in /specs/009-semantic-etl/test_data/
- [X] T049 [US1] Write E2E test: upload standard file, verify extraction in services/ml-analyze/tests/e2e/test_standard_upload.py
- [X] T050 [US1] Write E2E test: verify category fuzzy matching (80% threshold) in services/ml-analyze/tests/e2e/test_category_matching.py
- [X] T051 [US1] Write E2E test: verify deduplication removes duplicates in services/ml-analyze/tests/e2e/test_deduplication.py
- [X] T052 [US1] Run performance test: 500-row file completes in <3 minutes

**Note:** Phase 3 complete. All testing tasks validated with 27 unit/integration tests passing.

---

## Phase 4: User Story 2 - Multi-Sheet Files (P2)

**User Story:** As a Marketbel admin, I want to upload an Excel file with multiple sheets so that the system intelligently identifies and processes only product data sheets.

**Goal:** Add smart sheet selection to handle multi-sheet Excel files

**Independent Test Criteria:**
- [ ] Upload Excel file with 5 sheets: "Instructions", "Products", "Pricing", "Config", "Upload to site"
- [ ] Only "Upload to site" is processed (priority sheet)
- [ ] If no priority sheet, "Products" and "Pricing" are processed
- [ ] "Instructions" and "Config" sheets are skipped
- [ ] Duplicates across sheets are removed
- [ ] Job completes successfully with multi-sheet summary

**Test Files:**
- `/specs/009-semantic-etl/test_data/multi_sheet_supplier.xlsx`

### Smart Sheet Selection

- [ ] T053 [P] [US2] Create SheetSelector class in services/ml-analyze/src/services/smart_parser/sheet_selector.py
- [ ] T054 [P] [US2] Implement identify_priority_sheets method (LLM-based) in services/ml-analyze/src/services/smart_parser/sheet_selector.py
- [ ] T055 [P] [US2] Add priority sheet names: "Upload to site", "Products", "Catalog", "Export", "Товары" in services/ml-analyze/src/services/smart_parser/sheet_selector.py
- [ ] T056 [P] [US2] Implement skip_metadata_sheets logic (skip "Instructions", "Settings") in services/ml-analyze/src/services/smart_parser/sheet_selector.py
- [ ] T057 [P] [US2] Write unit tests for SheetSelector in services/ml-analyze/tests/services/test_sheet_selector.py

### Multi-Sheet Processing

- [ ] T058 [US2] Update SmartParserService to handle multiple sheets in services/ml-analyze/src/services/smart_parser/service.py
- [ ] T059 [US2] Aggregate ExtractionResult across multiple sheets in services/ml-analyze/src/services/smart_parser/service.py
- [ ] T060 [US2] Add cross-sheet deduplication logic in services/ml-analyze/src/services/smart_parser/service.py

### Testing

- [ ] T061 [US2] Create test data: multi_sheet_supplier.xlsx with 5 sheets in /specs/009-semantic-etl/test_data/
- [ ] T062 [US2] Write E2E test: multi-sheet file processing in services/ml-analyze/tests/e2e/test_multi_sheet_upload.py
- [ ] T063 [US2] Write E2E test: verify metadata sheets are skipped in services/ml-analyze/tests/e2e/test_sheet_selection.py

---

## Phase 5: User Story 3 - Category Review Workflow (P3)

**User Story:** As a Marketbel admin, I want to see all categories that need review in the Admin UI so that I can approve or merge them with existing categories.

**Goal:** Implement category governance workflow for admin review

**Independent Test Criteria:**
- [ ] Admin navigates to /admin/categories/review
- [ ] All categories with needs_review=true are displayed
- [ ] Admin can approve a category (sets needs_review=false)
- [ ] Admin can merge a category with existing (transfers products, deletes source)
- [ ] Approved categories immediately available for fuzzy matching
- [ ] Category review count badge shows pending items

**Test Files:**
- `/specs/009-semantic-etl/test_data/test_categories_review.sql`

### Backend API (Bun Service)

- [ ] T064 [P] [US3] Implement GET /categories/review endpoint in services/bun-api/src/controllers/admin/categories.controller.ts
- [ ] T065 [P] [US3] Add query filters: supplier_id, limit, offset in services/bun-api/src/controllers/admin/categories.controller.ts
- [ ] T066 [P] [US3] Implement POST /categories/approve endpoint in services/bun-api/src/controllers/admin/categories.controller.ts
- [ ] T067 [US3] Create CategoryService with approve and merge methods in services/bun-api/src/services/category.service.ts
- [ ] T068 [US3] Add transaction handling for merge operation (transfer products, delete source) in services/bun-api/src/services/category.service.ts
- [ ] T069 [P] [US3] Write unit tests for CategoryService in services/bun-api/tests/services/test_category_service.test.ts

### Frontend UI

- [ ] T070 [P] [US3] Create CategoryReviewPage component in services/frontend/src/pages/admin/CategoryReviewPage.tsx
- [ ] T071 [P] [US3] Design CategoryReviewTable with columns: Name, Parent, Supplier, Product Count, Actions in services/frontend/src/components/admin/CategoryReviewTable.tsx
- [ ] T072 [US3] Implement useCategories hook with TanStack Query in services/frontend/src/hooks/useCategories.ts
- [ ] T073 [US3] Implement useCategoryApproval mutation hook in services/frontend/src/hooks/useCategoryApproval.ts
- [ ] T074 [US3] Add CategoryApprovalDialog component (approve or merge) in services/frontend/src/components/admin/CategoryApprovalDialog.tsx
- [ ] T075 [US3] Add category review count badge to navigation in services/frontend/src/components/layout/AdminNav.tsx
- [ ] T076 [P] [US3] Add i18n translations for category review UI in services/frontend/public/locales/en/admin.json and ru/admin.json

### Testing

- [ ] T077 [US3] Create seed data: categories with needs_review=true in /specs/009-semantic-etl/test_data/test_categories_review.sql
- [ ] T078 [US3] Write E2E test: admin approves category in services/frontend/tests/e2e/test_category_approval.spec.ts
- [ ] T079 [US3] Write E2E test: admin merges duplicate category in services/frontend/tests/e2e/test_category_merge.spec.ts

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal:** Improve observability, error handling, performance, and documentation

### Monitoring & Observability

- [ ] T080 [P] Add structured logging for semantic ETL phases in services/ml-analyze/src/services/smart_parser/service.py
- [ ] T081 [P] Add metrics: extraction_success_rate, category_match_rate, processing_time_seconds in services/ml-analyze/src/api/metrics.py
- [ ] T082 [P] Add debug mode: log markdown chunks and LLM prompts/responses in services/ml-analyze/src/services/smart_parser/langchain_extractor.py

### Error Handling

- [ ] T083 [P] Improve error messages for validation failures in services/ml-analyze/src/services/smart_parser/service.py
- [ ] T084 [P] Add retry logic summary to job status (e.g., "Retried 2/3 times") in services/ml-analyze/src/api/routes/analyze.py
- [ ] T085 [P] Add user-facing error recommendations in services/bun-api/src/services/job.service.ts

### Performance Optimization

- [ ] T086 [P] Profile LLM extraction time per chunk, optimize if >5s in services/ml-analyze/src/services/smart_parser/langchain_extractor.py
- [ ] T087 [P] Add category cache refresh on insert to reduce DB queries in services/ml-analyze/src/services/category_normalizer.py
- [ ] T088 [P] Optimize fuzzy matching for large category sets (>1000 categories) in services/ml-analyze/src/services/category_normalizer.py

### Documentation

- [ ] T089 [P] Create ADR: ADR-009 Semantic ETL with LLM-Based Extraction in /docs/adr/009-semantic-etl.md
- [ ] T090 [P] Update CLAUDE.md with Phase 9 overview and key files in /CLAUDE.md
- [ ] T091 [P] Update API documentation: OpenAPI spec for new endpoints in services/bun-api/docs/openapi.json
- [ ] T092 [P] Add inline code comments for LLM prompt templates in services/ml-analyze/src/services/smart_parser/prompts.py
- [ ] T093 [P] Add admin UI help text for category review workflow in services/frontend/src/pages/admin/CategoryReviewPage.tsx

### Migration & Rollback

- [ ] T094 Document rollback procedure in /specs/009-semantic-etl/rollback.md
- [ ] T095 Create migration checklist in /specs/009-semantic-etl/migration-checklist.md
- [ ] T096 Add feature flag toggle instructions in /specs/009-semantic-etl/feature-flag.md

---

## Task Summary

- **Total Tasks:** 96
- **Setup & Infrastructure:** 7 tasks
- **Foundational:** 8 tasks
- **User Story 1 (P1):** 37 tasks
- **User Story 2 (P2):** 11 tasks
- **User Story 3 (P3):** 16 tasks
- **Polish & Cross-Cutting:** 17 tasks

**Estimated Total Effort:** ~90-120 hours (11-15 days for 1 developer)

---

## Dependencies Graph

### User Story Completion Order

```
Setup (Phase 1) ──┐
                  ├──> Foundational (Phase 2) ──┐
                  │                               ├──> US1 (P1) ──┐
                  │                               │                ├──> US2 (P2) ──┐
                  │                               │                │                ├──> US3 (P3) ──> Polish
                  │                               │                │                │
                  └───────────────────────────────┘                └────────────────┘
```

**Blocking Dependencies:**
- **US1 is prerequisite for US2 and US3:** Multi-sheet and category review build on core extraction
- **Foundational blocks all user stories:** Data models must exist before implementation
- **Setup blocks everything:** Environment must be ready before coding

**No Dependencies (Can start anytime after Setup):**
- Documentation tasks (T089-T093)
- Monitoring tasks (T080-T082)
- Performance optimization tasks (T086-T088)

---

## Parallel Execution Examples

### During User Story 1 (Maximum Parallelization)

**Group A (Backend - Markdown & Extraction):**
- Developer 1: T016-T019 (MarkdownConverter)
- Developer 2: T020-T026 (LangChainExtractor)

**Group B (Backend - Categories & Dedup):**
- Developer 3: T027-T031 (CategoryNormalizer)
- Developer 4: T032-T034 (DeduplicationService)

**Group C (Python Worker):**
- Developer 5: T044-T047 (Legacy parser cleanup)

All groups work in parallel until T035 (SmartParserService orchestration), which depends on Groups A & B completing.

### During User Story 3 (Frontend + Backend Parallel)

**Backend Team:**
- Developer 1: T064-T069 (Bun API endpoints & service)

**Frontend Team:**
- Developer 2: T070-T076 (React components & hooks)

Both teams work in parallel after contracts are agreed upon. Integration happens at T077-T079 (E2E tests).

---

## Testing Strategy

### Unit Tests (Target: ≥90% coverage for critical path)
- MarkdownConverter (T019)
- LangChainExtractor (T026)
- CategoryNormalizer (T031)
- DeduplicationService (T034)
- Pydantic validators (T015)

### Integration Tests
- POST /analyze/file endpoint (T043)
- CategoryService approve/merge (T069)

### E2E Tests
- Standard file upload (T049-T051)
- Multi-sheet processing (T062-T063)
- Category review workflow (T078-T079)

**Test Data Location:** `/specs/009-semantic-etl/test_data/`

---

## Success Metrics

**Per User Story:**

- **US1 Success:**
  - ✅ Extract 300 products from standard file in <2 minutes
  - ✅ Extraction accuracy >95%
  - ✅ Category match rate >80%
  - ✅ Deduplication removes <5% duplicates

- **US2 Success:**
  - ✅ Correctly identify priority sheets
  - ✅ Skip metadata sheets
  - ✅ Cross-sheet deduplication works

- **US3 Success:**
  - ✅ Admin can approve categories
  - ✅ Merge operation transfers products correctly
  - ✅ UI responsive with 100+ pending categories

**Overall Success Criteria:**
- Zero legacy parsing logic remains in python-ingestion
- LLM extraction handles 10 test files with >95% accuracy
- System processes 500-row files in <3 minutes
- Feature flag enables gradual rollout

---

## Rollback Plan

**Trigger Conditions:**
- Extraction accuracy <90%
- Job failure rate >10%
- LLM service unavailable for >1 hour

**Rollback Steps:**
1. Set `USE_SEMANTIC_ETL=false` in environment
2. Update all suppliers: `UPDATE suppliers SET use_semantic_etl = false;`
3. Restart services: `docker-compose restart ml-analyze python-ingestion`
4. Monitor legacy system for stability
5. Debug semantic ETL issues offline

**No Data Migration Needed:** Both systems write to same tables, rollback is instant.

---

## Notes

- **Feature Flag:** Deploy with `USE_SEMANTIC_ETL=false`, enable per-supplier for testing
- **Migration Strategy:** Parallel run (semantic + legacy) for 1 week validation
- **LLM Dependency:** Ensure Ollama llama3 availability before production rollout
- **Monitoring:** Track extraction_success_rate, category_match_rate, processing_time_seconds
- **ULTRATHINK Context:** This task breakdown prioritizes incremental delivery, independent testing, and clear user story boundaries per the workflow requirements

---

**Generated:** 2025-12-04
**Last Updated:** 2025-12-04
**Status:** Ready for Implementation
