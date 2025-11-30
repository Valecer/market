# Feature Plan: Product Matching & Data Enrichment Pipeline

**Date:** 2025-11-30

**Status:** Planning Complete

**Owner:** AI Agent

---

## Overview

This feature implements an automated product matching pipeline that links supplier items to unified products in the catalog, extracts technical specifications from item text, and maintains accurate aggregate pricing. The pipeline extends the existing Python worker (Phase 1) with new services and queue tasks.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

### Principle 1: Single Responsibility (SOLID-S) ✅
- **MatchingService:** Only handles product matching logic
- **ExtractionService:** Only handles feature extraction
- **AggregationService:** Only handles aggregate calculations
- **Queue Tasks:** Each task has one purpose (match, enrich, recalculate)

### Principle 2: Open/Closed (SOLID-O) ✅
- **MatcherStrategy interface:** New algorithms can be added without modifying existing code
- **FeatureExtractor interface:** New extractors can be added without modifying core service
- Future ML-based matching can be implemented as new strategy

### Principle 3: Liskov Substitution (SOLID-L) ✅
- All `MatcherStrategy` implementations honor the same contract
- All `FeatureExtractor` implementations return consistent data structures
- Test doubles can replace production implementations

### Principle 4: Interface Segregation (SOLID-I) ✅
- `MatcherStrategy` has minimal interface (find_matches, get_strategy_name)
- `FeatureExtractor` has minimal interface (extract, get_extractor_name)
- No fat interfaces that force unnecessary method implementations

### Principle 5: Dependency Inversion (SOLID-D) ✅
- Services depend on abstract interfaces, not concrete implementations
- Matching service receives DTOs, not database models
- Queue tasks use dependency injection for Redis and database sessions

### Principle 6: KISS ✅
- Start with RapidFuzz fuzzy matching (deterministic, fast)
- ML-based matching deferred to Phase 5
- Regex patterns hardcoded in classes (no database complexity)
- Simple threshold-based decision logic

### Principle 7: DRY ✅
- Reusable strategy interfaces across matching and extraction
- Centralized configuration in settings module
- Shared Pydantic models for validation

### Principle 8: Separation of Concerns ✅
- Python worker handles all data processing (matching, extraction, aggregation)
- Bun API publishes events for manual operations
- Services communicate only via Redis queues

### Principle 9: Strong Typing ✅
- Pydantic models for all queue messages
- SQLAlchemy ORM models with type hints
- Dataclasses for DTOs (MatchCandidate, MatchResult)

### Principle 10: Design System Consistency ✅
- N/A (no frontend components in this phase)

**Violations/Exceptions:** None

---

## Goals

- [x] Automatically match unlinked supplier items to existing products (FR-1)
- [x] Extract technical specifications from item text (FR-2)
- [x] Maintain accurate aggregate pricing and availability (FR-3)
- [x] Handle manual override events from Bun API (FR-4)
- [x] Create review queue for uncertain matches (FR-5)
- [x] Achieve >1000 items/minute matching throughput (NFR-1)

---

## Non-Goals

Explicitly out of scope for this phase:

- Machine learning-based matching (Phase 5)
- Multi-language text extraction
- Image-based product matching
- MRP calculation (placeholder only)
- Frontend UI for review queue (Phase 3 scope)

---

## Success Metrics

- **Catalog Unification Rate:** >90% of items auto-linked within 24 hours
- **Manual Review Reduction:** <10% items require review
- **Processing Speed:** 10,000 items matched in <10 minutes
- **Data Quality:** min_price accurate to 1 cent
- **Accuracy:** >99% correct linkage in random sample of 100

---

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Bun API Service                          │
│  (Manual link/unlink events published to Redis)                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ Redis LPUSH
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Redis Queue (arq)                           │
│  ┌────────────────┬────────────────┬───────────────────────┐   │
│  │ match_items    │ enrich_item    │ recalc_aggregates     │   │
│  │ _task          │ _task          │ _task                 │   │
│  └────────────────┴────────────────┴───────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Python Worker Service                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Services Layer                        │   │
│  │  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │   │
│  │  │ MatchingService│ │ExtractionService│ │AggregationSvc│ │   │
│  │  │ (RapidFuzz)    │ │ (Regex)        │ │ (SQL)        │ │   │
│  │  └────────────────┘ └────────────────┘ └──────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Database Layer                        │   │
│  │  SQLAlchemy ORM + PostgreSQL (with locking)             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL                                │
│  ┌───────────────┬───────────────┬──────────────────────────┐  │
│  │ products      │ supplier_items│ match_review_queue       │  │
│  │ (+min_price)  │ (+match_status│ (NEW)                    │  │
│  │ (+availability│  +match_score)│                          │  │
│  └───────────────┴───────────────┴──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Python Service (Data Processing)

**Responsibilities:**
- Fuzzy string matching using RapidFuzz
- Feature extraction using regex patterns
- Aggregate calculation (min_price, availability)
- Review queue management

**Processing Logic:**
1. `match_items_task`: SELECT unmatched items FOR UPDATE SKIP LOCKED
2. Compare against products in same category (blocking strategy)
3. Apply threshold logic: ≥95% → auto, 70-94% → review, <70% → new product
4. Chain to `enrich_item_task` and `recalc_product_aggregates_task`

**Data Flow:**
```
Parse Task → Match Items Task → Enrich Item Task
                     │
                     └──→ Recalc Aggregates Task
```

### Redis Queue Communication

**Queue Names:**
- `arq:queue:default` - All matching pipeline tasks
- `arq:dlq:dlq` - Dead letter queue for failed tasks

**Message Formats:**
- See `/plan/contracts/queue-messages.json`

**Error Handling:**
- Exponential backoff: 1s, 5s, 25s
- Max retries: 3
- Failed tasks routed to DLQ

### PostgreSQL Schema

**Tables Affected:**
- `products` - Add min_price, availability, mrp columns
- `supplier_items` - Add match_status, match_score, match_candidates columns
- `match_review_queue` - NEW table for pending reviews

**Migration Plan:**
- Single Alembic migration: `002_add_matching_pipeline.py`
- Includes enum types, columns, indexes, constraints

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **Initial Implementation:** RapidFuzz WRatio with preprocessing
- **Scalability Path:** Embedding-based matching when scale requires (Phase 5)

---

## Type Safety

### Python Types (Pydantic + Dataclasses)

```python
@dataclass
class MatchCandidate:
    product_id: UUID
    product_name: str
    score: float  # 0-100
    category_id: Optional[UUID] = None

class MatchItemsTaskMessage(BaseModel):
    task_id: str
    category_id: Optional[UUID] = None
    batch_size: int = Field(default=100, ge=1, le=1000)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=1, le=10)
```

### SQLAlchemy Models

```python
class MatchStatus(PyEnum):
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    POTENTIAL_MATCH = "potential_match"
    VERIFIED_MATCH = "verified_match"

class SupplierItem(Base):
    match_status: Mapped[MatchStatus]
    match_score: Mapped[Decimal | None]
    match_candidates: Mapped[Dict[str, Any] | None]
```

---

## Testing Strategy

- **Unit Tests:** Matcher strategies, extractors, threshold logic
- **Integration Tests:** Full pipeline with Docker services, concurrent workers
- **Performance Tests:** >1000 items/minute, <10s aggregation
- **Coverage Target:** ≥85% for business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Low match accuracy | High | Medium | Tune thresholds, add review queue |
| Concurrent duplicate matches | High | Low | SELECT FOR UPDATE SKIP LOCKED |
| Performance degradation | Medium | Medium | Category blocking, batch processing |
| False positives in auto-match | High | Low | 95% threshold, admin review capability |

---

## Dependencies

- **Python Packages:** `rapidfuzz>=3.5.0`
- **External Services:** None (uses existing Redis, PostgreSQL)
- **Infrastructure:** No changes (extends existing Docker services)

---

## Timeline

| Phase | Tasks | Duration | Target |
|-------|-------|----------|--------|
| Phase 1 | Database migration, models | 1 day | Day 1 |
| Phase 2 | Matching service + task | 2 days | Day 3 |
| Phase 3 | Extraction service + task | 1 day | Day 4 |
| Phase 4 | Aggregation service + task | 1 day | Day 5 |
| Phase 5 | Integration tests | 1 day | Day 6 |
| Phase 6 | Performance testing | 1 day | Day 7 |

---

## Open Questions

- [x] ~~Concurrent processing strategy~~ → SELECT FOR UPDATE SKIP LOCKED
- [x] ~~Verified match admin-only reset~~ → Yes, admin role only
- [x] ~~Backpressure handling~~ → Accept all, FIFO, alert on backlog
- [x] ~~Items without category~~ → Flag with "needs_category" status

---

## References

- Research: `/specs/004-product-matching-pipeline/plan/research.md`
- Data Model: `/specs/004-product-matching-pipeline/plan/data-model.md`
- Queue Contracts: `/specs/004-product-matching-pipeline/plan/contracts/queue-messages.json`
- Quickstart: `/specs/004-product-matching-pipeline/plan/quickstart.md`
- Phase 1 Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Phase 2 Admin API: `/specs/002-api-layer/plan/contracts/admin-api.json`

---

## Generated Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Research | `/plan/research.md` | ✅ Complete |
| Data Model | `/plan/data-model.md` | ✅ Complete |
| Queue Contracts | `/plan/contracts/queue-messages.json` | ✅ Complete |
| Quickstart | `/plan/quickstart.md` | ✅ Complete |

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
