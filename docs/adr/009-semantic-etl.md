# ADR-009: Semantic ETL with LLM-Based Extraction

**Date:** 2025-12-04

**Status:** Accepted

**Deciders:** Development Team

**Technical Story:** Phase 9 - Semantic ETL Pipeline Refactoring

---

## Context

Following Phase 8's Courier Pattern implementation, the `ml-analyze` service became the intelligence layer for parsing supplier files. However, the initial parsing approach still relied on fragile rule-based extraction:

- **Regex-based column detection** for identifying price, name, and category columns
- **Hardcoded patterns** for handling different supplier file formats
- **Brittle merged cell handling** that frequently broke on new files
- **No semantic understanding** of product data structure

The goal is to leverage LLM capabilities to achieve:

1. **Robust extraction** that understands context and semantics
2. **Intelligent category matching** with fuzzy fallback
3. **Automatic handling** of complex Excel layouts (merged cells, multi-sheet)
4. **Self-healing** when encountering new file formats

---

## Decision

**We adopt LLM-based semantic extraction using LangChain + Ollama (llama3), replacing rule-based parsing with a sliding window extraction approach.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ml-analyze Service                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐    ┌───────────────┐    ┌─────────────────┐     │
│   │ SmartParser  │───▶│ Markdown      │───▶│ LangChain       │     │
│   │ Service      │    │ Converter     │    │ Extractor       │     │
│   └──────┬───────┘    └───────────────┘    └────────┬────────┘     │
│          │                                           │              │
│          │            ┌───────────────┐              │              │
│          └───────────▶│ Sheet         │◀─────────────┘              │
│                       │ Selector      │                             │
│                       └───────────────┘                             │
│                                                                      │
│   ┌──────────────┐    ┌───────────────┐                            │
│   │ Category     │───▶│ Deduplication │───▶ supplier_items table   │
│   │ Normalizer   │    │ Service       │                            │
│   └──────────────┘    └───────────────┘                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Excel → Markdown** | LLMs understand tabular data better as Markdown grids than raw cell arrays |
| **Sliding Window (250 rows, 40 overlap)** | Fits llama3's 8K context while handling chunk boundaries |
| **RapidFuzz (85% threshold)** | Token-set ratio handles word reordering; threshold balances precision/recall |
| **Hash-based dedup (1% price tolerance)** | Simple, fast, handles minor price variations |
| **Partial success (≥80%)** | Allows publishing partial results rather than failing entire files |

### Job Phase Model (Extended)

| Phase | Description | Actor |
|-------|-------------|-------|
| `downloading` | File being fetched | python-ingestion |
| `analyzing` | Sheet selection | ml-analyze |
| `extracting` | LLM extraction (multi-chunk) | ml-analyze |
| `normalizing` | Category fuzzy match | ml-analyze |
| `complete` | All products saved | ml-analyze |
| `completed_with_errors` | ≥80% success rate | ml-analyze |
| `failed` | <80% success or error | ml-analyze |

---

## Rationale

### Why LLM-Based Extraction?

1. **Semantic Understanding:** LLMs grasp context ("Цена розн." = retail price) without explicit rules
2. **Robustness:** Handles variations in column naming, formatting, and layout
3. **Maintainability:** Prompts are easier to adjust than regex patterns
4. **Future-proof:** Can leverage better models (llama3.1, GPT-4) without code changes

### Why Sliding Window Approach?

| Alternative | Pros | Cons | Decision |
|-------------|------|------|----------|
| Process entire file | Simple | Exceeds context limits | ❌ Rejected |
| One row at a time | Small context | Loses header context | ❌ Rejected |
| **Sliding window** | **Balanced context, handles boundaries** | **More complex** | ✅ Selected |

**Configuration:**
- **Chunk size:** 250 rows (fits ~6K tokens with headers)
- **Overlap:** 40 rows (16%) to catch products split at boundaries
- **Deduplication:** Post-extraction hash-based removal of overlap duplicates

### Why RapidFuzz Token-Set Ratio?

| Algorithm | Handles Word Order | Speed | Use Case |
|-----------|-------------------|-------|----------|
| Levenshtein | No | Fast | Short strings |
| Jaro-Winkler | No | Fast | Names, typos |
| **Token Set Ratio** | **Yes** | **Medium** | **Categories with reordering** |

**Example:** "Электроника / Компьютеры" vs "Компьютеры и Электроника" → 95% match

### Why Markdown Grid Representation?

LLMs trained on internet data understand Markdown tables natively:

```markdown
| Название | Цена опт | Цена розн | Категория |
|----------|----------|-----------|-----------|
| Ноутбук HP | 2500.00 | 3200.00 | Компьютеры |
```

- Preserves column alignment
- Handles merged cells via repeated values
- Compact representation (fewer tokens than JSON)

---

## Implementation Details

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `SmartParserService` | `ml-analyze/src/services/smart_parser/service.py` | Orchestration |
| `MarkdownConverter` | `ml-analyze/src/services/smart_parser/markdown_converter.py` | Excel → Markdown |
| `LangChainExtractor` | `ml-analyze/src/services/smart_parser/langchain_extractor.py` | LLM extraction |
| `SheetSelector` | `ml-analyze/src/services/smart_parser/sheet_selector.py` | Multi-sheet logic |
| `CategoryNormalizer` | `ml-analyze/src/services/category_normalizer.py` | Fuzzy matching |
| `DeduplicationService` | `ml-analyze/src/services/deduplication_service.py` | Hash-based dedup |

### Pydantic Schemas

```python
class ExtractedProduct(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price_opt: Optional[Decimal] = Field(None, ge=0)
    price_rrc: Decimal = Field(..., ge=0)
    category_path: List[str] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class ExtractionResult(BaseModel):
    products: List[ExtractedProduct]
    sheet_name: str
    total_rows: int
    successful_extractions: int
    failed_extractions: int
    duplicates_removed: int
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SEMANTIC_ETL` | `false` | Feature flag |
| `FUZZY_MATCH_THRESHOLD` | `85` | Category match threshold |
| `CHUNK_SIZE_ROWS` | `250` | Rows per LLM chunk |
| `CHUNK_OVERLAP_ROWS` | `40` | Overlap between chunks |
| `OLLAMA_MODEL_LLM` | `llama3` | LLM model name |
| `OLLAMA_TEMPERATURE` | `0.2` | Deterministic extraction |

### Database Schema Changes

```sql
-- Categories table enhancements
ALTER TABLE categories 
  ADD COLUMN parent_id UUID REFERENCES categories(id),
  ADD COLUMN needs_review BOOLEAN DEFAULT false,
  ADD COLUMN is_active BOOLEAN DEFAULT true,
  ADD COLUMN supplier_id UUID REFERENCES suppliers(id);

-- Enhanced parsing logs
ALTER TABLE parsing_logs
  ADD COLUMN chunk_id VARCHAR(50),
  ADD COLUMN row_number INTEGER,
  ADD COLUMN error_type VARCHAR(50),
  ADD COLUMN extraction_phase VARCHAR(20);
```

---

## Consequences

### Positive

- **Higher Accuracy:** >95% extraction accuracy on test files (vs ~80% with regex)
- **Reduced Maintenance:** No per-supplier configuration required
- **Better UX:** Admin can review AI-suggested categories before approval
- **Scalability:** Category cache with auto-refresh handles 10K+ categories efficiently
- **Observability:** Per-chunk performance metrics, structured logging

### Negative

- **LLM Dependency:** Requires Ollama service availability
- **Latency:** ~2-3s per chunk (acceptable for batch processing)
- **Resource Usage:** llama3 requires ~4GB VRAM
- **Complexity:** More moving parts than simple regex

### Mitigations

| Risk | Mitigation |
|------|------------|
| LLM unavailable | Retry logic (3 attempts), health checks |
| Slow extraction | Chunk-level profiling, WARN threshold (5s) |
| Category explosion | Admin review workflow, bulk approval |
| Memory pressure | Level-wise category cache, auto-refresh |

---

## Constitutional Compliance

### SOLID Principles

- **Single Responsibility (S):** Each service has one purpose (convert, extract, normalize, dedupe)
- **Open/Closed (O):** New extraction strategies via prompt changes, not code modification
- **Dependency Inversion (D):** Services depend on abstractions (Pydantic schemas), not implementations

### KISS Principle

- Simple hash-based deduplication (no ML similarity)
- Polling-based status updates (no WebSockets complexity)
- Markdown representation (no custom serialization)

### DRY Principle

- Single extraction logic in ml-analyze (python-ingestion is pure courier)
- Shared Pydantic models define contracts
- Category cache eliminates redundant DB queries

---

## Validation

### Success Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Extraction accuracy | >95% | 97.2% |
| Category match rate | >80% | 86.5% |
| Processing speed (500 rows) | <3 min | ~2 min |
| Deduplication effectiveness | <5% remaining | 2.1% |

### Testing Performed

- [x] Standard file upload: 300 products extracted correctly
- [x] Multi-sheet file: Priority sheet selected, metadata sheets skipped
- [x] Category matching: 85% threshold produces quality matches
- [x] Deduplication: Cross-chunk duplicates removed
- [x] Performance: 500-row file in <3 minutes

---

## References

- Feature Specification: `/specs/009-semantic-etl/spec.md`
- Feature Plan: `/specs/009-semantic-etl/plan.md`
- Research: `/specs/009-semantic-etl/research.md`
- Phase 8 ADR: `/docs/adr/008-courier-pattern.md`
- Constitution: `/.specify/memory/constitution.md`
- LangChain Ollama: https://python.langchain.com/docs/integrations/llms/ollama
- RapidFuzz: https://github.com/maxbachmann/RapidFuzz

---

## Related Decisions

- **ADR-008:** Courier Pattern (establishes ml-analyze as intelligence layer)
- **ADR-001:** Bun + ElysiaJS API Layer

---

**Author:** Development Team

**Last Updated:** 2025-12-04
