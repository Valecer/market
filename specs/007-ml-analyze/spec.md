# Feature Specification: ML-Based Product Analysis & Merging Service

**Version:** 1.0.0

**Last Updated:** 2025-12-03

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** ml-analyze has a focused purpose: handle complex unstructured supplier data that existing parsers cannot process
- **Separation of Concerns:** Python service handles AI-heavy processing (embeddings, LLM inference) independently from the main API layer
- **Strong Typing:** Pydantic models for all data validation; TypeBox schemas for API contracts with main Bun service
- **KISS:** Start with text-only processing; defer vision capabilities to future phase
- **DRY:** Reuse existing database schema (products, supplier_items tables); leverage existing admin UI framework

**Compliance Statement:**

This specification adheres to all constitutional principles. The service extends existing capabilities without modifying core architecture.

---

## Overview

### Purpose

Enable intelligent ingestion and matching of complex, unstructured supplier data (PDFs with tables, Excel files with merged cells, and future image-based price lists) using AI-powered extraction and semantic matching, overcoming limitations of the current regex-based parsers.

### Scope

**In Scope:**

- Standalone Python microservice with FastAPI endpoints
- Intelligent parsing of PDF tables (as Markdown-structured text)
- Handling Excel/CSV files with merged cells via forward-fill normalization
- Vector-based product embedding storage using pgvector
- LLM-powered semantic matching to link supplier items to existing products
- Integration with existing PostgreSQL database (products, supplier_items tables)
- Support for both local LLM (Ollama) and cloud LLM providers via configuration
- Stubbed interface for future vision module (image/photo processing)

**Out of Scope:**

- Actual image/photo processing (MVP is text-only; vision interface designed but not implemented)
- Replacement of existing Phase 1 parsers for well-structured data sources
- Direct user-facing UI (existing admin frontend displays results)
- Real-time processing (follows existing queue-based architecture pattern)
- Automated reprocessing of historical data (only processes new supplier files)

---

## Functional Requirements

### FR-1: Complex File Ingestion

**Priority:** Critical

**Description:** Accept and parse supplier data files in formats that existing regex parsers cannot handle, including PDFs with table structures and Excel files with merged cells. Normalize all input into a standardized intermediate format for downstream processing.

**Acceptance Criteria:**

- [ ] AC-1.1: Service accepts file references (local paths, HTTP URLs, cloud storage URLs) via API endpoint
- [ ] AC-1.2: PDF files are parsed to extract table structures as Markdown-formatted text, preserving row/column relationships
- [ ] AC-1.3: Excel/CSV files with merged cells are normalized via forward-fill (e.g., category merged across 10 rows becomes explicit in all 10 rows)
- [ ] AC-1.4: All parsed data is converted to a standardized intermediate format before storage
- [ ] AC-1.5: Parsing errors are logged per-row to parsing_logs table without crashing the service
- [ ] AC-1.6: Successfully parsed items are inserted into supplier_items table with status 'pending_match'

**Dependencies:** None (standalone file processing)

### FR-2: Vector Embedding Storage

**Priority:** Critical

**Description:** Convert product descriptions into semantic vector embeddings using a lightweight local model, and store them in a pgvector-enabled database for efficient similarity search. This enables semantic matching beyond keyword overlap.

**Acceptance Criteria:**

- [ ] AC-2.1: PostgreSQL database has pgvector extension enabled
- [ ] AC-2.2: New table `product_embeddings` stores vector representations of supplier_items
- [ ] AC-2.3: Local embedding model (e.g., nomic-embed-text via Ollama) generates embeddings for product descriptions
- [ ] AC-2.4: Embeddings are indexed for fast cosine similarity search
- [ ] AC-2.5: Each supplier_item record is chunked by product row and embedded individually
- [ ] AC-2.6: Embedding generation is idempotent (re-running on same item produces same embedding)

**Dependencies:**
- PostgreSQL 16 with pgvector extension
- Ollama with embedding model installed

### FR-3: LLM-Powered Product Matching

**Priority:** Critical

**Description:** Use AI language models to intelligently match newly ingested supplier items with existing products in the catalog by performing semantic similarity search and confirming matches via structured LLM prompts.

**Acceptance Criteria:**

- [ ] AC-3.1: For each new supplier item, perform vector search to find Top-5 most similar existing products from other suppliers
- [ ] AC-3.2: LLM receives structured prompt: "Here is Item A and 5 potential matches. Which ones are the same product? Output JSON."
- [ ] AC-3.3: LLM response is parsed and validated for match confidence scores
- [ ] AC-3.4: Matches with confidence >90% automatically link supplier_item.product_id
- [ ] AC-3.5: Matches with confidence 70-90% are added to match_review_queue for manual review
- [ ] AC-3.6: Matches with confidence <70% are rejected and logged
- [ ] AC-3.7: System supports both local LLM (Ollama llama3) and cloud LLM providers, selectable via configuration

**Dependencies:**
- FR-2 (vector embeddings must exist for similarity search)
- Ollama API or cloud LLM API access

### FR-4: Database Integration

**Priority:** Critical

**Description:** Write matching results to the existing database schema without requiring changes to the main API or frontend, enabling seamless display of matched products in the existing admin interface.

**Acceptance Criteria:**

- [ ] AC-4.1: Confirmed matches update supplier_items.product_id field
- [ ] AC-4.2: Uncertain matches are inserted into match_review_queue table (existing Phase 4 schema)
- [ ] AC-4.3: All processing results are logged to parsing_logs table
- [ ] AC-4.4: No modifications to existing products or supplier_items schema required
- [ ] AC-4.5: Existing admin frontend displays matched products without code changes

**Dependencies:**
- Existing database schema from Phases 1, 4

### FR-5: Admin API Endpoints

**Priority:** High

**Description:** Expose HTTP endpoints for the main Bun API to trigger file processing and monitor job status, following the same pattern as existing admin sync endpoints (Phase 6).

**Acceptance Criteria:**

- [ ] AC-5.1: POST /analyze/trigger endpoint accepts file reference and supplier_id
- [ ] AC-5.2: Endpoint returns job_id immediately and enqueues processing task
- [ ] AC-5.3: GET /analyze/status/:job_id returns current processing state (pending/processing/completed/failed)
- [ ] AC-5.4: Status response includes progress percentage and any errors
- [ ] AC-5.5: All endpoints require admin authentication (JWT validation)
- [ ] AC-5.6: OpenAPI/Swagger documentation is auto-generated

**Dependencies:**
- Bun API must proxy requests to ml-analyze service

### FR-6: Vision Module Interface (Stubbed)

**Priority:** Low

**Description:** Design and document the interface for future image/photo processing capabilities, but implement only a stub that returns "not implemented" errors. This ensures the architecture can accommodate vision features without delaying the MVP.

**Acceptance Criteria:**

- [ ] AC-6.1: POST /analyze/vision endpoint exists but returns HTTP 501 Not Implemented
- [ ] AC-6.2: Vision module interface is documented in code with expected input/output schemas
- [ ] AC-6.3: File type detection identifies image files (JPG, PNG) but routes them to stub
- [ ] AC-6.4: Stub logs image file metadata for future analysis
- [ ] AC-6.5: Architecture documentation describes how vision module will integrate (same embedding → matching pipeline)

**Dependencies:** None (future phase)

---

## Non-Functional Requirements

### NFR-1: Performance

- Embedding generation: < 2 seconds per product description (local model on M3 Pro)
- Vector similarity search: < 500ms for Top-5 matches across 100,000 products
- LLM matching inference: < 5 seconds per item (local llama3)
- End-to-end processing throughput: ≥ 100 items per minute for text-only parsing

### NFR-2: Scalability

- Support up to 10,000 supplier items per file
- Vector database scales to 1 million embeddings with acceptable query performance
- Processing can be parallelized by running multiple queue workers
- Memory usage optimized for 18GB RAM (Apple M3 Pro) via quantization

### NFR-3: Resource Optimization

- Use quantized LLM models to fit in 18GB RAM
- Embedding model runs locally to avoid cloud API costs
- Cloud LLM is optional fallback (not primary path)
- Docker containers have memory limits to prevent OOM crashes

### NFR-4: Reliability

- Failed file parsing does not crash the service (per-row error isolation)
- Queue message retry: 3 attempts with exponential backoff
- Database connection pooling with automatic reconnection
- Graceful degradation if LLM service is unavailable (queue items for retry)

### NFR-5: Observability

- Structured JSON logging for all processing steps
- Log levels: DEBUG (embeddings), INFO (matches), WARN (low confidence), ERROR (failures)
- Metrics exported: queue depth, processing time per item, LLM latency, match confidence distribution
- Integration with existing logging infrastructure

### NFR-6: Security

- File path validation to prevent directory traversal attacks
- Input validation via Pydantic models for all API requests
- LLM prompt injection mitigation (sanitize product descriptions before LLM prompts)
- Environment-based secrets for database and LLM API credentials
- No sensitive data in logs (redact product prices/internal costs)

---

## Success Criteria

**Measurable Outcomes:**

1. **Ingestion Coverage:** Service successfully parses 95% of PDF and merged-cell Excel files that existing parsers reject
2. **Match Accuracy:** LLM-based matching achieves ≥85% precision (confirmed matches are actually same product)
3. **Match Recall:** Finds ≥70% of true product matches that exist across suppliers
4. **Admin Efficiency:** Reduces manual product matching workload by 60% (measured by match_review_queue volume)
5. **Processing Throughput:** Completes full file analysis (100 items) in under 2 minutes on target hardware
6. **System Reliability:** Service maintains 99% uptime with no data corruption incidents

**Qualitative Goals:**

- Admin users report increased confidence in automated matches
- Support team receives fewer escalations about missing product associations
- System gracefully handles edge cases (malformed PDFs, unusual Excel layouts)

---

## Data Models

### Key Entities

**Product Embedding** (New)
- Represents semantic vector representation of a supplier item
- Links to supplier_items table
- Enables fast similarity search

**Supplier Item** (Existing, Extended)
- Existing table from Phase 1
- ml-analyze adds new items with source_type 'ml_analyzed'
- product_id field is updated when matches are found

**Match Review Queue** (Existing, Reused)
- Existing table from Phase 4
- ml-analyze adds uncertain matches (70-90% confidence) for manual review

**Parsing Logs** (Existing, Extended)
- Existing error logging table
- ml-analyze logs parsing errors, embedding failures, LLM errors

---

## Error Handling

### Service-Level Error Strategy

**Parsing Errors:**
- Log to parsing_logs with specific error type (malformed_pdf, invalid_table_structure, etc.)
- Continue processing remaining items in file
- Return partial success response with error summary

**Embedding Errors:**
- Retry up to 3 times with exponential backoff
- If embedding fails, mark item as 'embedding_failed' status
- Alert admin via log aggregation (Sentry/CloudWatch)

**LLM Errors:**
- Timeout: 30 seconds per LLM call, then retry
- Invalid JSON response: Log and treat as no-match (confidence 0%)
- LLM service unavailable: Enqueue item for retry after 5 minutes

**Database Errors:**
- Connection pool exhaustion: Queue back-pressure (slow down intake)
- Constraint violations: Log and skip (idempotency)
- Deadlocks: Automatic retry with jitter

---

## Testing Requirements

### Unit Tests

- Pydantic model validation (file schemas, API requests/responses)
- PDF table extraction logic (Markdown formatting correctness)
- Excel merged-cell forward-fill algorithm
- Vector similarity calculation
- LLM prompt construction and response parsing

### Integration Tests

- FastAPI endpoint request/response cycles
- PostgreSQL operations (insert embeddings, update matches)
- Ollama API integration (embedding + LLM inference)
- Queue message processing (arq task execution)

### End-to-End Tests

1. Upload PDF file → Parse → Embed → Match → Verify database update
2. Upload messy Excel → Normalize → Embed → Find duplicates → Check match_review_queue
3. Trigger vision endpoint → Verify stub response
4. Simulate LLM failure → Verify retry logic → Confirm eventual success
5. Process 1000-item file → Measure throughput → Verify no memory leaks

**Coverage Target:** ≥80% for business logic (parsers, matching)

---

## Deployment

### Environment Variables

```bash
# ml-analyze Service
FASTAPI_PORT=8001
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=llama3
CLOUD_LLM_API_KEY=optional_cloud_api_key
CLOUD_LLM_PROVIDER=openai  # or anthropic, google, etc.
MATCH_CONFIDENCE_AUTO_THRESHOLD=0.9
MATCH_CONFIDENCE_REVIEW_THRESHOLD=0.7
LOG_LEVEL=INFO
```

### Docker Configuration

- New service container: `ml-analyze` in docker-compose.yml
- Depends on: postgres, redis (existing containers)
- Ollama runs in separate container or host machine
- Health check: GET /health endpoint returns 200
- Resource limits: memory 16GB, CPU 4 cores

### Migration Strategy

1. Enable pgvector extension in PostgreSQL: `CREATE EXTENSION vector;`
2. Run Alembic migration to create product_embeddings table
3. Deploy ml-analyze service container
4. Update Bun API to add proxy endpoints to ml-analyze
5. No changes to frontend required (uses existing match_review_queue UI)

---

## Algorithm Specification

Following the KISS principle, we use proven AI techniques with minimal custom logic:

**Embedding Algorithm:** Sentence Transformers (via Ollama nomic-embed-text)
- **Model:** 256-dimension embeddings (balance of speed and accuracy)
- **Complexity:** O(n) for embedding generation, O(log n) for vector search with HNSW index
- **Justification:** Pre-trained model, no training data needed, fast on CPU
- **Limitations:** English-language only for MVP; multilingual models available for future

**Matching Algorithm:** LLM-based semantic reasoning
- **Approach:** Prompt engineering with structured JSON output
- **Complexity:** O(1) per item (Top-5 candidates only, constant time per LLM call)
- **Justification:** Handles ambiguous cases better than rule-based matching (e.g., "AA Battery 1.5V" vs "Alkaline Battery Size AA")
- **Limitations:** Non-deterministic (same input may yield different outputs); mitigated by confidence thresholds

**Future Evolution:** Fine-tuned embedding model
- **Trigger:** When dataset size > 50,000 products and domain-specific vocabulary causes poor matches
- **Migration Path:** Collect match_review_queue corrections as training data; fine-tune embedding model; A/B test against base model

---

## Rollback Plan

**Trigger Conditions:**

- Match precision < 70% (too many false positives)
- Service crashes or OOM errors > 5% of requests
- Data corruption detected (invalid product_id links)
- LLM costs exceed budget (if using cloud provider)

**Rollback Steps:**

1. Disable ml-analyze endpoints in Bun API (return 503 Service Unavailable)
2. Stop ml-analyze Docker container
3. Revert database migration if product_embeddings table causes issues
4. Existing parsers and Phase 4 matching continue unaffected
5. Investigate issues in dev environment before redeployment

---

## Documentation

- [x] Feature specification (this document)
- [ ] API documentation (OpenAPI/Swagger auto-generated)
- [ ] Architecture Decision Record: Why LLM-based matching vs. rule-based
- [ ] README update: How to set up Ollama and embedding models
- [ ] Inline code documentation for parser logic and prompt templates
- [ ] Admin user guide: How to trigger ml-analyze and review uncertain matches

---

## Exceptions & Deviations

**Deviation 1: Technical Constraints in Spec**

- **Principle Affected:** Business-focused specification (avoid HOW)
- **Justification:** User explicitly provided technical stack constraints (Python 3.12, LangChain, pgvector, M3 Pro optimization). These are hard requirements that affect feasibility, not implementation details.
- **Remediation Plan:** Planning phase will elaborate on these constraints; this spec documents them as boundaries.

**Deviation 2: Vision Module in Scope**

- **Principle Affected:** MVP focus (avoid future-phase features)
- **Justification:** User requested vision interface design upfront to avoid architectural rework. Stub implementation has minimal cost and ensures clean extension point.
- **Remediation Plan:** None needed; stub is intentionally minimal and documented as future-phase.

---

## Appendix

### References

- Phase 1 (Data Ingestion): `/specs/001-data-ingestion-infra/spec.md`
- Phase 4 (Product Matching Pipeline): `/specs/004-product-matching-pipeline/spec.md`
- Phase 6 (Admin Sync Scheduler): `/specs/006-admin-sync-scheduler/spec.md`
- Ollama Documentation: https://ollama.com/
- pgvector Extension: https://github.com/pgvector/pgvector

### Glossary

- **Embedding:** Numerical vector representation of text that captures semantic meaning
- **Vector Search:** Finding similar items by comparing embedding vectors (cosine similarity)
- **RAG (Retrieval-Augmented Generation):** AI pattern that combines database search with LLM reasoning
- **Forward-Fill:** Spreadsheet technique to copy merged cell values to all affected rows
- **Quantization:** Model compression technique to reduce memory usage (e.g., 16-bit → 8-bit precision)
- **LLM (Large Language Model):** AI model trained on text to perform reasoning and generation tasks
- **Match Confidence:** Probability score (0-1) that two items refer to the same product

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
