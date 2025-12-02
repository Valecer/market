# Research: Product Matching & Data Enrichment Pipeline

**Date:** 2025-11-30  
**Feature:** 004-product-matching-pipeline  
**Status:** Complete

---

## Overview

This document captures research findings and technology decisions for Phase 4: Product Matching & Data Enrichment Pipeline. All decisions align with the project constitution and follow SOLID principles.

---

## Technology Decisions

### 1. Fuzzy String Matching Library: RapidFuzz

**Decision:** Use `rapidfuzz` library for all fuzzy string matching operations.

**Rationale:**
- **Performance:** Written in C++, 10-100x faster than pure Python alternatives like FuzzyWuzzy
- **API Compatibility:** Drop-in replacement for FuzzyWuzzy with identical function signatures
- **License:** MIT license (commercial-friendly)
- **Features:** Provides `WRatio`, `token_set_ratio`, and `process.extractOne` for efficient batch matching
- **Memory Efficiency:** `process.extract_iter` yields results lazily for large datasets

**Alternatives Considered:**
- `thefuzz` (FuzzyWuzzy fork): Slower performance, Python-only implementation
- `polyfuzz`: Overkill for our needs (includes ML models), larger dependency footprint
- Custom implementation: Unnecessary complexity given RapidFuzz's maturity

**Key API Usage:**

```python
from rapidfuzz import process, fuzz, utils

# Find best match with preprocessing
result = process.extractOne(
    query="Samsung Galaxy A54",
    choices=["Samsung Galaxy A54 5G 128GB", "Samsung Galaxy S22", "iPhone 14"],
    scorer=fuzz.WRatio,
    processor=utils.default_process,
    score_cutoff=70.0  # Minimum threshold
)
# Returns: ('Samsung Galaxy A54 5G 128GB', 95.0, 0)

# Get top N candidates for review queue
candidates = process.extract(
    query="Samsung A54",
    choices=product_names,
    scorer=fuzz.WRatio,
    processor=utils.default_process,
    limit=5,
    score_cutoff=70.0
)

# Batch comparison for performance
scores = process.cdist(queries, choices, scorer=fuzz.ratio)
```

**Best Practices:**
- Always use `processor=utils.default_process` for case-insensitive, whitespace-normalized matching
- Use `score_cutoff` parameter to filter low-confidence matches at the C++ level (faster than Python filtering)
- Use `fuzz.WRatio` for general product name matching (automatically selects best algorithm)
- Use `fuzz.token_set_ratio` when word order varies significantly

---

### 2. Matching Strategy Pattern

**Decision:** Implement `MatcherStrategy` interface following Open/Closed Principle (SOLID-O).

**Rationale:**
- Allows swapping matching algorithms without modifying core service code
- Enables future ML-based matching implementations
- Facilitates A/B testing of different algorithms
- Improves testability with mock implementations

**Interface Design:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

@dataclass
class MatchCandidate:
    """Data transfer object for match candidates."""
    product_id: UUID
    product_name: str
    score: float  # 0-100
    category_id: Optional[UUID] = None

@dataclass
class MatchResult:
    """Result of matching operation."""
    supplier_item_id: UUID
    match_status: str  # 'auto_matched', 'potential_match', 'unmatched'
    best_match: Optional[MatchCandidate] = None
    candidates: List[MatchCandidate] = None  # For potential matches
    match_score: Optional[float] = None

class MatcherStrategy(ABC):
    """Abstract interface for product matching algorithms."""
    
    @abstractmethod
    async def find_matches(
        self,
        item_name: str,
        category_id: Optional[UUID],
        candidates: List[dict]  # DTOs with 'id', 'name', 'category_id'
    ) -> List[MatchCandidate]:
        """Find matching products for a supplier item.
        
        Args:
            item_name: Name of supplier item to match
            category_id: Category for blocking (optional)
            candidates: List of product DTOs to compare against
            
        Returns:
            List of MatchCandidate sorted by score descending
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return unique identifier for this strategy."""
        pass
```

**Implementations:**
1. `RapidFuzzMatcher` - Current implementation using rapidfuzz
2. `EmbeddingMatcher` - Future ML-based implementation (Phase 5)

---

### 3. Feature Extraction Strategy Pattern

**Decision:** Implement `FeatureExtractor` interface with hardcoded regex patterns per KISS principle.

**Rationale:**
- Regex patterns are deterministic and fast
- Hardcoding patterns in Python classes avoids database complexity
- New extractors can be added without modifying existing code (SOLID-O)
- Each extractor has single responsibility (SOLID-S)

**Interface Design:**

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import re

class FeatureExtractor(ABC):
    """Abstract interface for extracting features from text."""
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """Extract features from text.
        
        Args:
            text: Input text (item name, description)
            
        Returns:
            Dictionary of extracted features (empty if none found)
        """
        pass
    
    @abstractmethod
    def get_extractor_name(self) -> str:
        """Return unique identifier for this extractor."""
        pass

class ElectronicsExtractor(FeatureExtractor):
    """Extracts electrical specifications: voltage, power, wattage."""
    
    # Patterns hardcoded per KISS principle
    VOLTAGE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Vv](?:olt)?s?(?:\s|$|,)', re.IGNORECASE)
    POWER_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Ww](?:att)?s?(?:\s|$|,)', re.IGNORECASE)
    KW_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Kk][Ww]', re.IGNORECASE)
    
    def extract(self, text: str) -> Dict[str, Any]:
        result = {}
        
        # Extract voltage
        voltage_match = self.VOLTAGE_PATTERN.search(text)
        if voltage_match:
            result['voltage'] = int(float(voltage_match.group(1)))
        
        # Extract power in watts
        power_match = self.POWER_PATTERN.search(text)
        if power_match:
            result['power_watts'] = int(float(power_match.group(1)))
        
        # Extract kilowatts (convert to watts)
        kw_match = self.KW_PATTERN.search(text)
        if kw_match and 'power_watts' not in result:
            result['power_watts'] = int(float(kw_match.group(1)) * 1000)
        
        return result
    
    def get_extractor_name(self) -> str:
        return "electronics"

class DimensionsExtractor(FeatureExtractor):
    """Extracts physical dimensions: weight, dimensions."""
    
    WEIGHT_KG_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Kk][Gg]', re.IGNORECASE)
    WEIGHT_G_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*[Gg](?:ram)?s?(?:\s|$|,)', re.IGNORECASE)
    DIMENSIONS_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?)\s*[Xx×]\s*(\d+(?:\.\d+)?)\s*[Xx×]\s*(\d+(?:\.\d+)?)\s*(?:cm|mm)?',
        re.IGNORECASE
    )
    
    def extract(self, text: str) -> Dict[str, Any]:
        result = {}
        
        # Extract weight in kg
        kg_match = self.WEIGHT_KG_PATTERN.search(text)
        if kg_match:
            result['weight_kg'] = float(kg_match.group(1))
        
        # Extract weight in grams (convert to kg)
        g_match = self.WEIGHT_G_PATTERN.search(text)
        if g_match and 'weight_kg' not in result:
            result['weight_kg'] = float(g_match.group(1)) / 1000
        
        # Extract dimensions
        dim_match = self.DIMENSIONS_PATTERN.search(text)
        if dim_match:
            result['dimensions_cm'] = {
                'length': float(dim_match.group(1)),
                'width': float(dim_match.group(2)),
                'height': float(dim_match.group(3))
            }
        
        return result
    
    def get_extractor_name(self) -> str:
        return "dimensions"
```

**Alternatives Considered:**
- Database-stored patterns: Adds complexity, harder to test, rarely changes
- Configuration file patterns: Similar complexity without type safety
- ML-based extraction: Overkill for structured patterns, reserved for Phase 5

---

### 4. Queue Task Architecture

**Decision:** Extend existing `arq` worker with new task types for matching pipeline.

**Rationale:**
- Leverages existing Phase 1 infrastructure (no new queue system)
- `arq` already configured with retry logic, DLQ, and monitoring
- Maintains separation of concerns (Python worker handles all data processing)
- Event-driven architecture enables decoupled aggregation updates

**New Task Types:**

1. **`match_items_task`** - Process batch of unmatched supplier items
2. **`enrich_item_task`** - Extract characteristics from single item
3. **`recalc_product_aggregates_task`** - Recalculate min_price/availability for product

**Task Chaining:**

```
[Parse Task] → [Match Items Task] → [Recalc Aggregates Task]
                    ↓
              [Enrich Item Task]
```

**Integration Points:**
- `parse_task` chains to `match_items_task` after successful ingestion
- Bun API publishes `recalc_product_aggregates_task` on manual link/unlink
- Matching service publishes `recalc_product_aggregates_task` on auto-match

---

### 5. Concurrency Control Strategy

**Decision:** Use PostgreSQL pessimistic locking with `SELECT FOR UPDATE SKIP LOCKED`.

**Rationale:**
- Prevents duplicate matches when multiple workers process same items
- `SKIP LOCKED` ensures workers don't block each other
- Native database feature (no additional infrastructure)
- Atomic operations within transactions

**Implementation:**

```python
async def get_unmatched_items_for_processing(
    session: AsyncSession,
    category_id: Optional[UUID],
    batch_size: int = 100
) -> List[SupplierItem]:
    """Get batch of unmatched items with pessimistic locking.
    
    Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate processing.
    """
    stmt = (
        select(SupplierItem)
        .where(SupplierItem.product_id.is_(None))
        .where(SupplierItem.match_status == 'unmatched')
        .order_by(SupplierItem.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    
    if category_id:
        # Apply blocking by category
        stmt = stmt.where(
            SupplierItem.characteristics['category_id'].astext == str(category_id)
        )
    
    result = await session.execute(stmt)
    return result.scalars().all()
```

---

### 6. Blocking Strategy for Performance

**Decision:** Block matching candidates by category to achieve >1000 items/minute throughput.

**Rationale:**
- Full catalog scan is O(n²) - unsustainable at scale
- Category blocking reduces comparison set by ~95% (assuming 50 categories)
- Items without category flagged for manual review instead of full scan
- Configurable per-supplier via metadata

**Performance Impact:**
- Without blocking: 10,000 products × 1,000 items = 10M comparisons
- With blocking: ~200 products × 1,000 items = 200K comparisons (50x reduction)

---

### 7. Threshold Configuration

**Decision:** Use environment variables for matching thresholds with sensible defaults.

**Configuration:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MATCH_AUTO_THRESHOLD` | 95.0 | Score >= this → auto-link |
| `MATCH_POTENTIAL_THRESHOLD` | 70.0 | Score >= this → potential match for review |
| `MATCH_BATCH_SIZE` | 100 | Items per matching batch |
| `REVIEW_EXPIRATION_DAYS` | 30 | Days before review items expire |

**Implementation:**

```python
# src/config.py
class MatchingSettings(BaseModel):
    """Matching pipeline configuration."""
    auto_threshold: float = Field(default=95.0, ge=0, le=100)
    potential_threshold: float = Field(default=70.0, ge=0, le=100)
    batch_size: int = Field(default=100, ge=1, le=1000)
    review_expiration_days: int = Field(default=30, ge=1, le=365)
    
    class Config:
        env_prefix = "MATCH_"
```

---

### 8. Aggregation Service Design

**Decision:** Calculate aggregates on-demand via background task, not triggers.

**Rationale:**
- Database triggers are harder to test and debug
- Background tasks allow batching multiple updates
- Consistent with existing Phase 1 architecture
- Enables audit logging of aggregate changes

**Aggregate Fields:**

| Field | Source | Calculation |
|-------|--------|-------------|
| `min_price` | `supplier_items.current_price` | `MIN(current_price)` WHERE active |
| `availability` | `supplier_items.characteristics.in_stock` | `ANY(in_stock = true)` |
| `mrp` | Placeholder | NULL (deferred to future phase) |

---

### 9. Match Status State Machine

**Decision:** Use PostgreSQL ENUM for match_status with explicit state transitions.

**States:**

```
unmatched (initial)
    ↓ [auto-match ≥95%]
auto_matched
    ↓ [admin confirms]
verified_match

unmatched (initial)
    ↓ [potential 70-94%]
potential_match
    ↓ [admin approves]
verified_match
    ↓ [admin rejects]
unmatched (creates new product)

verified_match
    ↓ [admin resets] (admin-only)
unmatched
```

**Business Rules:**
- `verified_match` items are SKIPPED by auto-matcher
- Only admin role can reset `verified_match` → `unmatched`
- State transitions are audit-logged

---

### 10. Observability & Metrics

**Decision:** Use existing `structlog` for structured logging with metrics counters.

**Metrics to Track:**

```python
# Counters (incrementing)
items_matched_total{match_type="auto|potential|new_product"}
items_flagged_for_review
new_products_created

# Histograms (timing)
matching_duration_seconds{category="..."}
extraction_duration_seconds{extractor="..."}
aggregation_duration_seconds

# Gauges (current state)
review_queue_depth{category="..."}
unmatched_items_backlog
```

**Alert Thresholds:**
- `unmatched_items_backlog > 10000` → Warning
- `matching_error_rate > 5%` → Critical

---

## Dependencies

### Python Packages (requirements.txt additions)

```text
# Product Matching Pipeline
rapidfuzz>=3.5.0  # Fuzzy string matching (C++ backend)
```

No additional packages required - uses existing `arq`, `sqlalchemy`, `pydantic`, `structlog`.

---

## Testing Strategy

### Unit Tests
- `MatcherStrategy` implementations with known inputs
- `FeatureExtractor` patterns with edge cases
- State transition validation
- Threshold logic

### Integration Tests
- End-to-end matching pipeline with Docker services
- Concurrent worker tests with `SELECT FOR UPDATE SKIP LOCKED`
- API → Redis → Worker → Database flow

### Performance Tests
- >1000 items/minute matching throughput
- <10 seconds aggregation recalculation
- Memory usage under batch processing

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Low match accuracy | High | Medium | Tune thresholds, add more patterns |
| Concurrent duplicate matches | High | Low | Pessimistic locking, unique constraints |
| Performance degradation at scale | Medium | Medium | Category blocking, batch processing |
| False positives in auto-match | High | Low | 95% threshold, admin review capability |

---

## References

- [RapidFuzz Documentation](https://maxbachmann.github.io/RapidFuzz/)
- [arq Documentation](https://arq-docs.helpmanual.io/)
- [PostgreSQL SELECT FOR UPDATE](https://www.postgresql.org/docs/current/explicit-locking.html)
- Phase 1 Data Model: `/specs/001-data-ingestion-infra/plan/data-model.md`
- Phase 2 Admin API: `/specs/002-api-layer/plan/contracts/admin-api.json`

---

**Approval:**
- [x] Research Complete - Ready for Data Model Phase

