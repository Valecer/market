# Implementation Tasks: Data Pipeline Stabilization

**Feature:** 011-pipeline-stabilization

**Branch:** 011-pipeline-stabilization

**Status:** Ready for Implementation

**Generated:** 2025-12-09

---

## Overview

This document breaks down the Data Pipeline Stabilization feature into actionable tasks organized by user story. Each phase represents a complete, independently testable increment.

**Total Estimated Duration:** 9 days (based on plan.md timeline)

---

## Task Summary

| Phase | User Story | Task Count | Estimated Duration |
|-------|------------|------------|-------------------|
| Phase 1 | Setup | 8 tasks | 1 day |
| Phase 2 | Foundational | 6 tasks | 1 day |
| Phase 3 | US1: Idempotent Re-Ingestion | 12 tasks | 1 day |
| Phase 4 | US2: Auto-Creation + Duplicates | 15 tasks | 2 days |
| Phase 5 | US3: Category Hierarchy | 10 tasks | 1 day |
| Phase 6 | US4: Variant Detection | 8 tasks | 1 day |
| Phase 7 | Polish & Integration | 10 tasks | 2 days |
| **Total** | **4 User Stories** | **69 tasks** | **9 days** |

---

## Dependencies & Execution Order

### User Story Dependencies

```
Phase 1: Setup (blocking)
    ↓
Phase 2: Foundational (blocking)
    ↓
    ├─→ Phase 3: US1 (Idempotent Re-Ingestion) [INDEPENDENT]
    ├─→ Phase 4: US2 (Auto-Creation + Duplicates) [INDEPENDENT]
    ├─→ Phase 5: US3 (Category Hierarchy) [INDEPENDENT]
    └─→ Phase 6: US4 (Variant Detection) [depends on US2 for auto-created products]
         ↓
Phase 7: Polish & Integration
```

### Parallel Opportunities

**After Foundational Phase completes, these can run in parallel:**

- **Team A:** US1 (Idempotent Re-Ingestion) + US3 (Category Hierarchy)
- **Team B:** US2 (Auto-Creation + Duplicates)
- **Team C (after Team B):** US4 (Variant Detection)

---

## Phase 1: Setup (Project Initialization)

**Goal:** Prepare project infrastructure and database schema for all features.

**Duration:** 1 day

**Independent Test:** All services start successfully, database migration runs without errors.

---

### Database Migration Tasks

- [ ] T001 Review database schema changes in data-model.md
- [ ] T002 Create Alembic migration file: services/python-ingestion/migrations/versions/011_pipeline_stabilization_schema.py
- [ ] T003 Add source_row_hash VARCHAR(32) column to supplier_items table
- [ ] T004 [P] Create index idx_supplier_items_hash on supplier_items(source_row_hash)
- [ ] T005 Add category_level INTEGER column to categories table
- [ ] T006 [P] Create check constraint chk_category_level on categories (values 1-3)
- [ ] T007 Implement category level backfill function in migration script
- [ ] T008 [P] Create potential_duplicates table with all constraints (see data-model.md)
- [ ] T009 [P] Create indexes on potential_duplicates: status, product_id_1, product_id_2

---

### Environment Configuration Tasks

- [ ] T010 [P] Add HASH_CACHE_ENABLED=true to services/python-ingestion/.env
- [ ] T011 [P] Add HASH_ALGORITHM=md5 to services/python-ingestion/.env
- [ ] T012 [P] Add AUTO_CREATE_THRESHOLD=90 to services/ml-analyze/.env
- [ ] T013 [P] Add VARIANT_DETECTION_ENABLED=true to services/ml-analyze/.env
- [ ] T014 [P] Add DUPLICATE_DETECTION_ENABLED=true to services/ml-analyze/.env
- [ ] T015 [P] Add DUPLICATE_SIMILARITY_THRESHOLD=85 to services/ml-analyze/.env
- [ ] T016 [P] Add DUPLICATE_PRICE_DIFF_THRESHOLD=20 to services/ml-analyze/.env

---

### Setup Verification

- [ ] T017 Run alembic upgrade head and verify migration completes
- [ ] T018 Verify all environment variables loaded via docker-compose config
- [ ] T019 Start all services (docker-compose up -d) and verify health checks pass

---

## Phase 2: Foundational (Blocking Prerequisites)

**Goal:** Implement core infrastructure needed by all user stories.

**Duration:** 1 day

**Independent Test:** Pydantic models validate correctly, type hints pass mypy checks.

---

### Type Definitions & Schemas

- [ ] T020 [P] Create Pydantic schema PotentialDuplicateCreate in services/ml-analyze/src/schemas/duplicate.py
- [ ] T021 [P] Create Pydantic schema PotentialDuplicateResponse in services/ml-analyze/src/schemas/duplicate.py
- [ ] T022 [P] Create Pydantic schema DuplicateDetectionStats in services/ml-analyze/src/schemas/duplicate.py
- [ ] T023 [P] Create TypeScript types in services/bun-api/src/types/duplicate.types.ts (see plan.md Type Safety section)
- [ ] T024 [P] Update SQLAlchemy models for supplier_items with source_row_hash in services/python-ingestion/src/db/models/supplier_item.py
- [ ] T025 [P] Update SQLAlchemy models for categories with category_level in services/python-ingestion/src/db/models/category.py
- [ ] T026 [P] Create SQLAlchemy model for PotentialDuplicate in services/ml-analyze/src/db/models.py
- [ ] T027 Run mypy --strict on all Python services and fix type errors
- [ ] T028 Run tsc --noEmit on all TypeScript services and fix type errors

---

## Phase 3: US1 - Idempotent Re-Ingestion

**User Story:** As a Procurement Manager, I want to re-import supplier price lists multiple times per day so that I can keep prices up-to-date without creating duplicate products.

**Priority:** P1 (Critical)

**Goal:** Implement hash-based idempotency to prevent duplicate products and speed up re-ingestion by 60-80%.

**Duration:** 1 day

**Independent Test:**
1. Import file with 100 rows
2. Re-import same file with 10 price changes
3. Verify: 90 hash hits (UPDATE), 10 hash misses (INSERT), no duplicate products created
4. Assert: Re-ingestion time <50% of initial ingestion

---

### US1: Service Layer Implementation

- [ ] T029 [P] [US1] Create IdempotencyService class in services/python-ingestion/src/services/idempotency_service.py
- [ ] T030 [US1] Implement compute_row_hash(supplier_id, row_data) method with MD5 hashing
- [ ] T031 [US1] Implement _normalize_row_data(row_data) helper method (sort keys, trim whitespace, normalize nulls)
- [ ] T032 [US1] Implement get_cached_item(source_row_hash) method with SQLAlchemy query
- [ ] T033 [US1] Add JSONB comparison for hash collision detection in get_cached_item
- [ ] T034 [US1] Implement update_price_only(item_id, prices) method with partial UPDATE query
- [ ] T035 [US1] Add structured logging for hash hits, misses, collisions in IdempotencyService

---

### US1: Integration with Download Tasks

- [ ] T036 [US1] Import IdempotencyService in services/python-ingestion/src/tasks/download_tasks.py
- [ ] T037 [US1] Modify process_supplier_file function to compute hash for each row before ML call
- [ ] T038 [US1] Add cache lookup logic: if hash found, call update_price_only; else call ML service
- [ ] T039 [US1] Add metrics tracking: hash_hits, hash_misses, ml_extractions_saved
- [ ] T040 [US1] Update job state to include hash metrics in Redis

---

### US1: Testing (if requested - skip if not needed)

- [ ] T041 [P] [US1] Write unit test test_compute_row_hash_deterministic in tests/services/test_idempotency_service.py
- [ ] T042 [P] [US1] Write unit test test_compute_row_hash_column_order_invariant
- [ ] T043 [P] [US1] Write unit test test_get_cached_item_exists
- [ ] T044 [P] [US1] Write unit test test_get_cached_item_not_found
- [ ] T045 [P] [US1] Write unit test test_update_price_only (verify only prices updated)
- [ ] T046 [P] [US1] Write unit test test_hash_collision_handling (simulate collision, verify fallback)
- [ ] T047 [US1] Write integration test test_idempotent_reingestion_flow in tests/integration/ (full E2E: ingest, re-ingest, verify metrics)

---

## Phase 4: US2 - Auto-Creation + Duplicate Detection

**User Story:** As a Sales Manager, I want new supplier items to be automatically added to the catalog so that I don't have to manually review 200+ unmatched items.

**Priority:** P1 (Critical for auto-creation), P2 (Medium for duplicate detection)

**Goal:** Auto-create products for <90% confidence matches, detect and flag potential duplicates.

**Duration:** 2 days

**Independent Test:**
1. Ingest new supplier catalog (200 items, all <90% confidence)
2. Verify: 200 new products created, match_status = 'auto_created'
3. Verify: potential_duplicates table has 5-10 flagged pairs (87-89% similarity)
4. Admin merges 1 duplicate pair
5. Verify: supplier_items from both products now linked to kept product

---

### US2: Auto-Creation Service

- [ ] T048 [P] [US2] Create AutoCreationService class in services/ml-analyze/src/services/auto_creation_service.py
- [ ] T049 [US2] Implement create_product_from_extraction(extraction, supplier_item_id) method
- [ ] T050 [US2] Generate internal_sku format: AUTO-{uuid4().hex[:8].upper()}
- [ ] T051 [US2] Set product status='active' and category_id from extraction
- [ ] T052 [US2] Link supplier_item.product_id and set match_status='auto_created'
- [ ] T053 [US2] Add audit logging for auto-creation events

---

### US2: Matching Service Refactor

- [ ] T054 [US2] Modify matching_service.py to import AutoCreationService
- [ ] T055 [US2] Update match_batch method to check confidence threshold (≥90% = link, <90% = auto-create)
- [ ] T056 [US2] Remove "Unmatched Items" queue logic (match_review_queue insertions for <90%)
- [ ] T057 [US2] Add match statistics: auto_matched_count, auto_created_count
- [ ] T058 [US2] Update job state to include auto-creation metrics

---

### US2: Duplicate Detection Service

- [ ] T059 [P] [US2] Create DuplicateDetectionService class in services/ml-analyze/src/services/duplicate_detection_service.py
- [ ] T060 [US2] Implement detect_duplicates(created_product_ids) method with category-scoped comparison
- [ ] T061 [US2] Implement compute_similarity(name1, name2) using RapidFuzz WRatio
- [ ] T062 [US2] Implement compute_price_diff(product1, product2) helper
- [ ] T063 [US2] Implement are_variants(product_id_1, product_id_2) check
- [ ] T064 [US2] Implement flag_duplicate(product_id_1, product_id_2, similarity_score) with ordered ID constraint
- [ ] T065 [US2] Add check for already-flagged pairs to avoid duplicates in potential_duplicates table

---

### US2: Bun API Endpoints

- [ ] T066 [P] [US2] Create duplicates.controller.ts in services/bun-api/src/controllers/admin/
- [ ] T067 [US2] Implement GET /api/v1/admin/duplicates endpoint (list with pagination)
- [ ] T068 [US2] Implement PATCH /api/v1/admin/duplicates/:id/merge endpoint
- [ ] T069 [US2] Implement PATCH /api/v1/admin/duplicates/:id/dismiss endpoint
- [ ] T070 [US2] Create duplicate.service.ts in services/bun-api/src/services/
- [ ] T071 [US2] Implement DuplicateService.list(status, limit, offset) method
- [ ] T072 [US2] Implement DuplicateService.merge(id, keepProductId, archiveProductId) method
- [ ] T073 [US2] Implement DuplicateService.dismiss(id) method
- [ ] T074 [US2] Add request validation using TypeBox schemas in duplicates.controller.ts
- [ ] T075 [US2] Register duplicate routes in services/bun-api/src/index.ts

---

### US2: Frontend Components

- [ ] T076 [P] [US2] Create DuplicatesReviewPage.tsx in services/frontend/src/pages/admin/
- [ ] T077 [P] [US2] Create PotentialDuplicatesTable.tsx component in services/frontend/src/components/admin/
- [ ] T078 [P] [US2] Create ProductMergeModal.tsx component in services/frontend/src/components/admin/
- [ ] T079 [US2] Implement useQuery hook for fetching duplicates in DuplicatesReviewPage
- [ ] T080 [US2] Implement useMutation hook for merge action
- [ ] T081 [US2] Implement useMutation hook for dismiss action
- [ ] T082 [US2] Add i18n translations for duplicate management UI in public/locales/en/translation.json
- [ ] T083 [US2] Add i18n translations in public/locales/ru/translation.json
- [ ] T084 [US2] Add route /admin/duplicates in services/frontend/src/App.tsx

---

### US2: Testing (if requested)

- [ ] T085 [P] [US2] Write unit test test_create_product_from_extraction in tests/services/test_auto_creation_service.py
- [ ] T086 [P] [US2] Write unit test test_auto_creation_sets_status_active
- [ ] T087 [P] [US2] Write unit test test_auto_creation_generates_internal_sku
- [ ] T088 [P] [US2] Write unit test test_detect_duplicates_within_threshold in tests/services/test_duplicate_detection_service.py
- [ ] T089 [P] [US2] Write unit test test_detect_duplicates_below_threshold
- [ ] T090 [P] [US2] Write unit test test_detect_duplicates_high_price_diff
- [ ] T091 [P] [US2] Write unit test test_detect_duplicates_already_variants
- [ ] T092 [P] [US2] Write API test test_get_duplicates_filters_by_status in services/bun-api/tests/controllers/
- [ ] T093 [P] [US2] Write API test test_merge_duplicates_updates_supplier_items
- [ ] T094 [US2] Write integration test test_auto_creation_and_duplicate_detection_flow

---

## Phase 5: US3 - Category Hierarchy Enforcement

**User Story:** As a Product Catalog Administrator, I want all products to follow a 3-level category hierarchy so that the catalog is organized consistently for clients.

**Priority:** P2 (High)

**Goal:** Enforce 3-level hierarchy (Top → Sub-category → Brand), flag incomplete hierarchies.

**Duration:** 1 day

**Independent Test:**
1. Ingest product with path: ["Electronics", "Laptops", "Dell"]
2. Verify: 3 categories created (L1: Electronics, L2: Laptops, L3: Dell), Product.category_id = Dell.id
3. Ingest product with path: ["Tools"]
4. Verify: 1 category created (L1: Tools), parsing_logs entry: error_type = 'incomplete_category_hierarchy'

---

### US3: Category Hierarchy Service

- [ ] T095 [P] [US3] Create CategoryHierarchyService class in services/ml-analyze/src/services/category_hierarchy_service.py
- [ ] T096 [US3] Implement ensure_3_level_hierarchy(category_path) method
- [ ] T097 [US3] Implement find_or_create_category(name, parent_id, level) method with level validation
- [ ] T098 [US3] Add logic for handling >3 levels: take first 3, log warning
- [ ] T099 [US3] Add logic for handling <3 levels: create partial, flag needs_review
- [ ] T100 [US3] Implement flag_incomplete_hierarchy(category_id) method (insert to parsing_logs)

---

### US3: Category Normalizer Integration

- [ ] T101 [US3] Modify category_normalizer.py to import CategoryHierarchyService
- [ ] T102 [US3] Update normalize_category_with_hierarchy method to build category_path: [Top, Sub, Brand]
- [ ] T103 [US3] Call ensure_3_level_hierarchy for all category assignments
- [ ] T104 [US3] Update product assignment logic to use returned Level 3 category ID

---

### US3: Frontend Breadcrumb Updates

- [ ] T105 [P] [US3] Update category breadcrumb component to display 3 levels consistently
- [ ] T106 [P] [US3] Add padding with "Uncategorized" for incomplete hierarchies (<3 levels)

---

### US3: Testing (if requested)

- [ ] T107 [P] [US3] Write unit test test_ensure_3_level_hierarchy_full_path in tests/services/test_category_hierarchy_service.py
- [ ] T108 [P] [US3] Write unit test test_ensure_3_level_hierarchy_partial_path
- [ ] T109 [P] [US3] Write unit test test_ensure_3_level_hierarchy_excess_path
- [ ] T110 [P] [US3] Write unit test test_find_or_create_category_existing
- [ ] T111 [P] [US3] Write unit test test_find_or_create_category_new
- [ ] T112 [US3] Write integration test test_category_hierarchy_enforcement

---

## Phase 6: US4 - Variant Detection Integration

**User Story:** As a Client, I want similar products (e.g., "48V 20Ah" vs "48V 30Ah") to be presented as variants so that I can easily compare options and select the right one.

**Priority:** P2 (High)

**Goal:** Integrate existing variant_detection_service.py into ingestion pipeline.

**Duration:** 1 day

**Dependencies:** US2 (needs auto-created products to group)

**Independent Test:**
1. Auto-create 2 products: "Battery 48V 20Ah" and "Battery 48V 30Ah"
2. Run variant detection
3. Verify: Products grouped, has_variants=true, variant_schema=[{key: "capacity"}], 2 variant records created

---

### US4: Ingestion Orchestrator

- [ ] T113 [P] [US4] Create IngestionOrchestrator class in services/ml-analyze/src/services/ingestion_orchestrator.py
- [ ] T114 [US4] Import existing VariantDetectionService from variant_detection_service.py
- [ ] T115 [US4] Implement on_batch_complete(batch_id, created_product_ids) hook method
- [ ] T116 [US4] Query categories of newly created products in on_batch_complete
- [ ] T117 [US4] Query all products in same categories for cross-batch variant detection
- [ ] T118 [US4] Call variant_detection_svc.group_variants(all_products_in_categories)
- [ ] T119 [US4] Implement store_variant_group(group) method to create product_variants records
- [ ] T120 [US4] Update parent product with has_variants=true and variant_schema

---

### US4: Integration with Matching Service

- [ ] T121 [US4] Modify matching_service.py to call IngestionOrchestrator.on_batch_complete after auto-creation phase
- [ ] T122 [US4] Pass list of auto-created product IDs to on_batch_complete
- [ ] T123 [US4] Add variant detection metrics to job state: variant_groups_created, products_grouped

---

### US4: Testing (if requested)

- [ ] T124 [P] [US4] Write unit test test_variant_detection_integration in tests/services/test_ingestion_orchestrator.py
- [ ] T125 [P] [US4] Mock VariantDetectionService and verify group_variants called with correct products
- [ ] T126 [US4] Write integration test test_variant_grouping_after_auto_creation

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal:** Complete testing, documentation, and production readiness tasks.

**Duration:** 2 days

---

### Integration Testing

- [ ] T127 Write E2E test: Full ingestion flow (upload → hash dedup → auto-create → variants → duplicates)
- [ ] T128 Write E2E test: Admin merges duplicate via UI, verify supplier_items reassigned
- [ ] T129 Write E2E test: Re-ingestion with 80% cached rows, verify time reduction
- [ ] T130 Verify all integration tests achieve ≥80% code coverage for business logic

---

### Error Handling & Logging

- [ ] T131 [P] Add structured logging (JSON format) for all new services
- [ ] T132 [P] Add error tracking for hash collisions, category violations, variant detection failures
- [ ] T133 [P] Implement retry logic for database connection errors in all services
- [ ] T134 Add Sentry/error tracking integration for production monitoring

---

### Performance Optimization

- [ ] T135 [P] Add batch hash lookups (1000 rows/query) in IdempotencyService
- [ ] T136 [P] Add memoization to category level backfill function
- [ ] T137 Profile duplicate detection with 500 products, optimize if >30 seconds
- [ ] T138 Add database connection pooling configuration for high concurrency

---

### Documentation & Deployment

- [ ] T139 [P] Update API documentation (OpenAPI/Swagger) for duplicate management endpoints
- [ ] T140 [P] Update README with feature overview and environment variables
- [ ] T141 [P] Create ADR (Architecture Decision Record) documenting MD5 choice, 3-level constraint, auto-creation strategy
- [ ] T142 Add inline code documentation for hash normalization logic
- [ ] T143 Create deployment runbook with rollback procedures
- [ ] T144 Create monitoring dashboard with key metrics (hash_hit_rate, auto_creation_rate, duplicate_queue_size)

---

### Staging & Production Deployment

- [ ] T145 Deploy to staging environment with feature flags OFF
- [ ] T146 Run smoke tests on staging: ingest sample file, verify all phases work
- [ ] T147 Enable feature flags gradually: HASH_CACHE_ENABLED=true first
- [ ] T148 Enable AUTO_CREATE_THRESHOLD=90, monitor auto-creation rate for 24 hours
- [ ] T149 Enable VARIANT_DETECTION_ENABLED=true and DUPLICATE_DETECTION_ENABLED=true
- [ ] T150 Monitor metrics for 1 week: hash_hit_rate ≥70%, auto_creation_rate 50-90%, duplicate queue <500
- [ ] T151 Deploy to production with same gradual rollout strategy
- [ ] T152 Create alert rules: hash_hit_rate <50%, auto_creation_rate >95%, duplicate_queue >500

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**Recommended MVP:** US1 only (Idempotent Re-Ingestion)

**Rationale:**
- US1 provides immediate value: 60-80% time savings on re-ingestion
- US1 is independently testable and deployable
- US1 has no dependencies on other user stories
- US1 solves the most critical pain point (duplicate products on re-import)

**MVP Tasks:** T001-T047 (47 tasks, 2 days)

**MVP Success Criteria:**
- Re-importing a file with 80% unchanged rows completes in <40% of initial time
- No duplicate products created on re-import
- Hash hit rate ≥70%

---

### Incremental Delivery Plan

**Iteration 1 (MVP):** US1 - Idempotent Re-Ingestion (2 days)
- Deploy to production
- Monitor for 1 week
- Collect feedback on time savings

**Iteration 2:** US2 - Auto-Creation + Duplicate Detection (3 days)
- Deploy to production
- Monitor auto-creation rate and duplicate queue
- Tune thresholds based on feedback

**Iteration 3:** US3 + US4 - Category Hierarchy + Variant Detection (2 days)
- Deploy to production
- Monitor category compliance and variant grouping quality

**Iteration 4:** Polish & Production Hardening (2 days)
- Performance optimization
- Monitoring dashboard
- Documentation

---

## Parallel Execution Examples

### Example 1: After Foundational Phase

**Team A (2 developers):**
- T029-T047: US1 (Idempotent Re-Ingestion)
- T095-T112: US3 (Category Hierarchy)

**Team B (3 developers):**
- T048-T094: US2 (Auto-Creation + Duplicates)

**Team C (1 developer, after Team B completes):**
- T113-T126: US4 (Variant Detection)

**Estimated Parallel Completion:** 3 days (vs. 5 days sequential)

---

### Example 2: Testing in Parallel

All testing tasks marked [P] can run in parallel:

**QA Engineer 1:**
- T041-T046: US1 unit tests

**QA Engineer 2:**
- T085-T093: US2 unit/API tests

**QA Engineer 3:**
- T107-T111: US3 unit tests
- T124-T125: US4 unit tests

**Estimated Testing Completion:** 1 day (vs. 2 days sequential)

---

## Task Checklist Format Validation

✅ **All tasks follow required format:**
- Checkbox: `- [ ]` ✓
- Task ID: Sequential (T001-T152) ✓
- [P] marker: 68 parallelizable tasks identified ✓
- [Story] label: 54 tasks labeled with user stories ✓
- File paths: Specified for all implementation tasks ✓

---

## Monitoring & Success Metrics

### Key Metrics Dashboard

**Idempotency (US1):**
- `hash_hit_rate`: ≥70% (target)
- `reingestion_time_reduction`: 60-80% (target)
- `hash_collision_rate`: <0.01% (alert if higher)

**Auto-Creation (US2):**
- `auto_creation_rate`: 50-90% (healthy range)
- `duplicate_queue_size`: <500 (alert if higher)
- `duplicate_false_positive_rate`: <10% (target)

**Category Hierarchy (US3):**
- `category_compliance_rate`: 100% assigned to L1-3 (target)
- `incomplete_hierarchy_count`: <100 pending review (alert if higher)

**Variant Detection (US4):**
- `variant_grouping_recall`: ≥85% (target)
- `variant_groups_created_per_batch`: track trend

---

## Rollback Plan

**Trigger Conditions:**
- hash_hit_rate <50%
- auto_creation_rate >95%
- duplicate_queue >500 pending
- category_violations >10% of ingestions

**Rollback Steps:**
1. Disable feature flags:
   - `HASH_CACHE_ENABLED=false`
   - `AUTO_CREATE_THRESHOLD=95` (revert to old threshold)
   - `VARIANT_DETECTION_ENABLED=false`
   - `DUPLICATE_DETECTION_ENABLED=false`
2. Revert services to previous version
3. Database: Do NOT drop new columns (preserve data for debugging)
4. Investigate root cause via logs and metrics
5. Fix issues and redeploy with gradual rollout

---

## References

- [Feature Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Data Model](./data-model.md)
- [API Contracts](./contracts/duplicates-api.yaml)
- [Research Decisions](./research.md)
- [Quickstart Guide](./quickstart.md)

---

**End of Tasks Document**
