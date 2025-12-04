# Feature Plan: Semantic ETL Pipeline Refactoring

**Date:** 2025-12-04

**Status:** Draft

**Owner:** Development Team

---

## Overview

This feature refactors the data ingestion pipeline to use semantic (LLM-based) extraction, eliminating fragile rule-based parsing logic. The `python-ingestion` service becomes a pure data courier (downloading files), while `ml-analyze` becomes the intelligence layer (parsing, extracting, normalizing).

**Key Changes:**
- Remove all legacy pandas/regex parsing from `python-ingestion`
- Implement LLM-based extraction in `ml-analyze` using LangChain
- Add intelligent category matching with fuzzy fallback
- Support complex Excel layouts via Markdown grid representation

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility (SOLID-S):** `python-ingestion` focuses solely on file acquisition ("Data Courier"). `ml-analyze` owns all parsing intelligence. Clear separation prevents responsibility creep.
- **Open/Closed (SOLID-O):** New file formats and extraction patterns can be added by extending LLM prompts without modifying core logic.
- **Separation of Concerns:** Data fetching (Python courier) is decoupled from data understanding (ML/LLM). Each service has a single, well-defined purpose.
- **Strong Typing:** Pydantic models define extraction contracts. TypeScript interfaces ensure type safety across the API boundary.
- **KISS:** Leverage existing LLM capabilities rather than maintaining complex, brittle regex/pandas parsing logic. Simpler codebase with fewer edge cases.
- **DRY:** Single source of truth for extraction logic (ml-analyze). Eliminates duplicate parsing implementations across different file types.

**Violations/Exceptions:** None. This refactoring strengthens constitutional adherence by simplifying architecture.

**Gates Evaluation:**
- ✅ No architectural violations
- ✅ Reduces complexity (removes legacy parsers)
- ✅ Improves maintainability (single extraction service)
- ✅ Maintains service boundaries (courier pattern)

---

## Goals

- [ ] Remove all legacy parsing logic from `python-ingestion` service
- [ ] Implement LLM-based sheet structure analysis and product extraction
- [ ] Achieve >95% extraction accuracy on test supplier files
- [ ] Support complex Excel layouts (merged cells, multi-sheet files)
- [ ] Implement intelligent category matching with fuzzy fallback
- [ ] Process 500-row files in <3 minutes end-to-end

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- Image extraction from supplier files (deferred to future phase)
- Multi-file deduplication (cross-supplier matching remains in Phase 4)
- Real-time streaming ingestion (batch processing only)
- Custom LLM training or fine-tuning (use pre-trained Ollama models)
- Currency conversion (assume BYN, log others for manual review)
- Automated pricing logic or margin calculations

---

## Success Metrics

How will we measure success?

- **Extraction Accuracy:** >95% of products in test supplier files correctly extracted with all required fields
- **Category Match Rate:** >80% of extracted categories match existing categories (fuzzy match success)
- **Processing Speed:** Files with 500 rows processed in <3 minutes end-to-end
- **Deduplication Effectiveness:** <5% duplicate products remain after within-file deduplication
- **Error Resilience:** System handles malformed data without crashing (>99% uptime)

---

## User Stories

### Story 1: Admin Uploads Standard Supplier File

**As a** Marketbel admin
**I want** to upload an Excel file with a sheet named "Upload to site"
**So that** products are automatically extracted and added to the catalog

**Acceptance Criteria:**

- [ ] Only the "Upload to site" sheet is processed
- [ ] All 300 products are extracted with Name, Price, and Category
- [ ] Categories are matched against existing catalog with >85% fuzzy threshold
- [ ] New categories are created with `needs_review=true` flag
- [ ] Job completes in <2 minutes

### Story 2: Admin Uploads Multi-Sheet File

**As a** Marketbel admin
**I want** to upload an Excel file with multiple sheets
**So that** the system intelligently identifies and processes only product data sheets

**Acceptance Criteria:**

- [ ] Non-product sheets (e.g., "Instructions") are skipped
- [ ] All product sheets are processed
- [ ] Duplicate products across sheets are removed
- [ ] Job completes successfully

### Story 3: Admin Reviews New Categories

**As a** Marketbel admin
**I want** to see all categories that need review in the Admin UI
**So that** I can approve or merge them with existing categories

**Acceptance Criteria:**

- [ ] All categories with `needs_review=true` are listed
- [ ] Admin can approve (merge) or create as new category
- [ ] Approved categories are immediately available for matching

---

## Technical Approach

### Architecture

**High-Level Flow:**

```
[Admin Upload] → [Bun API] → [Redis: job created] → [python-ingestion: download]
                                                            ↓
[/shared/uploads/file.xlsx] ← download ← [python-ingestion: download_task]
                ↓                                          ↓
[ml-analyze reads file] ← HTTP POST ← [python-ingestion: ml_client]
                ↓
[SmartParserService] → [Markdown Converter] → [LangChain Extraction]
                ↓                                          ↓
[CategoryNormalizer] → [FuzzyMatcher] → [supplier_items table]
                ↓
[Redis: phase=complete] → [Bun API polls] → [Frontend displays results]
```

**Bun Service (API/User Logic):**

- **Responsibilities:** Job creation, status polling, retry triggers
- **Endpoints:**
  - `POST /admin/suppliers` (enqueue download task)
  - `GET /admin/sync/status` (poll job progress with phases)
  - `POST /admin/jobs/:id/retry` (retry failed jobs)
- **Data flow:** HTTP → Redis → Response

**Python Service (Data Courier Only):**

- **Responsibilities:** File download, metadata creation, ML service trigger
- **Tasks:**
  - `download_and_trigger_ml`: Download file → Save to `/shared/uploads` → POST to ml-analyze
  - `poll_ml_status`: Poll ml-analyze for completion
  - `cleanup_shared_files`: Remove old files (24h TTL)
  - `retry_job_task`: Retry failed jobs (max 3 attempts)
- **Data flow:** Redis → Download → Shared Volume → ml-analyze HTTP trigger
- **IMPORTANT:** NO parsing logic, NO pandas DataFrames, NO regex extraction

**ML-Analyze Service (Intelligence Layer):**

- **Responsibilities:** File parsing, LLM extraction, category normalization, DB writes
- **New Components:**
  - `SmartParserService`: Orchestrates parsing workflow
  - `MarkdownConverter`: Excel/CSV → Markdown table representation
  - `LangChainExtractor`: LLM-based product extraction with sliding window
  - `CategoryNormalizer`: Fuzzy matching + new category creation
- **Data flow:** HTTP request → Read file → Parse → Extract → Normalize → DB write

**Redis Queue Communication:**

- **Queue names:** `arq:queue` (existing)
- **Job state keys:** `job:{job_id}` (phase, progress, error)
- **Phases:** `downloading` → `analyzing` → `extracting` → `normalizing` → `complete` / `failed`
- **Message formats:** Existing Pydantic models (no changes)
- **Error handling:** Retry with exponential backoff, detailed error logging

**PostgreSQL Schema:**

- **Tables affected:**
  - `categories`: Add `parent_id` (FK self), `needs_review` (boolean), `is_active` (boolean)
  - `supplier_items`: Ensure `price_opt` (wholesale) and `price_rrc` (retail) columns exist
- **Migration plan:** Alembic migration in `ml-analyze` service

**Frontend (React + Vite + Tailwind v4.1):**

- **Components:**
  - `JobPhaseIndicator.tsx`: Display multi-phase progress (existing, Phase 8)
  - `SupplierStatusTable.tsx`: Enhanced with semantic ETL phases
  - `CategoryReviewPage.tsx`: NEW - Review `needs_review` categories
- **State management:** TanStack Query for job polling
- **API integration:** Existing job status endpoint returns new phases

### Design System

- [ ] Consulted `mcp 21st-dev/magic` for UI design elements (CategoryReviewPage)
- [ ] Collected documentation via `mcp context7` (LangChain, Ollama, RapidFuzz)
- [ ] Tailwind v4.1 CSS-first approach confirmed (no `tailwind.config.js`)

### Algorithm Choice

Following KISS principle:

**Smart Sheet Selection:**
- **Initial Implementation:** LLM analyzes sheet names, prioritizes "Upload to site", "Products", "Catalog", "Товары"
- **Complexity:** O(n) where n = number of sheets (linear scan)
- **Scalability Path:** N/A (sheet count is small, <10 typically)

**Markdown Grid Conversion:**
- **Initial Implementation:** openpyxl or pandas → Markdown table with pipe delimiters
- **Merged cells:** Repeat values or use rowspan/colspan indicators
- **Complexity:** O(rows × cols)

**LLM-Based Extraction:**
- **Approach:** Sliding window with 20-30 row chunks, 20% overlap to prevent data loss
- **Model:** Ollama llama3 (8k token context window)
- **Prompt:** Structured JSON output via LangChain `StructuredOutputParser`
- **Complexity:** O(n) where n = number of chunks
- **Scalability Path:** If LLM becomes bottleneck, batch multiple chunks in parallel

**Fuzzy Category Matching:**
- **Initial Implementation:** RapidFuzz `token_set_ratio` with 85% threshold
- **Complexity:** O(m × k) where m = extracted categories, k = existing categories
- **Optimization:** Cache category list in-memory, refresh on insert
- **Scalability Path:** If category count >10k, use embeddings + vector similarity

**Within-File Deduplication:**
- **Approach:** Hash-based dedup on normalized product name + price (1% tolerance)
- **Complexity:** O(n) with hash set
- **Keep:** First occurrence in file order

### Data Flow (Detailed)

```
┌───────────────────────────────────────────────────────────────────────┐
│ Admin UI: Upload file                                                 │
└─────────────┬─────────────────────────────────────────────────────────┘
              │ POST /admin/suppliers
              ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Bun API: Create job, enqueue download_and_trigger_ml                  │
└─────────────┬─────────────────────────────────────────────────────────┘
              │ Redis: job:{id} = { phase: 'pending' }
              ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Python Worker: download_and_trigger_ml task                           │
│   1. Download file (Google Sheets API → XLSX export)                  │
│   2. Save to /shared/uploads/{supplier_id}_{timestamp}.xlsx           │
│   3. Write metadata sidecar (.meta.json)                              │
│   4. Update Redis: phase = 'downloading' → 'analyzing'                │
│   5. HTTP POST → ml-analyze /analyze/file                             │
└─────────────┬─────────────────────────────────────────────────────────┘
              │ File in shared volume
              ▼
┌───────────────────────────────────────────────────────────────────────┐
│ ml-analyze: /analyze/file endpoint                                    │
│   1. Read file from /shared/uploads                                   │
│   2. SmartParserService.parse(file_path)                              │
│       a. Identify sheets (LLM: Structure Analysis)                    │
│       b. Convert to Markdown (MarkdownConverter)                      │
│       c. Extract products (LangChainExtractor: sliding window)        │
│       d. Normalize categories (CategoryNormalizer: fuzzy match)       │
│       e. Deduplicate products (within-file)                           │
│       f. Insert to supplier_items table                               │
│   3. Update Redis: phase = 'analyzing' → 'complete'                   │
│   4. Return job status                                                │
└─────────────┬─────────────────────────────────────────────────────────┘
              │
              ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Python Worker: poll_ml_status task (every 10s)                        │
│   Check Redis job state, update Bun API via DB writes                 │
└─────────────┬─────────────────────────────────────────────────────────┘
              │
              ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Frontend: Poll GET /admin/sync/status                                 │
│   Display: Downloading → Analyzing → Extracting → Normalizing → Done  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Technical Context

### Known Requirements

**Service Roles:**
- `python-ingestion`: Data courier only (download, trigger ML, poll status)
- `ml-analyze`: Intelligence layer (parse, extract, normalize, write DB)

**Technology Stack:**
- **LangChain:** `langchain-core` for prompt engineering and structured output parsing
- **LLM:** Ollama llama3 (already installed, Phase 7)
- **Embeddings:** Ollama nomic-embed-text (existing, not used for extraction, only for vector search)
- **Fuzzy Matching:** RapidFuzz (already installed, Phase 4)
- **Excel/CSV Parsing:** pandas or openpyxl (already installed)
- **Markdown Generation:** Custom converter (to be implemented)

**Data Contracts:**
- ExtractedProduct (Pydantic): name, description, wholesale_price, retail_price, category_path, raw_data
- ExtractionResult (Pydantic): products[], sheet_name, total_rows, successful_extractions, failed_extractions, duplicates_removed

**Database Schema Changes:**
- `categories` table: Add `parent_id INT (FK categories.id)`, `needs_review BOOLEAN DEFAULT false`, `is_active BOOLEAN DEFAULT true`
- `supplier_items` table: Ensure `price_opt DECIMAL(12,2)` and `price_rrc DECIMAL(12,2)` columns exist

### NEEDS CLARIFICATION

The following items require research before implementation:

1. **LangChain Prompt Engineering Best Practices**
   - How to design prompts for tabular data extraction?
   - How to enforce strict JSON schema output?
   - How to handle LLM hallucinations in product extraction?

2. **Sliding Window Chunk Size Optimization**
   - What is the optimal chunk size (rows) for llama3's 8k token context?
   - How much overlap (%) prevents data loss at boundaries?
   - How to handle products split across chunk boundaries?

3. **Markdown Table Representation for Merged Cells**
   - How to represent merged cells in Markdown that LLMs understand?
   - Should we use repeated values or special syntax (e.g., colspan indicators)?
   - How do popular libraries (pymupdf4llm) handle this?

4. **Category Hierarchy Creation Logic**
   - When LLM returns ["Parent", "Child"], should we create both if missing?
   - How to handle orphaned child categories (parent doesn't exist)?
   - Should `parent_id` be nullable or require root category?

5. **LangChain Model Selection and Configuration**
   - Which LangChain LLM wrapper to use for Ollama integration?
   - How to configure temperature, max_tokens, and other parameters?
   - How to handle LangChain retries vs our custom retry logic?

6. **Migration Strategy from Legacy Parsers**
   - Should we run both systems in parallel for validation?
   - How to handle rollback if semantic extraction fails?
   - What metrics to track during transition period?

7. **Error Handling for Partial Extractions**
   - If 80% of products extract successfully, is that "completed_with_errors" or "failed"?
   - How to surface partial results to admin users?
   - Should we insert partial results or rollback the entire job?

---

## Type Safety

### TypeScript Types

```typescript
// services/bun-api/src/types/job.types.ts

export type JobPhase =
  | 'pending'
  | 'downloading'
  | 'analyzing'
  | 'extracting'
  | 'normalizing'
  | 'complete'
  | 'failed'
  | 'completed_with_errors';

export interface JobStatus {
  job_id: string;
  supplier_id: number;
  phase: JobPhase;
  progress_percent: number;
  total_rows?: number;
  processed_rows?: number;
  successful_extractions?: number;
  failed_extractions?: number;
  duplicates_removed?: number;
  error_message?: string;
  created_at: Date;
  updated_at: Date;
}

export interface CategoryReviewItem {
  id: number;
  name: string;
  parent_id?: number;
  needs_review: boolean;
  is_active: boolean;
  supplier_id: number;
  created_at: Date;
}

export interface CategoryApprovalRequest {
  category_id: number;
  action: 'approve' | 'merge';
  merge_with_id?: number; // Required if action = 'merge'
}
```

### Python Types

```python
# services/ml-analyze/src/schemas/extraction.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from decimal import Decimal

class ExtractedProduct(BaseModel):
    """Product extracted from supplier file via LLM."""
    name: str = Field(..., min_length=1, description="Product name (required)")
    description: Optional[str] = Field(None, description="Product specs or description")
    wholesale_price: Optional[Decimal] = Field(None, ge=0, description="Wholesale price (opt)")
    retail_price: Decimal = Field(..., ge=0, description="Retail price (required)")
    category_path: List[str] = Field(default_factory=list, description="Category hierarchy")
    raw_data: Dict[str, any] = Field(default_factory=dict, description="Original row data")

    @validator('name')
    def normalize_name(cls, v):
        return v.strip()

    @validator('category_path')
    def normalize_categories(cls, v):
        return [c.strip() for c in v if c.strip()]

class ExtractionResult(BaseModel):
    """Result of file extraction process."""
    products: List[ExtractedProduct]
    sheet_name: str
    total_rows: int
    successful_extractions: int
    failed_extractions: int
    duplicates_removed: int

class CategoryMatchResult(BaseModel):
    """Result of category fuzzy matching."""
    extracted_name: str
    matched_id: Optional[int] = None
    matched_name: Optional[str] = None
    similarity_score: float
    action: str  # 'matched' | 'created' | 'skipped'
    needs_review: bool
```

```python
# services/python-ingestion/src/schemas/ml_client.py

from pydantic import BaseModel, HttpUrl
from typing import Optional

class MLAnalyzeRequest(BaseModel):
    """Request to ml-analyze service for file analysis."""
    file_path: str  # Absolute path in shared volume
    supplier_id: int
    job_id: str

class MLAnalyzeResponse(BaseModel):
    """Response from ml-analyze service."""
    job_id: str
    status: str  # 'queued' | 'processing' | 'complete' | 'failed'
    progress_percent: int
    message: Optional[str] = None
```

---

## Testing Strategy

- **Unit Tests:**
  - MarkdownConverter: Excel → Markdown conversion, merged cell handling
  - LangChainExtractor: Prompt construction, schema validation, chunk overlap logic
  - CategoryNormalizer: Fuzzy matching thresholds, hierarchy creation, deduplication
  - DeduplicationService: Hash-based dedup, price tolerance calculation

- **Integration Tests:**
  - ml-analyze `/analyze/file`: Full workflow with sample Excel/CSV files
  - LangChain + Ollama: Mock LLM responses to test extraction validation
  - CategoryNormalizer + PostgreSQL: Test category insertion and FK relationships

- **E2E Tests:**
  - Full ingestion flow: Admin upload → Download → ML analysis → Category matching → DB insertion → Frontend display
  - Error scenarios: Malformed file, LLM timeout, missing required fields, partial extraction
  - Deduplication: Files with known duplicates
  - Multi-sheet files: Mixed data types, priority sheet selection

- **Coverage Target:** ≥90% for extraction and matching logic (critical path)

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LLM extraction accuracy <95% | High | Medium | Run parallel testing with legacy parsers, validate on 10 test files before cutover |
| LLM response time >5s per chunk | Medium | Medium | Optimize chunk size, consider batching, add timeout and retry logic |
| Category duplication rate >10% | Medium | High | Lower fuzzy threshold to 80%, add admin UI for bulk category merging |
| llama3 context limit (8k tokens) insufficient | High | Low | Reduce chunk size, use smaller overlap, or upgrade to llama3.1 (128k context) |
| Migration breaks existing suppliers | High | Low | Feature flag toggle, rollback plan, keep legacy code for 1 release cycle |
| Category hierarchy creation errors | Medium | Medium | Add validation: parent must exist before child, UI for orphan resolution |
| Frontend performance with 1000+ pending review categories | Low | Low | Paginate CategoryReviewPage, add filters (supplier, date) |

---

## Dependencies

**Bun Packages:** (No new dependencies)

**Python Packages:**
- `langchain-core==0.3.21` - LangChain framework for prompt engineering
- `langchain-ollama==0.2.0` - Ollama integration for LangChain
- `openpyxl==3.1.5` - Excel file reading (alternative to pandas for cleaner API)
- `rapidfuzz==3.10.1` - Fuzzy string matching (already installed, Phase 4)

**External Services:**
- Ollama (llama3 model) - Already running, Phase 7
- PostgreSQL (pgvector extension) - Already enabled, Phase 7
- Redis - Already running, Phase 8

**Infrastructure:**
- Docker shared volume `/shared/uploads` - Already configured, Phase 8
- Environment variables:
  - `OLLAMA_BASE_URL=http://ollama:11434`
  - `OLLAMA_MODEL_LLM=llama3`
  - `FUZZY_MATCH_THRESHOLD=85`
  - `CHUNK_SIZE_ROWS=25` (NEW)
  - `CHUNK_OVERLAP_PERCENT=20` (NEW)

---

## Timeline

Implementation will proceed in phases:

| Phase | Tasks | Duration | Target Date |
|-------|-------|----------|-------------|
| **Phase 0: Research** | Resolve NEEDS CLARIFICATION items, generate research.md | 1 day | TBD |
| **Phase 1: Design** | Generate data-model.md, contracts/, quickstart.md | 1 day | TBD |
| **Phase 2: Database** | Alembic migration, category table updates | 0.5 days | TBD |
| **Phase 3: Markdown Converter** | Implement Excel/CSV → Markdown conversion | 1 day | TBD |
| **Phase 4: LangChain Extraction** | Implement SmartParserService, LangChainExtractor, sliding window | 2 days | TBD |
| **Phase 5: Category Normalization** | Implement CategoryNormalizer, fuzzy matching, hierarchy creation | 1.5 days | TBD |
| **Phase 6: Deduplication** | Implement within-file deduplication logic | 0.5 days | TBD |
| **Phase 7: Python Worker Cleanup** | Remove legacy parsers from python-ingestion | 0.5 days | TBD |
| **Phase 8: Frontend** | CategoryReviewPage, enhanced JobPhaseIndicator | 1 day | TBD |
| **Phase 9: Testing** | Unit, integration, E2E tests | 2 days | TBD |
| **Phase 10: Migration** | Parallel testing, cutover, monitoring | 1 day | TBD |

**Total Estimated Duration:** ~11 days

---

## Open Questions

These will be resolved during Phase 0 (Research):

- [ ] **Q1:** What is the optimal chunk size (rows) for llama3's 8k token context?
- [ ] **Q2:** How to represent merged cells in Markdown for LLM understanding?
- [ ] **Q3:** Should we create parent categories automatically or require manual creation?
- [ ] **Q4:** What LangChain prompt template works best for tabular extraction?
- [ ] **Q5:** How to handle partial extraction results (80% success rate)?
- [ ] **Q6:** What metrics to track during migration from legacy parsers?
- [ ] **Q7:** Should we add a feature flag for semantic ETL vs legacy parsing?

---

## References

- Feature Spec: `/specs/009-semantic-etl/spec.md`
- Phase 7 Spec (ml-analyze foundation): `/specs/007-ml-analyze/spec.md`
- Phase 8 Spec (courier pattern): `/specs/008-ml-ingestion-integration/spec.md`
- Phase 8 ADR (courier architecture): `/docs/adr/008-courier-pattern.md`
- LangChain Documentation: https://python.langchain.com/docs/get_started/introduction
- LangChain Ollama Integration: https://python.langchain.com/docs/integrations/llms/ollama
- Ollama Documentation: https://ollama.com/docs
- RapidFuzz Documentation: https://github.com/maxbachmann/RapidFuzz
- Openpyxl Documentation: https://openpyxl.readthedocs.io/

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
