# Feature Specification: Semantic ETL Pipeline Refactoring

**Version:** 1.0.0

**Last Updated:** 2025-12-04

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** `python-ingestion` focuses solely on file acquisition and delivery ("Data Courier"). `ml-analyze` owns all parsing intelligence ("Intelligence"). Clear separation prevents responsibility creep.
- **Separation of Concerns:** Data fetching (Python) is decoupled from data understanding (ML/LLM). Each service has a single, well-defined purpose.
- **Strong Typing:** Pydantic models define extraction contracts. TypeScript interfaces ensure type safety across the API boundary.
- **KISS:** Leverage existing LLM capabilities rather than maintaining complex, brittle regex/pandas parsing logic. Simpler codebase with fewer edge cases.
- **DRY:** Single source of truth for extraction logic (ml-analyze). Eliminates duplicate parsing implementations across different file types.

**Compliance Statement:**

This specification adheres to all constitutional principles by simplifying the architecture through clear responsibility boundaries and reducing code duplication.

---

## Overview

### Purpose

Refactor the data ingestion pipeline to use semantic (LLM-based) extraction, eliminating fragile rule-based parsing logic and improving data quality through intelligent understanding of diverse supplier file formats.

### Scope

**In Scope:**

- Remove all legacy pandas/regex parsing logic from `python-ingestion` service
- Implement LLM-based sheet structure analysis in `ml-analyze`
- Implement LLM-based product data extraction with sliding window processing
- Add intelligent category matching with fuzzy matching fallback
- Implement automatic category hierarchy creation
- Add deduplication logic within single file uploads
- Handle mixed/composite data fields (e.g., "Category | Name | Specs")
- Support Markdown/Text Grid representation for layout preservation

**Out of Scope:**

- Image extraction from supplier files (deferred)
- Multi-file deduplication (cross-supplier matching remains in Phase 4)
- Real-time streaming ingestion (batch processing only)
- Custom LLM training or fine-tuning (use pre-trained models)
- Currency conversion (assume BYN, log others for manual review)
- Automated pricing logic or margin calculations

---

## Functional Requirements

### FR-1: Data Courier Role for Python Ingestion

**Priority:** Critical

**Description:** The `python-ingestion` service must act strictly as a data courier, responsible only for downloading files and triggering analysis. All parsing intelligence is delegated to `ml-analyze`.

**Acceptance Criteria:**

- [ ] AC-1: No pandas DataFrame manipulation logic exists in `python-ingestion` codebase
- [ ] AC-2: No string pattern matching or regex parsing exists in `python-ingestion` for product extraction
- [ ] AC-3: File download tasks save files to shared volume and trigger `ml-analyze` via HTTP
- [ ] AC-4: Job status reflects courier responsibilities: "downloading", "triggering_analysis", "awaiting_ml_results"
- [ ] AC-5: Legacy parser modules (if any) are removed from `python-ingestion/src/parsers/`

**Dependencies:** Phase 8 courier pattern infrastructure, shared Docker volume

---

### FR-2: Smart Sheet Selection

**Priority:** Critical

**Description:** The system must intelligently identify which sheets contain product data, prioritizing sheets with specific names indicating they are upload-ready.

**Acceptance Criteria:**

- [ ] AC-1: LLM analyzes all sheet names in Excel/CSV files
- [ ] AC-2: If a sheet named "Upload to site" (case-insensitive) exists, only that sheet is processed
- [ ] AC-3: If multiple priority sheet names exist (e.g., "Upload to site", "Products for catalog"), the first match is selected
- [ ] AC-4: If no priority sheets exist, all sheets containing tabular product data are processed
- [ ] AC-5: Empty sheets (no data rows after header) are skipped
- [ ] AC-6: Sheets identified as metadata or configuration (e.g., "Settings", "Instructions") are skipped

**Dependencies:** None

**Notes:** Priority sheet names include: "Upload to site", "Products", "Catalog", "Export", "Товары" (Russian). System logs sheet selection reasoning for audit.

---

### FR-3: Markdown Grid Representation

**Priority:** High

**Description:** Excel/CSV data must be converted to a Markdown/Text Grid format that preserves visual layout, including merged cells and spatial relationships, before LLM analysis.

**Acceptance Criteria:**

- [ ] AC-1: Excel sheets are converted to Markdown tables with pipe-delimited columns
- [ ] AC-2: Merged cells are represented with colspan/rowspan indicators or repeated values
- [ ] AC-3: CSV files are converted to the same Markdown table format
- [ ] AC-4: Column alignment and spacing reflect the original visual structure
- [ ] AC-5: Header rows are clearly distinguished from data rows
- [ ] AC-6: The Markdown representation is human-readable and suitable for LLM context windows

**Dependencies:** pymupdf4llm (for PDF), openpyxl (for Excel)

---

### FR-4: LLM-Based Product Extraction

**Priority:** Critical

**Description:** The system must use a sliding window approach to feed Markdown chunks to the LLM for product data extraction into a strict JSON structure.

**Acceptance Criteria:**

- [ ] AC-1: Markdown data is split into overlapping chunks that fit within LLM context limits
- [ ] AC-2: Each chunk is processed to extract products with fields: Product Name, Description/Specs, Wholesale Price (optional), Retail Price (required), Category Path
- [ ] AC-3: LLM output follows a strict JSON schema validated by Pydantic
- [ ] AC-4: Numeric price values are extracted regardless of formatting (e.g., "1 234,56 р.", "$1,234.56", "1234.56 BYN")
- [ ] AC-5: Currency symbols are removed; all prices are assumed to be BYN
- [ ] AC-6: Non-BYN currencies (USD, EUR, RUB) are logged but not converted
- [ ] AC-7: Products without extractable Product Name or Retail Price are rejected with error logging
- [ ] AC-8: Category Path is extracted as an array of strings representing hierarchy (e.g., ["Electronics", "Laptops"])

**Dependencies:** FR-3 (Markdown representation), Ollama llama3 model

**Notes:** Sliding window overlap (default 20% of chunk size) prevents data loss at boundaries.

---

### FR-5: Mixed Field Splitting

**Priority:** Medium

**Description:** The system must intelligently split composite data fields (e.g., "Category | Product Name | Specs") into separate structured fields.

**Acceptance Criteria:**

- [ ] AC-1: LLM identifies pipe-delimited (|) or slash-delimited (/) composite fields
- [ ] AC-2: Composite fields are split into separate JSON properties
- [ ] AC-3: Split logic respects semantic meaning (e.g., "Parent / Child" becomes category hierarchy)
- [ ] AC-4: If split fails, the entire value is stored in the most relevant field with a warning log
- [ ] AC-5: Common patterns (e.g., "Name - Specs", "Category: Name") are handled correctly

**Dependencies:** FR-4 (LLM extraction)

---

### FR-6: Hybrid Category Governance

**Priority:** Critical

**Description:** The system must match extracted categories against existing categories using fuzzy matching. If no match is found, new categories are created with a review flag.

**Acceptance Criteria:**

- [ ] AC-1: Each extracted Category Path is fuzzy-matched against the `categories` table using RapidFuzz with >85% similarity threshold
- [ ] AC-2: Matching is case-insensitive and ignores leading/trailing whitespace
- [ ] AC-3: If a match is found, the product is linked to the existing category ID
- [ ] AC-4: If no match is found, a new category is created with `needs_review = true`
- [ ] AC-5: Category hierarchy is preserved: if LLM returns ["Parent", "Child"], both categories exist in the database with proper parent-child relationship
- [ ] AC-6: New categories inherit the language/locale of the supplier source
- [ ] AC-7: Admin UI displays a list of categories with `needs_review = true` for manual approval/merging

**Dependencies:** `categories` table with `needs_review` column, RapidFuzz library

**Notes:** Fuzzy matching threshold of 85% balances precision and recall. Lower thresholds may be explored if too many duplicates are created.

---

### FR-7: Within-File Deduplication

**Priority:** High

**Description:** The system must identify and remove duplicate products within a single file upload to prevent redundant entries in the catalog.

**Acceptance Criteria:**

- [ ] AC-1: Products are deduplicated based on Product Name (case-insensitive, normalized whitespace)
- [ ] AC-2: If duplicate names exist with identical Retail Price (within 1% tolerance), only one is kept
- [ ] AC-3: If duplicate names exist with different prices, all are kept with a warning log
- [ ] AC-4: Deduplication occurs before database insertion
- [ ] AC-5: Deduplication metrics (e.g., "10 duplicates removed from 250 products") are logged per job
- [ ] AC-6: The first occurrence in file order is kept; subsequent duplicates are discarded

**Dependencies:** FR-4 (product extraction)

**Notes:** Cross-supplier deduplication (Phase 4 product matching) remains separate and unchanged.

---

### FR-8: Error Handling and Validation

**Priority:** High

**Description:** The system must gracefully handle extraction failures, malformed data, and LLM errors without blocking the entire ingestion pipeline.

**Acceptance Criteria:**

- [ ] AC-1: Products that fail extraction (missing required fields) are logged to `parsing_logs` with error details
- [ ] AC-2: LLM timeouts or API errors trigger retry logic (max 3 retries with exponential backoff)
- [ ] AC-3: If an entire file fails analysis after retries, job status is set to "failed" with detailed error message
- [ ] AC-4: Partial success is supported: if 80% of products extract successfully, the job is marked "completed_with_errors"
- [ ] AC-5: Extraction errors include row/chunk identifiers for debugging
- [ ] AC-6: Malformed JSON responses from LLM are caught and logged

**Dependencies:** `parsing_logs` table, job state management (Redis)

---

## Non-Functional Requirements

### NFR-1: Performance

- LLM extraction throughput: >10 products/second on average hardware
- File processing time: <5 minutes for files up to 1000 rows
- Sliding window processing: Chunk size optimized to fit LLM context limits (~8k tokens for llama3)
- Fuzzy matching: <50ms per category lookup

### NFR-2: Scalability

- Support files with up to 10,000 rows without memory issues
- Horizontal scaling: Multiple `ml-analyze` instances can process different files concurrently
- Chunk-based processing prevents memory overflow on large files

### NFR-3: Reliability

- LLM API retry policy: 3 retries with exponential backoff (1s, 2s, 4s)
- Graceful degradation: If LLM is unavailable, job is queued for retry
- No data loss: Failed extractions are logged and can be manually reviewed
- Idempotency: Re-running the same file produces the same results

### NFR-4: Observability

- Structured logs for each extraction phase: sheet selection, chunk processing, category matching, deduplication
- Metrics: extraction success rate, LLM response time, fuzzy match hit rate
- Job progress tracking: "X of Y chunks processed"
- Debug mode: Log Markdown chunks and LLM prompts/responses

### NFR-5: Maintainability

- LLM prompts are externalized and version-controlled
- Extraction schema (Pydantic model) is centralized and reusable
- No hardcoded parsing rules or regex patterns
- Clear separation between Markdown generation and LLM extraction

---

## Success Criteria

1. **Zero Legacy Parsing Logic:** No pandas, regex, or rule-based parsing code remains in `python-ingestion` service
2. **Extraction Accuracy:** >95% of products in test supplier files are correctly extracted with all required fields
3. **Category Match Rate:** >80% of extracted categories match existing categories (fuzzy match success rate)
4. **Processing Speed:** Files with 500 rows are processed in <3 minutes end-to-end
5. **Error Resilience:** System handles files with malformed data (missing columns, merged cells) without crashing
6. **Deduplication Effectiveness:** <5% duplicate products remain after within-file deduplication
7. **Admin Visibility:** All new categories with `needs_review=true` are visible in Admin UI within 1 second of creation

---

## User Scenarios & Testing

### Scenario 1: Standard Supplier File Upload

**Given:** Admin uploads an Excel file with a sheet named "Upload to site" containing 300 products

**When:** The ingestion job is triggered

**Then:**
- Only the "Upload to site" sheet is processed
- All 300 products are extracted with Name, Price, and Category
- Categories are matched against existing catalog with >85% fuzzy match threshold
- 5 new categories are created with `needs_review=true` flag
- Job completes with status "completed" in <2 minutes
- Admin sees 5 categories pending review in the UI

### Scenario 2: Multi-Sheet File with Mixed Data

**Given:** Admin uploads an Excel file with sheets: "Instructions", "Products", "Pricing"

**When:** The ingestion job is triggered

**Then:**
- "Instructions" sheet is skipped (identified as non-product data)
- "Products" and "Pricing" sheets are analyzed and merged
- LLM extracts products from both sheets
- Deduplication logic removes 10 duplicate products across sheets
- Job completes successfully

### Scenario 3: Complex Merged Cells Layout

**Given:** Supplier file uses merged cells for category headers spanning multiple product rows

**When:** The file is converted to Markdown Grid and processed

**Then:**
- Merged cells are represented with repeated values or indicators
- LLM correctly infers category for all products under merged header
- Category hierarchy is preserved (e.g., "Electronics" > "Laptops" > "Gaming")

### Scenario 4: Mixed Field Splitting

**Given:** Supplier file has a column "Category | Product Name | Specs"

**When:** LLM processes the Markdown chunk

**Then:**
- Composite field is split into separate JSON fields: `category_path`, `name`, `description`
- Products are inserted with correct field mapping
- No data loss occurs

### Scenario 5: LLM Failure and Retry

**Given:** LLM service is temporarily unavailable during chunk processing

**When:** ml-analyze attempts extraction

**Then:**
- First attempt fails with timeout error
- System retries 3 times with exponential backoff
- After 3 failures, job status is set to "failed"
- Admin can manually retry the job from UI
- Detailed error message indicates "LLM service unavailable"

### Scenario 6: Fuzzy Category Matching

**Given:** Existing category "Motorcycles" exists in database

**When:** LLM extracts category "Motorcycle" (singular) from supplier file

**Then:**
- Fuzzy match succeeds with >85% similarity
- Product is linked to existing "Motorcycles" category
- No duplicate category is created

### Scenario 7: Category Review Workflow

**Given:** 15 new categories with `needs_review=true` were created during last sync

**When:** Admin opens the Category Management page

**Then:**
- All 15 categories are listed with review flag
- Admin can approve (merge with existing) or create as new
- Approved categories have `needs_review=false` and are available for matching

---

## Data Models

### Python Service: Extraction Schema

```python
# src/ingest/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List

class ExtractedProduct(BaseModel):
    name: str = Field(..., min_length=1, description="Product name")
    description: Optional[str] = Field(None, description="Product description or specifications")
    wholesale_price: Optional[float] = Field(None, ge=0, description="Wholesale price in BYN")
    retail_price: float = Field(..., ge=0, description="Retail price in BYN (required)")
    category_path: List[str] = Field(default_factory=list, description="Category hierarchy, e.g., ['Electronics', 'Laptops']")
    raw_data: dict = Field(default_factory=dict, description="Original row data for debugging")

class ExtractionResult(BaseModel):
    products: List[ExtractedProduct]
    sheet_name: str
    total_rows: int
    successful_extractions: int
    failed_extractions: int
    duplicates_removed: int
```

### Database: Categories Table Update

```sql
-- Migration: Add needs_review column to categories table
ALTER TABLE categories
ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
```

---

## Algorithm Specification

Following the KISS principle, we leverage existing LLM capabilities:

**LLM-Based Extraction Algorithm:**

- **Approach:** Use llama3 (via Ollama) with structured output prompts
- **Complexity:** O(n) where n = number of chunks (linear processing)
- **Justification:** LLMs handle diverse formats, merged cells, and mixed fields without custom code. Simpler than maintaining rule-based parsers.
- **Limitations:** LLM response time (~1-3s per chunk), requires Ollama service availability, token limits require chunking

**Fuzzy Matching Algorithm:**

- **Approach:** RapidFuzz with token_set_ratio scorer
- **Complexity:** O(m × k) where m = extracted categories, k = existing categories
- **Threshold:** 85% similarity
- **Justification:** Fast, deterministic, no training required. Handles typos and plural forms.

**Future Evolution:**

- **Trigger:** If category duplicate rate >10% or manual review queue >100 items
- **Migration Path:** Fine-tune embedding model on approved category mappings, use vector similarity for matching

---

## Error Handling

### ml-analyze Service

```python
# Error handling for LLM extraction
try:
    result = llm_client.extract_products(markdown_chunk)
    validate_extraction(result)
except LLMTimeoutError as e:
    logger.warning(f"LLM timeout on chunk {chunk_id}, retrying...")
    retry_with_backoff(extract_products, chunk_id, max_retries=3)
except ValidationError as e:
    logger.error(f"Invalid extraction schema: {e}")
    log_to_parsing_logs(job_id, chunk_id, error=str(e))
except Exception as e:
    logger.error(f"Unexpected error during extraction: {e}")
    raise
```

**Error Codes:**

- `SHEET_SELECTION_FAILED`: Unable to identify product sheets
- `LLM_TIMEOUT`: LLM API did not respond within timeout
- `VALIDATION_ERROR`: Extracted data does not match Pydantic schema
- `FUZZY_MATCH_ERROR`: Category matching failed
- `DEDUPLICATION_ERROR`: Error during deduplication logic

---

## Testing Requirements

### Unit Tests

- **ml-analyze:** Test Markdown grid generation, LLM prompt construction, fuzzy matching logic, deduplication algorithm
- **python-ingestion:** Test file download, metadata sidecar creation, ml-analyze HTTP client

### Integration Tests

- **API:** Test `/analyze/file` endpoint with sample Excel/CSV files
- **LLM:** Mock Ollama responses to test extraction schema validation
- **Fuzzy Matching:** Test category matching with known similar/dissimilar pairs

### E2E Tests

- Full ingestion flow: Upload Excel → Download → Markdown conversion → LLM extraction → Category matching → Database insertion
- Error scenarios: Malformed file, LLM timeout, missing required fields
- Deduplication: Files with known duplicates

**Coverage Target:** ≥90% for extraction and matching logic (critical path)

---

## Deployment

### Environment Variables

```bash
# ml-analyze Service
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL_EMBED=nomic-embed-text
OLLAMA_MODEL_LLM=llama3
FUZZY_MATCH_THRESHOLD=85
CHUNK_SIZE_TOKENS=7000
CHUNK_OVERLAP_PERCENT=20

# python-ingestion Service (no change)
ML_ANALYZE_URL=http://ml-analyze:8001
```

### Migration Strategy

1. **Phase 1:** Deploy ml-analyze with new extraction endpoints (backward compatible)
2. **Phase 2:** Update python-ingestion to remove legacy parsers and use ml-analyze
3. **Phase 3:** Run parallel testing: legacy vs. semantic extraction on test suppliers
4. **Phase 4:** Full cutover, remove legacy code
5. **Phase 5:** Monitor extraction accuracy and category match rates for 1 week

### Rollback Plan

**Trigger Conditions:**

- Extraction accuracy <90%
- Job failure rate >10%
- LLM service unavailable for >1 hour

**Rollback Steps:**

1. Revert python-ingestion to legacy parsers (keep as fallback branch)
2. Disable LLM extraction feature flag
3. Investigate and fix issues
4. Retest before re-deployment

---

## Documentation

- [ ] Update `CLAUDE.md` with Phase 9 overview and Semantic ETL architecture
- [ ] Create ADR: "ADR-009: Semantic ETL with LLM-Based Extraction"
- [ ] Update API documentation for ml-analyze extraction endpoints
- [ ] Inline code comments for LLM prompt templates
- [ ] Admin UI help text for category review workflow

---

## Exceptions & Deviations

**None**

---

## Appendix

### References

- Phase 7 spec: `/specs/007-ml-analyze/spec.md`
- Phase 8 spec: `/specs/008-ml-ingestion-integration/spec.md`
- Ollama documentation: https://ollama.com/docs
- RapidFuzz documentation: https://github.com/maxbachmann/RapidFuzz

### Glossary

- **Data Courier:** Service role focused solely on data acquisition and delivery, no processing logic
- **Semantic ETL:** ETL (Extract, Transform, Load) process that uses semantic understanding (LLM) rather than rule-based parsing
- **Markdown Grid:** Markdown table representation preserving visual layout of Excel/CSV data
- **Sliding Window:** Technique for processing large files by breaking into overlapping chunks
- **Fuzzy Matching:** Approximate string matching using similarity algorithms
- **Needs Review:** Flag indicating a database entity (e.g., category) requires manual admin approval

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
