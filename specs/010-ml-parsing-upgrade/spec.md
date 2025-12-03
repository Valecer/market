# Feature Specification: ML Parsing Service Upgrade

**Version:** 1.0.0

**Last Updated:** 2025-12-03

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Each parsing stage handles one concern—structure detection vs. data extraction
- **Separation of Concerns:** LLM reasoning isolated from file I/O; shared volume access decoupled from parsing logic
- **Strong Typing:** Pydantic models for all parsed data; TypeBox schemas for currency and pricing fields
- **KISS:** Two-stage parsing simplifies LLM context management; delimiter-based parsing before complex NLP
- **DRY:** Reuse existing parser infrastructure; extend NormalizedRow rather than creating new models

**Compliance Statement:**

This specification adheres to all constitutional principles. The upgrade extends existing capabilities while maintaining backward compatibility with the Phase 7 architecture.

---

## Overview

### Purpose

Enhance the ML-Analyze parsing service to improve accuracy and efficiency when processing complex supplier documents. The upgrade introduces intelligent two-stage parsing, shared volume file access, composite product name handling, and comprehensive price/currency extraction.

### Scope

**In Scope:**

- File path-based API interface for shared Docker volume access
- Two-stage LLM parsing: structure analysis followed by targeted data extraction
- Composite product name parsing with delimiter-based field mapping
- Currency symbol recognition and standardized code mapping
- Dual price extraction (retail and wholesale pricing)
- Backward compatibility with existing Phase 7 API consumers

**Out of Scope:**

- Changes to the Bun API proxy layer (consumers remain unchanged)
- Modification of database schema (uses existing pricing fields from Phase 9)
- Image/vision parsing enhancements (remains as stubbed interface)
- Multi-language product name detection (uses existing delimiter strategy)
- Real-time streaming of parsing results (maintains queue-based pattern)

---

## User Scenarios & Testing

### Scenario 1: Admin Triggers File Analysis from Shared Volume

**Actor:** Admin User

**Precondition:** Supplier file downloaded to shared volume by python-ingestion worker (Phase 8 courier pattern)

**Flow:**

1. Admin initiates sync for a supplier in the UI
2. Python-ingestion downloads file to `/shared/uploads/{supplier_id}_{timestamp}_{filename}`
3. Worker calls ML-Analyze API with the file path
4. ML-Analyze reads file from shared volume
5. Two-stage parsing extracts structured product data
6. Results written to database; Admin sees parsed items in UI

**Expected Outcome:** Products appear in supplier items list with correctly parsed names, categories, and prices

### Scenario 2: Complex Product Name Parsing

**Actor:** System (Automated)

**Precondition:** Source document contains composite product strings like "Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"

**Flow:**

1. Parser encounters composite string with "|" delimiters
2. System splits string into segments
3. First segment maps to category path
4. Second segment maps to product name
5. Third+ segments concatenate as description/specifications

**Expected Outcome:** 
- Category: "Electric Bicycle"
- Name: "Shtenli Model Gt11"
- Description: "Li-ion 48V 15Ah"

### Scenario 3: Multi-Currency Price Extraction

**Actor:** System (Automated)

**Precondition:** Source document contains prices with various currency symbols (₽, $, €)

**Flow:**

1. Parser identifies price cells in document
2. Currency symbol extracted and mapped to ISO code (₽→RUB, $→USD, €→EUR)
3. Numeric value extracted and stored separately
4. Both retail and wholesale prices identified when present

**Expected Outcome:** Prices stored with correct numeric values and standardized currency codes

### Scenario 4: Two-Stage Structure Detection

**Actor:** System (Automated)

**Precondition:** PDF or Excel file with complex table structure (merged headers, varying row formats)

**Flow:**

1. Stage A: LLM receives document sample and identifies:
   - Header row indices
   - Data row start index
   - Column purpose mapping
2. Stage B: Using Stage A analysis, parser extracts only relevant rows
3. Irrelevant rows (totals, disclaimers, empty) are skipped

**Expected Outcome:** Parser processes only product data rows with correct column interpretation

---

## Functional Requirements

### FR-1: File Path-Based API Interface

**Priority:** Critical

**Description:** Modify the `/analyze/file` endpoint to accept a local file path instead of URLs. The service reads files directly from a Docker shared volume, enabling zero-copy file handoff from the python-ingestion worker.

**Acceptance Criteria:**

- [ ] AC-1.1: API accepts `file_path` parameter as a string path (e.g., `/shared/uploads/supplier-data.xlsx`)
- [ ] AC-1.2: Service validates file path is within allowed directory (`/shared/uploads` or configured mount point)
- [ ] AC-1.3: Service returns appropriate error if file does not exist or is unreadable
- [ ] AC-1.4: Path traversal attacks are prevented (no `../` sequences allowed)
- [ ] AC-1.5: Existing `file_url` parameter remains supported for backward compatibility (deprecated but functional)
- [ ] AC-1.6: File size validation enforced before processing (configurable limit, default 50MB)

**Dependencies:** Phase 8 shared volume infrastructure

### FR-2: Two-Stage LLM Parsing Strategy

**Priority:** Critical

**Description:** Implement a two-stage parsing approach where the LLM first analyzes document structure to identify header and data rows, then performs targeted extraction only on identified data rows. This optimizes context window usage and improves extraction accuracy.

**Acceptance Criteria:**

- [ ] AC-2.1: Stage A sends document sample (first N rows) to LLM for structure analysis
- [ ] AC-2.2: LLM returns structured response identifying:
  - Header row indices (may be multi-row headers)
  - First data row index
  - Last data row index (or "end of document")
  - Column purpose mapping (which column is name, price, etc.)
- [ ] AC-2.3: Stage B uses Stage A results to extract data from identified rows only
- [ ] AC-2.4: Stage B sends focused prompts with column context from Stage A
- [ ] AC-2.5: Total LLM tokens used is measurably lower than single-stage approach on equivalent documents
- [ ] AC-2.6: System handles documents where Stage A returns uncertain results (falls back to full-document parsing)
- [ ] AC-2.7: Stage A results are cached for retry scenarios within same job

**Dependencies:** Ollama LLM service (llama3 model)

### FR-3: Complex Product Name Parsing

**Priority:** High

**Description:** Parse composite product strings that encode multiple fields in a single cell using the "|" (pipe) delimiter. Map segments to category hierarchy, product name, and description fields following a consistent pattern.

**Acceptance Criteria:**

- [ ] AC-3.1: Strings containing "|" delimiter are split into segments
- [ ] AC-3.2: First segment maps to primary category (Level 1)
- [ ] AC-3.3: If first segment contains "/" or ">" within it, create nested category hierarchy
- [ ] AC-3.4: Second segment maps to product name field
- [ ] AC-3.5: Third and subsequent segments concatenate into description/specifications
- [ ] AC-3.6: Leading/trailing whitespace trimmed from all segments
- [ ] AC-3.7: Empty segments are skipped (handles "Name || Description" gracefully)
- [ ] AC-3.8: Non-delimited strings process normally (single segment = product name only)
- [ ] AC-3.9: Delimiter character is configurable (default: "|")

**Dependencies:** None

### FR-4: Currency Symbol Extraction and Mapping

**Priority:** High

**Description:** Extract currency symbols from price values during parsing and map them to standardized ISO 4217 currency codes. Store the currency code alongside the numeric price value.

**Acceptance Criteria:**

- [ ] AC-4.1: Currency symbols ₽, $, € are recognized during price parsing
- [ ] AC-4.2: Symbols map to ISO codes: ₽→RUB, $→USD, €→EUR
- [ ] AC-4.3: Currency symbols appearing before or after numeric values are handled
- [ ] AC-4.4: Text currency indicators are recognized: "руб", "руб.", "RUB", "USD", "EUR", "dollars", "euros"
- [ ] AC-4.5: Currency code stored in `currency_code` field of NormalizedRow
- [ ] AC-4.6: When no currency detected, field defaults to configured supplier default or null
- [ ] AC-4.7: Mixed currency documents preserve per-row currency information
- [ ] AC-4.8: Currency extraction does not affect numeric precision of price value

**Dependencies:** Phase 9 pricing schema (currency_code field)

### FR-5: Retail and Wholesale Price Extraction

**Priority:** High

**Description:** Identify and extract both retail (end-customer) and wholesale (dealer/bulk) prices when present in source documents. Detect price type from column headers and contextual clues.

**Acceptance Criteria:**

- [ ] AC-5.1: Column headers analyzed to identify retail vs. wholesale price columns
- [ ] AC-5.2: Common retail indicators detected: "розница", "розн.", "retail", "RRP", "MSRP", "цена"
- [ ] AC-5.3: Common wholesale indicators detected: "опт", "оптовая", "wholesale", "dealer", "bulk", "дилер"
- [ ] AC-5.4: Retail price stored in `retail_price` field
- [ ] AC-5.5: Wholesale price stored in `wholesale_price` field
- [ ] AC-5.6: When only one price column exists, determine type from context or default to retail
- [ ] AC-5.7: Multiple price columns (e.g., tiered wholesale) store additional tiers in characteristics
- [ ] AC-5.8: Price extraction handles formatted numbers (spaces as thousands separator, comma as decimal)

**Dependencies:** Phase 9 pricing schema (retail_price, wholesale_price fields)

### FR-6: Parsing Result Quality Metrics

**Priority:** Medium

**Description:** Track and report parsing quality metrics for each job to enable monitoring and continuous improvement of the parsing pipeline.

**Acceptance Criteria:**

- [ ] AC-6.1: Each job records: total rows scanned, rows parsed successfully, rows skipped, rows with errors
- [ ] AC-6.2: Structure detection confidence score (0-100%) from Stage A recorded
- [ ] AC-6.3: Per-field extraction rates tracked (% of rows with name, price, category, etc.)
- [ ] AC-6.4: LLM token usage recorded per stage (Stage A tokens, Stage B tokens)
- [ ] AC-6.5: Parsing duration breakdown available (file read, Stage A, Stage B, database write)
- [ ] AC-6.6: Metrics exposed in job status response

**Dependencies:** FR-2 (two-stage parsing)

---

## Success Criteria

**Measurable Outcomes:**

1. **Parsing Accuracy:** Two-stage parsing achieves 90% correct field extraction on test document set (vs. 75% baseline)
2. **Token Efficiency:** Average LLM token usage reduced by 40% compared to single-pass full-document parsing
3. **Composite Name Handling:** 95% of pipe-delimited product strings correctly split into category/name/description
4. **Currency Recognition:** 99% accuracy on currency symbol detection across RUB, USD, EUR
5. **Price Field Coverage:** Dual pricing extracted from 80% of documents containing both retail and wholesale columns
6. **Processing Time:** File analysis completes within 3 minutes for documents under 1000 rows
7. **Error Rate:** Less than 2% of parseable rows result in parsing errors

**Qualitative Goals:**

- Admin users observe more complete product data after import
- Reduced manual correction of category assignments
- Pricing data immediately usable without post-processing cleanup

---

## Key Entities

### NormalizedRow (Extended)

**Description:** Core data structure for parsed product rows. Extended with new fields for dual pricing and currency.

**New/Modified Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `retail_price` | Decimal | End-customer price |
| `wholesale_price` | Decimal | Dealer/bulk price |
| `currency_code` | String(3) | ISO 4217 currency code |
| `category_path` | String[] | Hierarchical category from composite parsing |
| `raw_composite` | String | Original composite string before splitting |

### StructureAnalysis

**Description:** Stage A output capturing document structure understanding.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `header_rows` | Integer[] | Row indices containing headers |
| `data_start_row` | Integer | First row index with product data |
| `data_end_row` | Integer | Last row index with product data |
| `column_mapping` | Object | Column index → field purpose mapping |
| `confidence` | Float | LLM confidence in analysis (0-1) |

### ParsingMetrics

**Description:** Quality metrics for completed parsing job.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `total_rows` | Integer | Rows in source document |
| `parsed_rows` | Integer | Successfully parsed rows |
| `skipped_rows` | Integer | Intentionally skipped rows |
| `error_rows` | Integer | Rows with parsing errors |
| `stage_a_tokens` | Integer | LLM tokens for structure analysis |
| `stage_b_tokens` | Integer | LLM tokens for data extraction |
| `duration_ms` | Integer | Total processing time |

---

## Assumptions

1. **Shared Volume Configuration:** The Docker shared volume is mounted at `/shared/uploads` and accessible by both python-ingestion and ml-analyze containers.

2. **Delimiter Consistency:** Supplier documents using composite product strings will consistently use "|" as the primary delimiter within a single document.

3. **Currency Symbol Placement:** Currency symbols appear adjacent to numeric price values (no whitespace exceeding one space between symbol and number).

4. **Header Row Location:** Header rows appear within the first 20 rows of the document.

5. **LLM Availability:** Ollama service with llama3 model is available and responsive during parsing operations.

6. **File Cleanup:** Files in the shared volume are cleaned up by the python-ingestion cleanup task (Phase 8); ml-analyze does not manage file lifecycle.

7. **Phase 9 Schema:** The `retail_price`, `wholesale_price`, and `currency_code` fields exist in the database schema per Phase 9 implementation.

---

## Dependencies

- **Phase 7:** Existing ML-Analyze service infrastructure (FastAPI, Ollama integration, parsing strategies)
- **Phase 8:** Shared volume mount and file handoff pattern from python-ingestion courier
- **Phase 9:** Database schema with pricing fields (`retail_price`, `wholesale_price`, `currency_code`)
- **External:** Ollama LLM service with llama3 model for structure analysis and extraction

---

## Appendix

### References

- Phase 7 (ML-Analyze Service): `/specs/007-ml-analyze/spec.md`
- Phase 8 (ML-Ingestion Integration): `/specs/008-ml-ingestion-integration/spec.md`
- Phase 9 (Advanced Pricing & Categories): `/specs/009-advanced-pricing-categories/spec.md`
- Ollama Documentation: https://ollama.com/

### Glossary

- **Two-Stage Parsing:** Technique where LLM first analyzes document structure, then performs targeted extraction
- **Composite Product String:** Single cell value containing multiple fields separated by delimiters
- **Forward-Fill:** Technique to propagate merged cell values to all affected rows
- **Shared Volume:** Docker volume accessible by multiple containers for file handoff
- **ISO 4217:** International standard for currency codes (e.g., USD, EUR, RUB)
- **Context Window:** Maximum text length an LLM can process in a single request

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
