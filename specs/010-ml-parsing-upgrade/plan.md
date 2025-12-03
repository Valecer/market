# Feature Plan: ML Parsing Service Upgrade

**Date:** 2025-12-03

**Status:** In Progress

**Owner:** Engineering Team

---

## Overview

Enhance the ML-Analyze parsing service with two-stage LLM parsing strategy, secure file path-based API for shared volume access, composite product name parsing, and comprehensive price/currency extraction. This upgrade improves parsing accuracy by ~15%, reduces token usage by ~40%, and adds dual pricing support from Phase 9 schema.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility (SOLID-S):** Each parsing stage handles one concern—Stage A: structure detection, Stage B: data extraction. Utility functions (name parser, price parser, file reader) each have single responsibilities.

- **Open/Closed (SOLID-O):** Two-stage parsing extends existing `TableNormalizer` pattern without modifying stable code. New utilities are additive, not modifications.

- **Liskov Substitution (SOLID-L):** Extended `NormalizedRow` maintains backward compatibility with deprecated field syncing. All existing parsers continue working unchanged.

- **Interface Segregation (SOLID-I):** `StructureAnalysis` and `ParsingMetrics` are narrow, focused models. No fat interfaces introduced.

- **Dependency Inversion (SOLID-D):** Parsing service depends on abstractions (prompts, models) not concrete LLM implementation. File reader abstracted from path validation.

- **KISS:** Two-stage parsing simplifies LLM context management vs single-pass. Delimiter-based name parsing before complex NLP. Simple path validation with `pathlib.resolve()`.

- **DRY:** Reuses existing parser infrastructure (`TableNormalizer`, `ParserFactory`). Extends `NormalizedRow` rather than creating new models. Currency mapping centralized in single dictionary.

- **Separation of Concerns:** LLM reasoning isolated from file I/O. Shared volume access decoupled from parsing logic. Prompt templates separate from chain execution.

- **Strong Typing:** Pydantic models for all parsed data (StructureAnalysis, NormalizedRow, ParsingMetrics). TypeBox schemas for API contracts.

**Violations/Exceptions:** None

---

## Goals

- [x] Implement file path-based API accepting `file_path` parameter for shared volume
- [x] Design two-stage LLM parsing strategy with STRUCTURE_ANALYSIS and EXTRACTION prompts
- [x] Create composite name parser splitting on "|" delimiter
- [x] Implement currency symbol extraction and ISO 4217 mapping
- [x] Support dual price extraction (retail_price, wholesale_price)
- [x] Track parsing quality metrics (tokens, timing, field rates)
- [x] Maintain backward compatibility with existing `file_url` parameter

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- No changes to Bun API proxy layer
- No database schema modifications (uses Phase 9 schema)
- No image/vision parsing (remains stubbed)
- No real-time streaming (maintains queue-based pattern)
- No multi-language product name NLP detection
- No WebSocket push notifications for job status

---

## Success Metrics

How will we measure success?

- **Parsing Accuracy:** 90% correct field extraction on test document set (vs 75% baseline)
- **Token Efficiency:** 40% reduction in LLM token usage compared to single-pass
- **Composite Name Handling:** 95% correct split on pipe-delimited strings
- **Currency Recognition:** 99% accuracy on RUB, USD, EUR detection
- **Processing Time:** <3 minutes for documents under 1000 rows
- **Error Rate:** <2% of parseable rows result in parsing errors

---

## User Stories

### Story 1: Admin Triggers File Analysis from Shared Volume

**As a** Admin User
**I want** to analyze supplier files already downloaded to shared volume
**So that** I can avoid re-downloading and process files faster

**Acceptance Criteria:**

- [x] API accepts `file_path` parameter pointing to shared volume
- [x] Path traversal attacks blocked (no `../` sequences)
- [x] Appropriate error returned if file doesn't exist
- [x] Backward compatibility maintained with `file_url`

### Story 2: Parse Composite Product Names

**As a** System (Automated)
**I want** composite product strings split into category/name/description
**So that** product data is properly structured

**Acceptance Criteria:**

- [x] Strings containing "|" split correctly
- [x] First segment maps to category (with hierarchy support via "/" or ">")
- [x] Second segment maps to product name
- [x] Third+ segments concatenate as description
- [x] Empty segments skipped gracefully

### Story 3: Extract Prices with Currency

**As a** System (Automated)
**I want** prices extracted with currency symbols mapped to ISO codes
**So that** pricing data is standardized

**Acceptance Criteria:**

- [x] ₽, $, € symbols recognized
- [x] Text indicators (руб, dollars, euros) recognized
- [x] Both retail and wholesale prices extracted when present
- [x] Currency stored per-row in `currency_code` field

---

## Technical Approach

### Architecture

High-level architecture decisions and service interactions.

**ML-Analyze Service (Data Processing):**

- Responsibilities:
  - Accept `file_path` from shared Docker volume
  - Execute two-stage LLM parsing (Structure → Extraction)
  - Parse composite names and extract prices/currency
  - Generate embeddings and match products
  - Track and report parsing metrics

- Endpoints:
  - `POST /analyze/file` - Extended with `file_path`, `default_currency`, `composite_delimiter`
  - `GET /analyze/status/{job_id}` - Extended with `metrics` field

- Data flow:
  ```
  file_path → validate_path → read_file → Stage A (structure) → Stage B (extract) → NormalizedRow[] → DB
  ```

**Python Worker (Courier Pattern - Phase 8):**

- Responsibilities unchanged: Downloads files to shared volume, triggers ML-Analyze
- No modifications required for Phase 10

**Bun API (Proxy Layer):**

- No changes required
- Passes through `file_path` to ML-Analyze

**PostgreSQL Schema:**

- No changes required
- Uses Phase 9 fields: `retail_price`, `wholesale_price`, `currency_code`

**Frontend (React):**

- Future: Display parsing metrics in admin panel
- Out of scope for Phase 10 implementation

### Design System

- [x] Consulted `mcp 21st-dev/magic` for UI design elements - N/A (backend only)
- [x] Collected documentation via `mcp context7` - Research complete
- [x] Tailwind v4.1 CSS-first approach confirmed - N/A (backend only)

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **Two-Stage LLM:** Simple sequential async calls (not LangChain chains)
- **Composite Name Parsing:** String split + positional mapping
- **Currency Extraction:** Regex + dictionary mapping
- **Price Column Detection:** Keyword matching

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Two-Stage Parsing Flow                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   POST /analyze/file                                                         │
│   { file_path: "/shared/uploads/file.xlsx", supplier_id: "..." }            │
│          │                                                                   │
│          │ 1. Validate path                                                  │
│          ▼                                                                   │
│   ┌──────────────┐                                                           │
│   │ SecureReader │ ──► Check within /shared/uploads                          │
│   │              │ ──► Check file exists & size                              │
│   └──────┬───────┘                                                           │
│          │                                                                   │
│          │ 2. Read file                                                      │
│          ▼                                                                   │
│   ┌──────────────┐      ┌─────────────────┐                                 │
│   │ Parser       │ ────►│ Raw Table Data  │                                 │
│   │ (Excel/PDF)  │      │ list[list[str]] │                                 │
│   └──────────────┘      └────────┬────────┘                                 │
│                                  │                                           │
│          ┌───────────────────────┤                                           │
│          │                       │                                           │
│          │ 3. Stage A: first N   │ 4. Use structure for                      │
│          │    rows as sample     │    targeted extraction                    │
│          ▼                       ▼                                           │
│   ┌──────────────┐      ┌─────────────────┐                                 │
│   │ LLM: Llama3  │      │ LLM: Llama3     │                                 │
│   │ STRUCTURE_   │      │ EXTRACTION_     │                                 │
│   │ ANALYSIS     │      │ PROMPT          │                                 │
│   └──────┬───────┘      └────────┬────────┘                                 │
│          │                       │                                           │
│          ▼                       ▼                                           │
│   ┌──────────────┐      ┌─────────────────┐                                 │
│   │ Structure    │      │ Raw Extracted   │                                 │
│   │ Analysis     │      │ JSON Array      │                                 │
│   │ {            │      │ [               │                                 │
│   │   header_rows│      │   { name, sku,  │                                 │
│   │   data_start │      │     price, ...} │                                 │
│   │   col_map    │      │ ]               │                                 │
│   │ }            │      └────────┬────────┘                                 │
│   └──────────────┘               │                                           │
│                                  │ 5. Post-process                           │
│                                  ▼                                           │
│                         ┌─────────────────┐                                 │
│                         │ Post-Processor  │                                 │
│                         │ - parse_composite│                                │
│                         │ - extract_price │                                 │
│                         │ - map_currency  │                                 │
│                         └────────┬────────┘                                 │
│                                  │                                           │
│                                  ▼                                           │
│                         ┌─────────────────┐                                 │
│                         │ NormalizedRow[] │                                 │
│                         │ - name          │                                 │
│                         │ - retail_price  │                                 │
│                         │ - wholesale_price│                                │
│                         │ - currency_code │                                 │
│                         │ - category_path │                                 │
│                         └────────┬────────┘                                 │
│                                  │                                           │
│                                  │ 6. Save to DB                             │
│                                  ▼                                           │
│                         ┌─────────────────┐                                 │
│                         │ supplier_items  │                                 │
│                         │ PostgreSQL      │                                 │
│                         └─────────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Type Safety

### Python Types

```python
# src/schemas/domain.py - Extended models
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Annotated, Any

class ColumnMapping(BaseModel):
    """Column index to field purpose mapping."""
    name_column: int | None = None
    sku_column: int | None = None
    retail_price_column: int | None = None
    wholesale_price_column: int | None = None
    category_column: int | None = None
    unit_column: int | None = None

class StructureAnalysis(BaseModel):
    """Stage A output: document structure understanding."""
    header_rows: list[int]
    data_start_row: int
    data_end_row: int
    column_mapping: ColumnMapping
    confidence: float
    detected_currency: str | None = None

class NormalizedRow(BaseModel):
    """Extended with pricing and composite fields."""
    name: str
    retail_price: Decimal | None = None
    wholesale_price: Decimal | None = None
    currency_code: str | None = None
    category_path: list[str] = Field(default_factory=list)
    raw_composite: str | None = None
    # ... existing fields

class ParsingMetrics(BaseModel):
    """Quality metrics for parsing job."""
    total_rows: int
    parsed_rows: int
    skipped_rows: int = 0
    error_rows: int = 0
    stage_a_tokens: int = 0
    stage_b_tokens: int = 0
    duration_ms: int
    field_extraction_rates: dict[str, float] = Field(default_factory=dict)
```

### Request/Response Types

```python
# src/schemas/requests.py
class FileAnalysisRequest(BaseModel):
    file_path: str | None = None  # NEW: Direct path
    file_url: HttpUrl | str | None = None  # Deprecated
    supplier_id: UUID
    file_type: Literal["pdf", "excel", "csv"]
    default_currency: str | None = None  # NEW
    composite_delimiter: str = "|"  # NEW

# src/schemas/responses.py
class FileAnalysisResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "complete", "failed"]
    message: str
    metrics: ParsingMetrics | None = None  # NEW
```

---

## Testing Strategy

- **Unit Tests:**
  - `test_file_reader.py` - Path validation, traversal prevention
  - `test_name_parser.py` - Composite name splitting
  - `test_price_parser.py` - Currency extraction, price parsing
  - `test_prompt_templates.py` - Prompt formatting

- **Integration Tests:**
  - Two-stage parsing with real Excel files
  - API endpoint with file_path parameter
  - Full pipeline with mock LLM responses

- **E2E Tests:**
  - Admin uploads file → shared volume → ML-analyze → DB
  - Verify dual pricing extracted correctly

- **Coverage Target:** ≥80% for new utility modules

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Stage A returns wrong structure | High | Medium | Fallback to full-document parsing if confidence < 0.7 |
| LLM returns invalid JSON | Medium | Medium | Retry with explicit JSON reminder, max 3 attempts |
| Path traversal attack | Critical | Low | Strict validation with resolve() + prefix check |
| Currency not recognized | Low | Low | Default to supplier currency or null |
| Composite delimiter varies | Low | Medium | Make delimiter configurable per request |

---

## Dependencies

- **Python Packages:** No new packages required
  - Existing: langchain-ollama, pydantic, openpyxl, pymupdf4llm
  
- **External Services:**
  - Ollama with llama3 model (existing)
  - PostgreSQL with pgvector (existing)
  
- **Infrastructure:**
  - Shared Docker volume at `/shared/uploads` (Phase 8)
  - New env vars: `STRUCTURE_CONFIDENCE_THRESHOLD`, `STRUCTURE_SAMPLE_ROWS`

---

## Timeline

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| Phase 0 | Research & Design | 1 day | Complete |
| Phase 1 | Data model, contracts, quickstart | 1 day | Complete |
| Phase 2 | Implementation | 2 days | TBD |
| Phase 3 | Testing & Integration | 1 day | TBD |

---

## Open Questions

- [x] ~~What fallback strategy for failed Stage A?~~ → Full-document parsing with confidence < 0.7
- [x] ~~How to handle mixed-currency documents?~~ → Per-row currency_code field
- [x] ~~Max file size for two-stage parsing?~~ → 50MB default, configurable

---

## References

- [Research Document](./research.md)
- [Data Model](./data-model.md)
- [API Contract](./contracts/analyze-file.openapi.yaml)
- [Quickstart Guide](./quickstart.md)
- [Phase 7 ML-Analyze Spec](/specs/007-ml-analyze/spec.md)
- [Phase 8 Integration Spec](/specs/008-ml-ingestion-integration/spec.md)
- [Phase 9 Pricing Spec](/specs/009-advanced-pricing-categories/spec.md)

---

## Implementation Files

### New Files to Create

| File | Purpose |
|------|---------|
| `src/utils/file_reader.py` | Secure file path validation and reading |
| `src/utils/name_parser.py` | Composite product name parsing |
| `src/utils/price_parser.py` | Price and currency extraction |
| `src/services/two_stage_parser.py` | Two-stage LLM parsing orchestration |

### Files to Modify

| File | Changes |
|------|---------|
| `src/schemas/domain.py` | Add StructureAnalysis, extend NormalizedRow, add ParsingMetrics |
| `src/schemas/requests.py` | Add file_path, default_currency, composite_delimiter |
| `src/schemas/responses.py` | Add metrics field |
| `src/rag/prompt_templates.py` | Add STRUCTURE_ANALYSIS_PROMPT, EXTRACTION_PROMPT |
| `src/api/routes/analyze.py` | Handle file_path parameter |
| `src/config/settings.py` | Add STRUCTURE_CONFIDENCE_THRESHOLD, STRUCTURE_SAMPLE_ROWS |

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
