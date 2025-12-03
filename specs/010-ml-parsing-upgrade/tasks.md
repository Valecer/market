# Task List: ML Parsing Service Upgrade

**Epic/Feature:** [010-ml-parsing-upgrade](/specs/010-ml-parsing-upgrade/plan.md)

**Sprint/Milestone:** Phase 10

**Owner:** Engineering Team

---

## Task Overview

| Phase | Name | Tasks | Description |
|-------|------|-------|-------------|
| 1 | Setup | 4 | Project initialization and configuration |
| 2 | Foundational | 5 | Data models shared across all stories |
| 3 | US1: File Path API | 5 | Secure file path-based API interface |
| 4 | US2: Two-Stage Parsing | 6 | Structure analysis + data extraction |
| 5 | US3: Composite Name Parsing | 4 | Pipe-delimited product name splitting |
| 6 | US4: Price/Currency Extraction | 5 | Currency symbols and dual pricing |
| 7 | US5: Metrics | 4 | Parsing quality metrics |
| 8 | Polish | 3 | Integration and cleanup |

**Total Tasks:** 36

---

## Phase 1: Setup

Project initialization and configuration updates.

### Tasks

- [ ] T001 Add new environment variables to `services/ml-analyze/.env.example`
- [ ] T002 [P] Update settings in `services/ml-analyze/src/config/settings.py` with STRUCTURE_CONFIDENCE_THRESHOLD, STRUCTURE_SAMPLE_ROWS
- [ ] T003 [P] Add SecurityError exception class to `services/ml-analyze/src/utils/errors.py`
- [ ] T004 Verify shared volume mount at `/shared/uploads` in `docker-compose.yml`

**Completion Criteria:**
- Environment variables documented
- Settings class updated with new fields
- SecurityError exception available for import
- Docker volume accessible

---

## Phase 2: Foundational

Data models and schemas shared across all user stories. Must complete before user story phases.

### Tasks

- [ ] T005 Add ColumnMapping Pydantic model to `services/ml-analyze/src/schemas/domain.py`
- [ ] T006 [P] Add StructureAnalysis Pydantic model to `services/ml-analyze/src/schemas/domain.py`
- [ ] T007 [P] Add ParsingMetrics Pydantic model to `services/ml-analyze/src/schemas/domain.py`
- [ ] T008 Extend NormalizedRow with retail_price, wholesale_price, currency_code, category_path, raw_composite in `services/ml-analyze/src/schemas/domain.py`
- [ ] T009 Add model_validator to NormalizedRow for backward compatibility sync in `services/ml-analyze/src/schemas/domain.py`

**Completion Criteria:**
- All Pydantic models pass validation tests
- NormalizedRow backward compatibility verified
- `mypy src/schemas/domain.py --strict` passes

**Dependencies:** Phase 1 complete

---

## Phase 3: US1 - File Path-Based API Interface

**User Story:** As an Admin User, I want to analyze supplier files already downloaded to shared volume, so that I can avoid re-downloading and process files faster.

**Priority:** Critical

**Acceptance Criteria:**
- API accepts `file_path` parameter
- Path traversal attacks blocked
- Appropriate error for missing files
- Backward compatibility with `file_url`

### Tasks

- [ ] T010 [US1] Create secure file reader module `services/ml-analyze/src/utils/file_reader.py` with validate_and_read_file function
- [ ] T011 [US1] Implement path traversal prevention using pathlib.resolve() in `services/ml-analyze/src/utils/file_reader.py`
- [ ] T012 [US1] Add file size validation to `services/ml-analyze/src/utils/file_reader.py`
- [ ] T013 [US1] Extend FileAnalysisRequest with file_path, default_currency, composite_delimiter in `services/ml-analyze/src/schemas/requests.py`
- [ ] T014 [US1] Update analyze_file route to handle file_path parameter in `services/ml-analyze/src/api/routes/analyze.py`

**Independent Test Criteria:**
```bash
# Test path traversal prevention
python -c "from src.utils.file_reader import validate_and_read_file; validate_and_read_file('/shared/uploads/../etc/passwd')"
# Should raise SecurityError

# Test API endpoint
curl -X POST http://localhost:8001/analyze/file \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/shared/uploads/test.xlsx", "supplier_id": "...", "file_type": "excel"}'
```

**Dependencies:** Phase 2 complete

---

## Phase 4: US2 - Two-Stage LLM Parsing Strategy

**User Story:** As a System, I want document structure analyzed before data extraction, so that parsing is more accurate and uses fewer tokens.

**Priority:** Critical

**Acceptance Criteria:**
- Stage A sends document sample for structure analysis
- LLM returns header rows, data boundaries, column mapping
- Stage B uses Stage A results for targeted extraction
- Fallback to full-document parsing if confidence < threshold

### Tasks

- [ ] T015 [US2] Add STRUCTURE_ANALYSIS_SYSTEM and STRUCTURE_ANALYSIS_USER prompts to `services/ml-analyze/src/rag/prompt_templates.py`
- [ ] T016 [P] [US2] Add EXTRACTION_SYSTEM and EXTRACTION_USER prompts to `services/ml-analyze/src/rag/prompt_templates.py`
- [ ] T017 [P] [US2] Add STRUCTURE_ANALYSIS_PROMPT ChatPromptTemplate to `services/ml-analyze/src/rag/prompt_templates.py`
- [ ] T018 [US2] Add EXTRACTION_PROMPT ChatPromptTemplate to `services/ml-analyze/src/rag/prompt_templates.py`
- [ ] T019 [US2] Create TwoStageParsingService class in `services/ml-analyze/src/services/two_stage_parser.py`
- [ ] T020 [US2] Implement run_structure_analysis and run_extraction async methods in `services/ml-analyze/src/services/two_stage_parser.py`

**Independent Test Criteria:**
```bash
# Test prompt templates render correctly
python -c "from src.rag.prompt_templates import STRUCTURE_ANALYSIS_PROMPT; print(STRUCTURE_ANALYSIS_PROMPT.format(sample_rows=20, document_sample='...'))"

# Test two-stage service with mock LLM
pytest tests/test_two_stage_parser.py -v
```

**Dependencies:** Phase 2 complete (StructureAnalysis model)

---

## Phase 5: US3 - Composite Product Name Parsing

**User Story:** As a System, I want composite product strings split into category/name/description, so that product data is properly structured.

**Priority:** High

**Acceptance Criteria:**
- Strings with "|" delimiter split correctly
- First segment → category (with "/" or ">" hierarchy support)
- Second segment → product name
- Third+ segments → description
- Empty segments skipped

### Tasks

- [ ] T021 [US3] Create CompositeNameResult dataclass in `services/ml-analyze/src/utils/name_parser.py`
- [ ] T022 [US3] Implement parse_composite_name function in `services/ml-analyze/src/utils/name_parser.py`
- [ ] T023 [US3] Add category hierarchy parsing (split on "/" and ">") in `services/ml-analyze/src/utils/name_parser.py`
- [ ] T024 [US3] Integrate name parser into TwoStageParsingService post-processing in `services/ml-analyze/src/services/two_stage_parser.py`

**Independent Test Criteria:**
```bash
# Test composite name parsing
python -c "
from src.utils.name_parser import parse_composite_name
result = parse_composite_name('Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah')
assert result.category_path == ['Electric Bicycle']
assert result.name == 'Shtenli Model Gt11'
assert result.description == 'Li-ion 48V 15Ah'
print('PASS')
"
```

**Dependencies:** Phase 2 complete (NormalizedRow with category_path)

---

## Phase 6: US4 - Price and Currency Extraction

**User Story:** As a System, I want prices extracted with currency symbols mapped to ISO codes, so that pricing data is standardized.

**Priority:** High

**Acceptance Criteria:**
- ₽, $, € symbols recognized
- Text indicators (руб, dollars, euros) recognized
- Both retail and wholesale prices extracted
- Currency stored in `currency_code` field

### Tasks

- [ ] T025 [US4] Create PriceResult dataclass in `services/ml-analyze/src/utils/price_parser.py`
- [ ] T026 [US4] Define CURRENCY_MAP dictionary with symbol/text → ISO code mappings in `services/ml-analyze/src/utils/price_parser.py`
- [ ] T027 [US4] Implement extract_price function with regex pattern in `services/ml-analyze/src/utils/price_parser.py`
- [ ] T028 [US4] Add classify_price_column function for retail/wholesale detection in `services/ml-analyze/src/utils/price_parser.py`
- [ ] T029 [US4] Integrate price parser into TwoStageParsingService post-processing in `services/ml-analyze/src/services/two_stage_parser.py`

**Independent Test Criteria:**
```bash
# Test price extraction
python -c "
from src.utils.price_parser import extract_price
result = extract_price('₽1 500.00')
assert result.amount == 1500
assert result.currency_code == 'RUB'
print('PASS')
"

# Test multiple currencies
python -c "
from src.utils.price_parser import extract_price
assert extract_price('\$99.99').currency_code == 'USD'
assert extract_price('150€').currency_code == 'EUR'
assert extract_price('25 руб').currency_code == 'RUB'
print('PASS')
"
```

**Dependencies:** Phase 2 complete (NormalizedRow with retail_price, wholesale_price, currency_code)

---

## Phase 7: US5 - Parsing Quality Metrics

**User Story:** As an Admin User, I want to see parsing quality metrics for each job, so that I can monitor and improve the parsing pipeline.

**Priority:** Medium

**Acceptance Criteria:**
- Total rows, parsed rows, skipped rows, error rows tracked
- Structure detection confidence recorded
- LLM token usage per stage recorded
- Parsing duration breakdown available
- Metrics exposed in job status response

### Tasks

- [ ] T030 [US5] Add metrics collection to TwoStageParsingService in `services/ml-analyze/src/services/two_stage_parser.py`
- [ ] T031 [US5] Track token usage from LLM responses in `services/ml-analyze/src/services/two_stage_parser.py`
- [ ] T032 [US5] Extend FileAnalysisResponse with metrics field in `services/ml-analyze/src/schemas/responses.py`
- [ ] T033 [US5] Update job status response to include metrics in `services/ml-analyze/src/api/routes/status.py`

**Independent Test Criteria:**
```bash
# Test metrics collection
curl http://localhost:8001/analyze/status/{job_id} | jq '.metrics'
# Should return:
# {
#   "total_rows": 500,
#   "parsed_rows": 480,
#   "skipped_rows": 15,
#   "error_rows": 5,
#   "stage_a_tokens": 1200,
#   "stage_b_tokens": 8500,
#   "duration_ms": 45000
# }
```

**Dependencies:** Phases 4-6 complete (TwoStageParsingService operational)

---

## Phase 8: Polish & Cross-Cutting Concerns

Final integration, fallback logic, and cleanup.

### Tasks

- [ ] T034 Implement fallback to single-pass parsing when Stage A confidence < threshold in `services/ml-analyze/src/services/two_stage_parser.py`
- [ ] T035 Add LLM JSON retry logic (max 3 attempts) in `services/ml-analyze/src/services/two_stage_parser.py`
- [ ] T036 Integrate TwoStageParsingService into IngestionService in `services/ml-analyze/src/services/ingestion_service.py`

**Completion Criteria:**
- Full pipeline works end-to-end
- Fallback logic tested
- Error handling comprehensive
- `mypy src/ --strict` passes

**Dependencies:** All user story phases complete

---

## Dependency Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational)
    │
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
Phase 3        Phase 4        Phase 5        Phase 6
(US1: API)     (US2: Parse)   (US3: Names)   (US4: Price)
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
                        │
                        ▼
                   Phase 7 (US5: Metrics)
                        │
                        ▼
                   Phase 8 (Polish)
```

**Parallel Opportunities:**
- T002 & T003 (Setup) - Different files
- T005, T006, T007 (Foundational) - Independent models
- T015, T016, T017, T018 (US2) - Prompt templates are independent
- Phases 3, 4, 5, 6 - Can run in parallel after Phase 2

---

## Parallel Execution Examples

### Example 1: Phase 2 Parallelization

```
T005 (ColumnMapping) ──┐
T006 (StructureAnalysis) ──┼──► T008 (NormalizedRow extension) ──► T009 (model_validator)
T007 (ParsingMetrics) ──┘
```

### Example 2: Cross-Story Parallelization

After Phase 2 completes, these can run simultaneously:

```
Developer A: Phase 3 (US1) - File path API
Developer B: Phase 4 (US2) - Two-stage parsing prompts
Developer C: Phase 5 (US3) - Name parser
Developer D: Phase 6 (US4) - Price parser
```

### Example 3: Within-Story Parallelization (Phase 4)

```
T015 (STRUCTURE_ANALYSIS_SYSTEM) ──┬──► T019 (TwoStageParsingService)
T016 (EXTRACTION_SYSTEM) ──────────┘          │
T017 (STRUCTURE_ANALYSIS_PROMPT) ─────────────┤
T018 (EXTRACTION_PROMPT) ─────────────────────┘
```

---

## Implementation Strategy

### MVP Scope (Recommended First Pass)

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)**

Deliver file path-based API first:
- Enables shared volume access immediately
- Unblocks python-ingestion Phase 8 integration
- Foundation for remaining phases

### Incremental Delivery Order

1. **MVP (US1):** File path API - 1 day
2. **Iteration 2 (US2):** Two-stage parsing - 1 day  
3. **Iteration 3 (US3+US4):** Name + Price parsing - 1 day
4. **Iteration 4 (US5+Polish):** Metrics + Integration - 1 day

### Risk-First Approach

Implement in order of technical risk:
1. **US2 (Two-Stage Parsing)** - Highest LLM dependency risk
2. **US1 (File Path API)** - Security risk (path traversal)
3. **US4 (Price Extraction)** - Regex complexity
4. **US3 (Name Parsing)** - Lowest risk, deterministic

---

## Task Summary

| Status | Count |
|--------|-------|
| Total | 36 |
| Critical (US1+US2) | 11 |
| High (US3+US4) | 9 |
| Medium (US5+Polish) | 7 |
| Setup/Foundational | 9 |

**Estimated Total Effort:** 4-5 days

---

## Notes

- All file paths are relative to `services/ml-analyze/`
- Tasks marked `[P]` can be parallelized
- Tasks marked `[USn]` belong to User Story n
- Run `mypy src/ --strict` after each phase
- Run `pytest tests/ -v` after completing each story phase
- Update task status in project management tool as completed

