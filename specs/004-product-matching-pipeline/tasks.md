# Tasks: Product Matching & Data Enrichment Pipeline

**Feature:** 004-product-matching-pipeline  
**Created:** 2025-11-30  
**Status:** Ready for Implementation

---

## Overview

This document contains all implementation tasks for Phase 4: Product Matching & Data Enrichment Pipeline. Tasks are organized by user story priority to enable independent implementation and testing.

**Functional Requirements Mapping:**
| FR | Priority | User Story | Description |
|----|----------|------------|-------------|
| FR-1 | Critical | US1 | Automatic Product Matcher ("The Linker") |
| FR-3 | Critical | US2 | Price & Availability Aggregation |
| FR-2 | High | US3 | Characteristics Extractor ("The Enricher") |
| FR-4 | High | US4 | Manual Override Handling (Feedback Loop) |
| FR-5 | Medium | US5 | Match Review Queue |

---

## Phase 1: Setup

**Goal:** Initialize project dependencies and configuration for the matching pipeline.

**Independent Test Criteria:**
- Worker starts without import errors
- Configuration loads from environment variables
- RapidFuzz library is importable

### Tasks

- [X] T001 Add rapidfuzz dependency to `services/python-ingestion/requirements.txt`
- [X] T002 Create matching settings configuration class in `services/python-ingestion/src/config.py`
- [X] T003 [P] Create `services/python-ingestion/src/services/matching/__init__.py` package init
- [X] T004 [P] Create `services/python-ingestion/src/services/extraction/__init__.py` package init
- [X] T005 [P] Create `services/python-ingestion/src/tasks/__init__.py` package init
- [X] T006 [P] Create `services/python-ingestion/src/models/matching.py` with MatchStatusEnum and MatchCandidate Pydantic models
- [X] T007 [P] Create `services/python-ingestion/src/models/review_queue.py` with ReviewStatusEnum and ReviewQueueItem models
- [X] T008 [P] Create `services/python-ingestion/src/models/extraction.py` with ExtractedFeatures Pydantic model

---

## Phase 2: Foundational (Database Schema)

**Goal:** Extend database schema with matching fields and new tables. This must complete before any user story implementation.

**Independent Test Criteria:**
- Migration runs without errors
- `supplier_items` has `match_status`, `match_score`, `match_candidates` columns
- `products` has `min_price`, `availability`, `mrp` columns
- `match_review_queue` table exists with all indexes
- Enum types `match_status` and `review_status` exist in PostgreSQL

### Tasks

- [X] T009 Create Alembic migration `services/python-ingestion/migrations/versions/002_add_matching_pipeline.py`
- [X] T010 Add `match_status` and `review_status` PostgreSQL ENUM types in migration
- [X] T011 Add `min_price`, `availability`, `mrp` columns to products table in migration
- [X] T012 Add `match_status`, `match_score`, `match_candidates` columns to supplier_items table in migration
- [X] T013 Create `match_review_queue` table with all columns and constraints in migration
- [X] T014 Add all required indexes (products, supplier_items, match_review_queue) in migration
- [X] T015 Update `services/python-ingestion/src/db/models/product.py` with min_price, availability, mrp fields
- [X] T016 Update `services/python-ingestion/src/db/models/supplier_item.py` with MatchStatus enum and match fields
- [X] T017 Create `services/python-ingestion/src/db/models/match_review_queue.py` SQLAlchemy model

---

## Phase 3: User Story 1 - Automatic Product Matcher (Critical)

**Goal:** Implement FR-1 - Automatically match unlinked supplier items to existing products or create new ones based on name similarity.

**Story:** As a system process, I want to automatically match supplier items to products based on name similarity, so that items with ≥95% similarity are auto-linked, 70-94% are flagged for review, and <70% create new products.

**Independent Test Criteria:**
- Given an item with 96%+ similarity → item is auto-linked
- Given an item with 78% similarity → item is flagged as `potential_match`
- Given an item with 50% similarity → new draft product is created
- Matching processes ≥1000 items/minute (performance target)
- Concurrent workers don't create duplicate matches (locking works)

### Tasks

- [X] T018 [US1] Create MatcherStrategy abstract base class in `services/python-ingestion/src/services/matching/matcher.py`
- [X] T019 [US1] Create MatchCandidate and MatchResult dataclasses in `services/python-ingestion/src/services/matching/matcher.py`
- [X] T020 [US1] Implement RapidFuzzMatcher class with find_matches method in `services/python-ingestion/src/services/matching/matcher.py`
- [X] T021 [US1] Add score_cutoff and preprocessing to RapidFuzz calls for performance in `services/python-ingestion/src/services/matching/matcher.py`
- [X] T022 [US1] Create match_items_task function in `services/python-ingestion/src/tasks/matching_tasks.py`
- [X] T023 [US1] Implement SELECT FOR UPDATE SKIP LOCKED query for unmatched items in match_items_task
- [X] T024 [US1] Implement auto-match logic (score ≥95%) with product linking in match_items_task
- [X] T025 [US1] Implement potential-match logic (score 70-94%) with review queue entry in match_items_task
- [X] T026 [US1] Implement new product creation logic (score <70%) in match_items_task
- [X] T027 [US1] Add category blocking filter to match_items_task for performance optimization
- [X] T028 [US1] Add structured logging with metrics (items_processed, auto_matched, etc.) to match_items_task

---

## Phase 4: User Story 2 - Price & Availability Aggregation (Critical)

**Goal:** Implement FR-3 - Automatically calculate and maintain aggregate fields on products whenever linked supplier items change.

**Story:** As a system process, I want to recalculate product aggregates (min_price, availability) when supplier items are linked or prices change, so that catalog data is always accurate.

**Independent Test Criteria:**
- Given a linked item with lowest price → product.min_price equals that price
- Given any linked item with stock → product.availability is TRUE
- Recalculation completes within 10 seconds per product
- Aggregates update after auto-match task completes

### Tasks

- [X] T029 [US2] Create aggregation service module `services/python-ingestion/src/services/aggregation/__init__.py`
- [X] T030 [US2] Create calculate_product_aggregates function in `services/python-ingestion/src/services/aggregation/service.py`
- [X] T031 [US2] Implement MIN(current_price) query for min_price calculation
- [X] T032 [US2] Implement ANY(in_stock) query for availability calculation
- [X] T033 [US2] Create recalc_product_aggregates_task in `services/python-ingestion/src/tasks/matching_tasks.py`
- [X] T034 [US2] Add batch processing for multiple product_ids in recalc_product_aggregates_task
- [X] T035 [US2] Chain recalc_product_aggregates_task from match_items_task on auto-match
- [X] T036 [US2] Add trigger parameter logging for audit trail (auto_match, manual_link, price_change)

---

## Phase 5: User Story 3 - Characteristics Extractor (High)

**Goal:** Implement FR-2 - Extract technical specifications from supplier item text using pattern matching.

**Story:** As a system process, I want to extract technical specifications (voltage, power, weight, dimensions) from supplier item names, so that structured data is available for filtering and comparison.

**Independent Test Criteria:**
- Given "750W 220V" → extracted voltage=220, power_watts=750
- Given "2.5kg" → extracted weight_kg=2.5
- Given "30x20x10cm" → extracted dimensions_cm={length:30, width:20, height:10}
- Extraction does not overwrite existing manually-set characteristics

### Tasks

- [X] T037 [US3] Create FeatureExtractor abstract base class in `services/python-ingestion/src/services/extraction/extractors.py`
- [X] T038 [US3] Implement ElectronicsExtractor with voltage, power patterns in `services/python-ingestion/src/services/extraction/extractors.py`. Include validation logic to skip/discard invalid or ambiguous values (e.g., "TBD", "N/A", negative numbers, out-of-range values).
- [X] T039 [US3] Implement DimensionsExtractor with weight, dimensions patterns in `services/python-ingestion/src/services/extraction/extractors.py`. Include validation logic to skip/discard invalid or ambiguous values (e.g., "TBD", "N/A", negative dimensions, unrealistic measurements).
- [X] T040 [US3] Create EXTRACTOR_REGISTRY dictionary for extractor lookup in `services/python-ingestion/src/services/extraction/extractors.py`
- [X] T041 [US3] Create enrich_item_task function in `services/python-ingestion/src/tasks/matching_tasks.py`
- [X] T042 [US3] Implement merge logic to preserve existing characteristics in enrich_item_task
- [X] T043 [US3] Add extractor selection parameter to enrich_item_task

---

## Phase 6: User Story 4 - Manual Override Handling (High)

**Goal:** Implement FR-4 - Process manual link/unlink events from users and protect verified matches from automatic changes.

**Story:** As an admin/procurement user, I want to manually link/unlink items and have my changes protected from auto-matching, so that manually verified data is not overwritten.

**Independent Test Criteria:**
- Given a manual link → item becomes `verified_match`
- Given a `verified_match` item → auto-matcher skips it
- Given a manual unlink → both products' aggregates are recalculated
- Only admin role can reset `verified_match` to `unmatched`

### Tasks

- [X] T044 [US4] Create handle_manual_match_event task in `services/python-ingestion/src/tasks/matching_tasks.py`. Must support actions: `link` (manual link), `unlink` (manual unlink), `reset_match` (admin removes verified_match status), `approve_match` (review queue approval → verified_match), `reject_match` (review queue rejection → create new product)
- [X] T045 [US4] Implement manual link logic with verified_match status in handle_manual_match_event
- [X] T046 [US4] Implement manual unlink logic with previous_product_id tracking
- [X] T047 [US4] Add verified_match filter to match_items_task to skip protected items
- [X] T048 [US4] Chain recalc_product_aggregates_task for both old and new products on manual link/unlink
- [X] T049 [US4] Add audit logging with user_id and action type

---

## Phase 7: User Story 5 - Match Review Queue (Medium)

**Goal:** Implement FR-5 - Maintain a queue of potential matches requiring human review.

**Story:** As a procurement user, I want to see potential matches with confidence scores, so that I can approve or reject matches that the system is uncertain about.

**Independent Test Criteria:**
- Potential matches (70-94%) create review queue entries
- Review queue items include candidate_products with scores
- Items expire after 30 days (configurable)
- Approved matches become verified_match; rejected items create new products
- `get_review_queue_stats()` returns counts grouped by supplier_id and category_id
- `search_match_candidates()` filters by match_score range, date range, and category

### Tasks

- [X] T050 [US5] Add review queue creation to match_items_task for potential matches
- [X] T051 [US5] Include top 5 candidates with scores in candidate_products field
- [X] T052 [US5] Calculate expires_at based on MATCH_REVIEW_EXPIRATION_DAYS setting
- [X] T053 [US5] Create expire_review_queue_task in `services/python-ingestion/src/tasks/matching_tasks.py`
- [X] T054 [US5] Add cron schedule for expire_review_queue_task in worker settings
- [X] T055 [US5] Create `get_review_queue_stats()` in `services/python-ingestion/src/services/aggregation/service.py` - count pending/approved/rejected grouped by supplier_id and category_id
- [X] T056 [US5] Create `search_match_candidates()` in `services/python-ingestion/src/services/matching/matcher.py` - filter supplier_items by match_score range, created_at range, and category_id

> **Note (Bun API Integration):** Tasks T055 and T056 provide the Python service layer logic for review queue statistics and candidate searching. The corresponding HTTP endpoints will be implemented in the Bun API service (Phase 2 extension), which will call these functions via Redis queue messages. The Python logic must be ready before API implementation.

---

## Phase 8: Integration & Polish

**Goal:** Register all tasks with the worker, add integration tests, and finalize cross-cutting concerns.

**Independent Test Criteria:**
- All tasks registered and worker starts successfully
- End-to-end pipeline: ingest → match → enrich → aggregate
- Performance: >1000 items/minute throughput
- Error handling: failed tasks go to DLQ

### Tasks

- [X] T057 Update worker.py to register all new tasks (match_items, enrich_item, recalc_aggregates, handle_manual_match_event, expire_review_queue)
- [X] T058 Export all models from `services/python-ingestion/src/db/models/__init__.py`
- [X] T059 Export all services from `services/python-ingestion/src/services/__init__.py`
- [X] T060 Add chain from parse_task to match_items_task on successful ingestion. Additionally, when a price change is detected on a linked supplier item during parsing, chain `recalc_product_aggregates_task` for the associated product_id with trigger="price_change"
- [X] T061 [P] Create unit test file `services/python-ingestion/tests/unit/test_matcher.py` for RapidFuzzMatcher
- [X] T062 [P] Create unit test file `services/python-ingestion/tests/unit/test_extractors.py` for feature extractors
- [X] T063 [P] Create unit test file `services/python-ingestion/tests/unit/test_aggregation.py` for aggregation service
- [X] T064 Create integration test file `services/python-ingestion/tests/integration/test_matching_pipeline.py`
- [X] T065 Add performance test for >1000 items/minute throughput in integration tests
- [X] T066 Add concurrent worker test with SELECT FOR UPDATE SKIP LOCKED verification
- [X] T067 Update `.env.example` with new MATCH_* environment variables
- [X] T068 Add observability metrics logging (items_matched_total, matching_duration_seconds)

---

## Dependencies

### Task Dependencies Graph

```
Phase 1 (Setup)
  T001-T008 ──────┐
                  ▼
Phase 2 (Foundational)
  T009-T017 ──────┐
                  ▼
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
Phase 3 (US1: Matcher)    Phase 5 (US3: Extractor)
  T018-T028                   T037-T043
    │                           │
    └─────────────┬─────────────┘
                  ▼
Phase 4 (US2: Aggregation)
  T029-T036
    │
    ▼
Phase 6 (US4: Manual Override)
  T044-T049
    │
    ▼
Phase 7 (US5: Review Queue)
  T050-T056
    │
    ▼
Phase 8 (Integration & Polish)
  T057-T068
```

### Cross-Phase Dependencies

| Task | Depends On | Reason |
|------|------------|--------|
| T018 | T006 | MatchCandidate dataclass used by RapidFuzzMatcher |
| T022 | T015-T016 | ORM models required for task |
| T029 | T015 | Product model with new fields |
| T035 | T022, T033 | Chain aggregation after matching |
| T044 | T016, T017 | SupplierItem and MatchReviewQueue models |
| T050 | T017, T022 | Review queue model and match task |
| T055 | T017, T029 | Review queue and aggregation service for stats |
| T056 | T016, T018 | SupplierItem model and matcher service |
| T057 | T022, T033, T041, T044, T053 | All tasks must exist |

---

## Parallel Execution Opportunities

### Phase 1: Maximum Parallelism (5 parallel)
```
T001 (deps) → T002 (config)
              │
              └──┬── T003, T004, T005 (package inits) [P]
                 │
                 └── T006, T007, T008 (Pydantic models) [P]
```

### Phase 3-5: Cross-Story Parallelism
After Phase 2 completes, US1 (Matcher) and US3 (Extractor) can proceed in parallel:
```
           ┌── US1: T018-T028 (Matcher)
Phase 2 ───┤
           └── US3: T037-T043 (Extractor)
```

### Phase 8: Test Parallelism (3 parallel)
```
T061 (test_matcher.py) ─────┐
T062 (test_extractors.py) ──┼── [P]
T063 (test_aggregation.py) ─┘
```

---

## Implementation Strategy

### MVP Scope (Recommended First Milestone)
**Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2)**

This delivers:
- Core matching functionality (auto-match ≥95%)
- Price aggregation on products
- Minimum viable pipeline end-to-end

**Estimated effort:** 2-3 days

### Full Feature Scope
All phases (T001-T068)

**Estimated effort:** 6-7 days (per plan.md timeline)

---

## Summary

| Metric | Count |
|--------|-------|
| **Total Tasks** | 68 |
| **Setup Tasks (P1)** | 8 |
| **Foundational Tasks (P2)** | 9 |
| **US1 Tasks (Matcher)** | 11 |
| **US2 Tasks (Aggregation)** | 8 |
| **US3 Tasks (Extractor)** | 7 |
| **US4 Tasks (Manual Override)** | 6 |
| **US5 Tasks (Review Queue)** | 7 |
| **Integration Tasks (P8)** | 12 |
| **Parallelizable Tasks** | 14 |

---

## Validation Checklist

- [x] All tasks follow checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
- [x] All user story tasks have [US#] label
- [x] File paths specified for all implementation tasks
- [x] Dependencies clearly documented
- [x] Independent test criteria for each phase/story
- [x] MVP scope identified

---

**Ready for Implementation** ✅

