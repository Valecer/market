# Research: Semantic ETL Pipeline with LangChain

**Date:** 2025-12-04

**Status:** Complete

---

## Overview

This document captures research findings for implementing a semantic ETL pipeline using LangChain and Ollama. All "NEEDS CLARIFICATION" items from the implementation plan have been resolved.

---

## Research Topics

### 1. LangChain Prompt Engineering Best Practices

**Question:** How to design prompts for tabular data extraction? How to enforce strict JSON schema output? How to handle LLM hallucinations?

#### Findings

**Structured Output with Pydantic:**
LangChain provides robust structured output capabilities via `model.with_structured_output()` and `ToolStrategy`. Key approaches:

1. **Pydantic BaseModel (Recommended):**
   ```python
   from pydantic import BaseModel, Field

   class ExtractedProduct(BaseModel):
       name: str = Field(..., min_length=1, description="Product name")
       retail_price: float = Field(..., ge=0, description="Retail price in BYN")
       category_path: list[str] = Field(default_factory=list, description="Category hierarchy")

   model_with_structure = model.with_structured_output(ExtractedProduct)
   ```

2. **JSON Schema (Maximum Control):**
   ```python
   json_schema = {
       "type": "object",
       "properties": {
           "name": {"type": "string", "description": "Product name"},
           "retail_price": {"type": "number", "minimum": 0}
       },
       "required": ["name", "retail_price"]
   }
   model_with_structure = model.with_structured_output(json_schema, method="json_schema")
   ```

**Tabular Data Best Practices:**

From [Medium: LLMs with Tabular Data](https://medium.com/@vamshidhar.pandrapagada/llms-with-tabular-data-using-langchain-and-prompt-engineering-383591d9abb8):

- **Add Column Semantics:** Tell the LLM what each column means and how they relate
- **Use Clear Instructions:** "Extract product data from the markdown table. Each row represents one product."
- **Define Expected Format:** Show the LLM an example of the desired output structure

From [Unstract: Structured Data Extraction](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/):

- **Three Strategies for Semi-Structured Data:**
  1. Pass entire table into LLM context window (simple, limited by context size)
  2. Detect and extract tables first, then process (targeted approach)
  3. Split documents preserving table elements (hybrid approach)

**Hallucination Prevention:**

From [LangChain: Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output):

- **Schema Validation with Error Handling:** LangChain's `ToolStrategy` with `handle_errors=True` catches validation errors and prompts the LLM to correct them
- **Required Fields:** Use `required` in JSON schema or `...` in Pydantic to enforce mandatory fields
- **Constraints:** Use Pydantic's `Field(..., ge=0, le=100)` for numeric ranges
- **System Prompts:** Add "Do not make any field or value up. If a field is missing, leave it null."

#### Decision

**For Marketbel Semantic ETL:**

1. **Use Pydantic BaseModel** for `ExtractedProduct` schema (runtime validation, clear error messages)
2. **Prompt Template Structure:**
   ```
   System: You are a product data extraction assistant. Extract structured product data from markdown tables.

   Instructions:
   - Each row in the markdown table represents one product
   - Extract: name (required), retail_price (required), wholesale_price (optional), category_path (array)
   - If a field is missing or unclear, leave it null
   - Do not invent data
   - Parse prices as numbers only (remove currency symbols, commas)

   Schema: {pydantic_schema_json}

   User: {markdown_chunk}
   ```

3. **Error Handling:** Enable `handle_errors=True` to automatically retry failed validations
4. **Column Semantics:** Prepend each chunk with detected column headers and their meanings

---

### 2. Sliding Window Chunk Size Optimization

**Question:** What is the optimal chunk size (rows) for llama3's 8k token context? How much overlap prevents data loss? How to handle products split across boundaries?

#### Findings

**Token Limits in 2025:**

From [Deepchecks: LLM Token Limits](https://www.deepchecks.com/5-approaches-to-solve-llm-token-limits/):

- **llama3 Context:** 8,192 tokens (approximately 6,000 words or 24,000 characters)
- **Practical Limit:** Reserve 20-25% for system prompt, schema, and output buffer
- **Effective Window:** ~6,000 tokens for input data

**Optimal Chunk Sizes:**

From [Pinecone: Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/):

- **512-1024 tokens:** Consistently best answer quality across diverse text types
- **Trade-off:** Larger chunks = more context, but fewer chunks = less coverage
- **For Tables:** Chunks should include header + multiple rows (not split mid-row)

From [Unstract: Chunk Size](https://docs.unstract.com/unstract/unstract_platform/user_guides/chunking/):

- **Chunk Overlap:** 10-20% of chunk size is standard
- **Purpose:** Prevents data loss at boundaries, especially for entities spanning multiple sentences/rows
- **Too Much Overlap:** Wastes tokens, duplicates data; **Too Little:** Risks missing cross-boundary patterns

**Sliding Window Best Practices:**

From [Flow AI: Long-Context LLMs](https://www.flow-ai.com/blog/advancing-long-context-llm-performance-in-2025):

- **Overlapping Segments:** Process text in overlapping chunks to retain critical information
- **Boundary Handling:** Always end chunks at natural boundaries (e.g., row breaks, not mid-cell)

#### Calculation

**For Marketbel Excel Files:**

Assumptions:
- Average row: 5 columns × 15 characters/cell = 75 characters/row
- Token ratio: ~4 characters/token (English text)
- Tokens per row: 75 / 4 = ~19 tokens/row
- Available tokens: 6,000 tokens (after reserving for prompt/schema)

**Optimal Chunk Size:**
- 6,000 tokens / 19 tokens/row = ~315 rows/chunk
- **Conservative estimate:** **250 rows/chunk** (accounts for longer descriptions, headers)

**Overlap:**
- 15% of 250 = **37 rows overlap**
- Ensures products near chunk boundaries are processed in both adjacent chunks

**Handling Split Products:**
- **Strategy:** Always split on row boundaries (never mid-row)
- **Overlap Deduplication:** Dedup logic compares products by name+price across chunks
- **Edge Case:** If a product appears in overlap zone of chunks N and N+1, keep the version from chunk N (first occurrence)

#### Decision

**For Marketbel Semantic ETL:**

1. **Chunk Size:** 250 rows per chunk (with dynamic adjustment based on token count)
2. **Overlap:** 40 rows (16%) to safely handle boundary cases
3. **Splitting Logic:**
   ```python
   def chunk_markdown(rows: list[str], chunk_size=250, overlap=40):
       chunks = []
       for i in range(0, len(rows), chunk_size - overlap):
           chunk = rows[i:i + chunk_size]
           chunks.append(chunk)
       return chunks
   ```

4. **Token Monitoring:** Log actual token counts per chunk, alert if approaching 6k token limit
5. **Boundary Handling:** Always include header row in each chunk for context

---

### 3. Markdown Table Representation for Merged Cells

**Question:** How to represent merged cells in Markdown that LLMs understand? Should we use repeated values or special syntax? How do libraries handle this?

#### Findings

**Markdown Limitations:**

Standard Markdown does not support merged cells (colspan/rowspan). Solutions:

1. **Repeated Values (Recommended for LLMs):**
   ```markdown
   | Category     | Product    | Price  |
   |--------------|------------|--------|
   | Electronics  | Laptop     | 1200   |
   | Electronics  | Mouse      | 25     |
   | Electronics  | Keyboard   | 75     |
   ```
   - Merged "Electronics" cell is repeated in each row
   - LLMs understand this pattern naturally (no special parsing)

2. **Empty Cells with Context:**
   ```markdown
   | Category     | Product    | Price  |
   |--------------|------------|--------|
   | Electronics  | Laptop     | 1200   |
   |              | Mouse      | 25     |
   |              | Keyboard   | 75     |
   ```
   - Merged cell represented by empty string in subsequent rows
   - Requires LLM to "carry forward" previous non-empty value
   - More error-prone (LLM might not infer relationship)

3. **HTML Tables (Not Recommended):**
   - Markdown supports embedded HTML with `colspan`/`rowspan`
   - LLMs struggle with HTML syntax, focus on content extraction instead

**Library Examples:**

- **pymupdf4llm (PDF parsing):** Converts PDF tables to Markdown with repeated values for merged cells
- **pandas `to_markdown()`:** Does not support merged cells (flattens them)
- **openpyxl:** Provides `merged_cells` property to detect merged ranges

#### Decision

**For Marketbel Semantic ETL:**

1. **Use Repeated Values:** When a cell is merged across multiple rows, repeat its value in each row
   ```python
   def convert_merged_cells(worksheet):
       # Detect merged ranges
       for merged_range in worksheet.merged_cells.ranges:
           # Get value from top-left cell
           value = worksheet.cell(merged_range.min_row, merged_range.min_col).value
           # Fill all cells in merged range with same value
           for row in range(merged_range.min_row, merged_range.max_row + 1):
               for col in range(merged_range.min_col, merged_range.max_col + 1):
                   worksheet.cell(row, col).value = value
   ```

2. **Document in Prompt:** Add instruction: "Some cells may have repeated values across rows (e.g., category names). This indicates they belong to the same group."

3. **Markdown Format:** Standard pipe-delimited tables with repeated values
   - Easy for LLMs to parse
   - No special syntax needed
   - Human-readable for debugging

---

### 4. Category Hierarchy Creation Logic

**Question:** When LLM returns ["Parent", "Child"], should we create both if missing? How to handle orphaned child categories? Should `parent_id` be nullable?

#### Findings

**Database Design Patterns:**

From [PostgreSQL Hierarchical Data](https://www.postgresql.org/docs/current/queries-with.html):

- **Self-Referencing FK:** `parent_id INT REFERENCES categories(id)` is standard for tree structures
- **Nullable Parent:** Root categories have `parent_id = NULL`
- **Constraint:** FK ensures referential integrity (parent must exist before child)

**Category Matching Strategies:**

From [RapidFuzz: Fuzzy Matching](https://github.com/maxbachmann/RapidFuzz):

- **Hierarchical Matching:** Match each level independently (e.g., "Parent" then "Child")
- **Threshold:** 85% similarity balances precision and recall
- **Token Set Ratio:** Handles word order differences ("Laptop Accessories" vs "Accessories for Laptops")

**Error Handling:**

Best practices:
- **Create Parent First:** If parent doesn't exist, create it before child
- **Mark for Review:** New categories get `needs_review=true` flag
- **Admin Approval:** Human reviews new categories before they're fully active

#### Decision

**For Marketbel Semantic ETL:**

1. **Automatic Hierarchy Creation:**
   ```python
   async def create_category_hierarchy(path: list[str], supplier_id: int) -> int:
       """
       Create category hierarchy, returning leaf category ID.
       Example: ["Electronics", "Laptops"] creates both if missing.
       """
       parent_id = None
       for level, name in enumerate(path):
           # Fuzzy match at current level
           matched = fuzzy_match_category(name, parent_id=parent_id)
           if matched:
               parent_id = matched.id
           else:
               # Create new category with needs_review=true
               new_cat = await create_category(
                   name=name,
                   parent_id=parent_id,
                   needs_review=True,
                   supplier_id=supplier_id
               )
               parent_id = new_cat.id
       return parent_id  # Return leaf category ID
   ```

2. **Database Schema:**
   ```sql
   ALTER TABLE categories
   ADD COLUMN parent_id INT REFERENCES categories(id) ON DELETE CASCADE,
   ADD COLUMN needs_review BOOLEAN DEFAULT false,
   ADD COLUMN is_active BOOLEAN DEFAULT true;

   CREATE INDEX idx_categories_parent_id ON categories(parent_id);
   CREATE INDEX idx_categories_needs_review ON categories(needs_review) WHERE needs_review = true;
   ```

3. **Orphan Prevention:**
   - **Enforced by FK:** PostgreSQL prevents orphan creation (parent must exist)
   - **Transaction Scope:** Create parent and child in same transaction
   - **Rollback on Error:** If child creation fails, rollback parent creation

4. **Admin Review Workflow:**
   - New categories: `needs_review=true`, `is_active=true` (visible but flagged)
   - Admin approves: Set `needs_review=false`
   - Admin merges: Update `parent_id` or delete duplicate, transfer products

---

### 5. LangChain Model Selection and Configuration

**Question:** Which LangChain LLM wrapper to use for Ollama? How to configure temperature, max_tokens? How to handle retries?

#### Findings

**LangChain Ollama Integration:**

From [LangChain Docs: Ollama](https://python.langchain.com/docs/integrations/llms/ollama):

- **Package:** `langchain-ollama` (official integration)
- **Chat Model:** `ChatOllama` for conversational models
- **LLM:** `OllamaLLM` for completion models
- **Recommended:** Use `ChatOllama` even for structured output (better prompt handling)

**Configuration Parameters:**

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3",
    base_url="http://ollama:11434",
    temperature=0.1,  # Low temperature for deterministic extraction
    num_predict=2048,  # Max tokens for response
    format="json",  # Force JSON output
    timeout=30.0,  # Request timeout (seconds)
)
```

**Key Parameters:**

- **temperature:** 0.0-0.3 for extraction (deterministic), 0.7-1.0 for creative tasks
- **num_predict:** Max response tokens (leave room for context: 8192 - input_tokens)
- **format:** Set to "json" to enforce JSON mode (Ollama feature)
- **top_k / top_p:** Default values work well (top_k=40, top_p=0.9)

**Retry Logic:**

From [LangChain: Error Handling](https://python.langchain.com/docs/guides/development/debugging):

- **Built-in Retries:** LangChain does NOT retry by default
- **Custom Retry:** Use `tenacity` library for exponential backoff
  ```python
  from tenacity import retry, stop_after_attempt, wait_exponential

  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=2, max=10),
      reraise=True
  )
  async def extract_with_retry(llm, prompt):
      return await llm.ainvoke(prompt)
  ```

#### Decision

**For Marketbel Semantic ETL:**

1. **Use ChatOllama:**
   ```python
   from langchain_ollama import ChatOllama

   llm = ChatOllama(
       model="llama3",
       base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
       temperature=0.2,  # Slightly creative for handling ambiguous cases
       num_predict=2048,
       format="json",
       timeout=60.0,  # Longer timeout for complex tables
   )
   ```

2. **Structured Output:**
   ```python
   model_with_structure = llm.with_structured_output(ExtractedProduct)
   ```

3. **Retry Configuration:**
   - **Max Retries:** 3 attempts
   - **Backoff:** Exponential (2s, 4s, 8s)
   - **Retry Conditions:** Timeout, connection error, validation error
   - **No Retry:** Invalid schema (log and skip), successful extraction

4. **Error Handling:**
   ```python
   try:
       result = await extract_with_retry(model_with_structure, prompt)
   except ValidationError as e:
       logger.error(f"Schema validation failed: {e}")
       # Log to parsing_logs, continue with next chunk
   except TimeoutError:
       logger.error("LLM timeout after 3 retries")
       # Mark job as failed, allow manual retry
   ```

---

### 6. Migration Strategy from Legacy Parsers

**Question:** Should we run both systems in parallel? How to handle rollback? What metrics to track?

#### Findings

**Blue-Green Deployment Patterns:**

From [Martin Fowler: Blue-Green Deployment](https://martinfowler.com/bliki/BlueGreenDeployment.html):

- **Parallel Run:** Run old and new systems simultaneously, compare outputs
- **Feature Flag:** Toggle between systems without code changes
- **Canary Release:** Roll out to small percentage of traffic first

**Rollback Strategies:**

- **Code Rollback:** Revert to previous git tag (keep legacy code in separate branch)
- **Feature Flag Disable:** Flip flag to disable semantic ETL, re-enable legacy
- **Data Rollback:** No data migration needed (both write to same tables)

**Metrics to Track:**

From [Observability Best Practices](https://opentelemetry.io/docs/concepts/observability-primer/):

- **Accuracy:** % of products correctly extracted (compare manual review)
- **Completeness:** % of required fields populated
- **Performance:** Processing time per file (median, p95, p99)
- **Error Rate:** % of jobs failed, % of products skipped
- **Category Match Rate:** % of categories matched vs created

#### Decision

**For Marketbel Semantic ETL:**

1. **Migration Phases:**
   - **Phase 1 (Week 1):** Deploy semantic ETL with feature flag OFF, test on dev environment
   - **Phase 2 (Week 2):** Enable for 3 test suppliers, compare legacy vs semantic results
   - **Phase 3 (Week 3):** Parallel run: Both systems process same files, compare outputs
   - **Phase 4 (Week 4):** Enable for 50% of suppliers (canary release)
   - **Phase 5 (Week 5):** Full cutover, remove legacy code after 1 week observation

2. **Feature Flag:**
   ```python
   # Environment variable
   USE_SEMANTIC_ETL = os.getenv("USE_SEMANTIC_ETL", "false").lower() == "true"

   # Per-supplier override (suppliers table)
   ALTER TABLE suppliers ADD COLUMN use_semantic_etl BOOLEAN DEFAULT false;

   # Logic
   if supplier.use_semantic_etl or USE_SEMANTIC_ETL:
       await semantic_extract(file_path)
   else:
       await legacy_extract(file_path)
   ```

3. **Metrics Dashboard:**
   - **Extraction Accuracy:** Compare semantic vs legacy on 10 test files
   - **Processing Time:** Track median time per file (target: <3 min for 500 rows)
   - **Error Rate:** Alert if >5% of jobs fail
   - **Category Match Rate:** Track % of fuzzy matches vs new categories
   - **Admin Feedback:** Count of manual corrections needed

4. **Rollback Triggers:**
   - Extraction accuracy <90% (compared to manual review)
   - Error rate >10%
   - Processing time >2x legacy system
   - Critical bug discovered in production

5. **Rollback Process:**
   ```bash
   # Disable feature flag
   export USE_SEMANTIC_ETL=false

   # Revert code (if needed)
   git revert <semantic-etl-commit>

   # Update suppliers table
   UPDATE suppliers SET use_semantic_etl = false;

   # Restart services
   docker-compose restart ml-analyze python-ingestion
   ```

---

### 7. Error Handling for Partial Extractions

**Question:** If 80% of products extract successfully, is that "completed_with_errors" or "failed"? How to surface partial results? Should we insert partial results or rollback?

#### Findings

**Job Status Patterns:**

Common statuses in ETL systems:
- **Success:** 100% of records processed successfully
- **Partial Success / Warning:** >X% success (e.g., 80%), some errors
- **Failed:** <X% success, job aborted

**Transactional Patterns:**

From [PostgreSQL: Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html):

- **All-or-Nothing:** ROLLBACK on any error (strict consistency)
- **Best-Effort:** COMMIT partial results, log errors (pragmatic approach)
- **Savepoints:** Partial commits within transaction (complex)

**User Experience:**

- **Visibility:** Users need to know about partial failures
- **Actionability:** Errors should include row numbers, field names
- **Retry:** Failed rows should be retryable without re-processing entire file

#### Decision

**For Marketbel Semantic ETL:**

1. **Job Status Thresholds:**
   - **Success:** 100% of rows extracted successfully
   - **Completed with Errors:** 80-99% success rate
   - **Failed:** <80% success rate OR critical error (file unreadable, LLM unavailable)

2. **Partial Result Handling:**
   - **Insert Partial Results:** Commit successfully extracted products to DB
   - **Log Errors:** Write failed rows to `parsing_logs` with details
   - **Surface to Admin:** Job status shows "150/200 products extracted (25 warnings)"

3. **Database Transaction Strategy:**
   ```python
   async def process_file(file_path: str, supplier_id: int):
       extracted = []
       errors = []

       for chunk in chunks:
           try:
               result = await extract_chunk(chunk)
               extracted.extend(result.products)
           except Exception as e:
               errors.append({"chunk_id": chunk.id, "error": str(e)})

       success_rate = len(extracted) / total_rows

       if success_rate >= 0.8:
           # Commit partial results
           async with db.transaction():
               await insert_products(extracted)
               await log_errors(errors)
           return JobStatus.COMPLETED_WITH_ERRORS if errors else JobStatus.SUCCESS
       else:
           # Rollback, log critical failure
           await log_critical_error(file_path, errors)
           return JobStatus.FAILED
   ```

4. **Error Detail Schema:**
   ```python
   # parsing_logs table
   CREATE TABLE parsing_logs (
       id SERIAL PRIMARY KEY,
       supplier_id INT REFERENCES suppliers(id),
       job_id VARCHAR(64),
       chunk_id INT,
       row_number INT,
       error_type VARCHAR(50),  -- 'validation', 'timeout', 'parsing'
       error_message TEXT,
       raw_data JSONB,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

5. **Admin UI Display:**
   - **Success:** Green checkmark, "200 products imported"
   - **Partial:** Yellow warning, "180/200 products imported (20 errors) [View Details]"
   - **Failed:** Red X, "Import failed (<80% success rate) [Retry]"
   - **Error Details Page:** Table of failed rows with error messages

6. **Retry Logic:**
   - **Whole File Retry:** Admin can retry entire job (e.g., if LLM was down)
   - **No Row-Level Retry:** Too complex; admin should fix file and re-upload

---

## Summary of Decisions

### Technical Stack Confirmed

| Component | Technology | Configuration |
|-----------|-----------|---------------|
| LLM Wrapper | `langchain-ollama.ChatOllama` | temp=0.2, num_predict=2048, format="json" |
| Structured Output | Pydantic BaseModel | `ExtractedProduct` schema with validation |
| Chunk Size | 250 rows | 40-row overlap (16%) |
| Markdown Format | Pipe-delimited tables | Repeated values for merged cells |
| Category Matching | RapidFuzz token_set_ratio | 85% threshold |
| Retry Logic | tenacity library | 3 attempts, exponential backoff (2s, 4s, 8s) |
| Migration | Feature flag + canary | Parallel run for 1 week before cutover |
| Partial Success | Insert + log errors | "completed_with_errors" if ≥80% success |

### Key Algorithms

1. **Chunk Generation:** Sliding window with 250 rows, 40-row overlap
2. **Merged Cell Handling:** Repeat values across merged range
3. **Category Hierarchy:** Create parent before child, fuzzy match each level
4. **Deduplication:** Hash-based on normalized name + price (1% tolerance)
5. **Error Recovery:** Commit partial results if ≥80% success, log failures

### Open Risks Mitigated

- **LLM Hallucination:** Schema validation + error handling + low temperature
- **Token Limits:** Conservative chunk size (250 rows), dynamic monitoring
- **Category Duplication:** 85% fuzzy threshold + admin review UI
- **Migration Risk:** Feature flag + parallel run + rollback plan
- **Partial Failures:** Clear status thresholds + detailed error logging

---

## References

### Documentation Sources

- [LangChain Python: Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain: Ollama Integration](https://python.langchain.com/docs/integrations/llms/ollama)
- [RapidFuzz Documentation](https://github.com/maxbachmann/RapidFuzz)
- [PostgreSQL: Recursive Queries](https://www.postgresql.org/docs/current/queries-with.html)

### Research Articles

- [Medium: LLMs with Tabular Data using LangChain](https://medium.com/@vamshidhar.pandrapagada/llms-with-tabular-data-using-langchain-and-prompt-engineering-383591d9abb8)
- [Medium: Better NLU of Tabular Data](https://rberga.medium.com/better-natural-language-understanding-of-tabular-data-through-prompt-engineering-ea76d7d3dcbf)
- [LangChain Blog: Benchmarking RAG on Tables](https://blog.langchain.com/benchmarking-rag-on-tables/)
- [Unstract: Structured Data Extraction from PDFs](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/)
- [PromptMixer: 7 Best Practices for AI Prompt Engineering in 2025](https://www.promptmixer.dev/blog/7-best-practices-for-ai-prompt-engineering-in-2025)
- [Deepchecks: 5 Approaches to Solve LLM Token Limits](https://www.deepchecks.com/5-approaches-to-solve-llm-token-limits/)
- [Flow AI: Advancing Long-Context LLM Performance in 2025](https://www.flow-ai.com/blog/advancing-long-context-llm-performance-in-2025)
- [Pinecone: Chunking Strategies for LLM Applications](https://www.pinecone.io/learn/chunking-strategies/)
- [Unstract: Chunk Size and Overlap](https://docs.unstract.com/unstract/unstract_platform/user_guides/chunking/)

---

**Next Steps:**

Proceed to Phase 1 (Design): Generate data-model.md, contracts/, and quickstart.md based on these research findings.
