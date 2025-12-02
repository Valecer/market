# Feature Plan: ML-Based Product Analysis & Merging Service

**Date:** 2025-12-03

**Status:** Draft

**Owner:** Development Team

---

## Overview

Implement a standalone Python microservice (`ml-analyze`) that uses AI-powered RAG (Retrieval-Augmented Generation) pipeline to intelligently ingest and match complex, unstructured supplier data (PDFs with tables, Excel files with merged cells) that existing regex-based parsers cannot handle. The service performs semantic matching using vector embeddings and LLM reasoning to automatically link supplier items to existing products in the catalog.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility Principle:** ml-analyze service has one focused purpose - handle complex unstructured data that existing parsers cannot process. Clear separation between ingestion (file parsing), embedding (vector storage), and matching (LLM reasoning) modules.

- **Open/Closed Principle:** Uses strategy pattern for file parsers (ExcelStrategy, PdfStrategy) allowing new file types to be added without modifying existing code. VectorService and MergerAgent use dependency injection for swappable LLM providers (Ollama local vs cloud).

- **Liskov Substitution Principle:** All parser strategies implement common TableNormalizer interface with consistent contract (input: file path, output: normalized dict list). LLM providers (Ollama, OpenAI) are swappable via LangChain abstraction.

- **Interface Segregation Principle:** Narrow, focused interfaces: IParser (file → dict), IEmbedder (text → vector), IMatcher (item → matches). No fat interfaces forcing unused method implementations.

- **Dependency Inversion Principle:** FastAPI controllers depend on service abstractions (VectorService, MergerAgent), not concrete implementations. Services depend on repository interfaces, not direct database access.

- **KISS Principle:** Start with text-only processing (defer vision to future). Use pre-trained embedding models (no custom training). Simple confidence thresholds (>90% auto, 70-90% review, <70% reject) rather than complex scoring algorithms.

- **DRY Principle:** Reuses existing database schema (products, supplier_items, match_review_queue, parsing_logs). Centralizes LLM prompt templates. Shares validation logic via Pydantic models.

- **Separation of Concerns:** ml-analyze is a standalone service independent of Bun API and existing Python worker. Communicates via well-defined HTTP API endpoints (no direct database access from Bun). Future queue integration follows existing Redis pattern.

- **Strong Typing:** Python type hints everywhere with Pydantic models for all API requests, queue messages, and database operations. Mypy strict mode compliance.

- **Documentation Requirements:** Will collect LangChain, FastAPI, pgvector docs via mcp context7 before implementation. OpenAPI/Swagger auto-generated for all endpoints.

**Violations/Exceptions:** None. This feature is designed to fully comply with all constitutional principles.

---

## Goals

- [ ] Parse 95% of PDF and merged-cell Excel files that existing parsers reject
- [ ] Achieve ≥85% precision on LLM-based product matching
- [ ] Process 100 items in under 2 minutes on Apple M3 Pro hardware
- [ ] Reduce manual product matching workload by 60%
- [ ] Integrate seamlessly with existing database schema (no modifications required)
- [ ] Support both local (Ollama) and cloud LLM providers via configuration
- [ ] Enable pgvector extension and create product_embeddings table
- [ ] Design and stub vision module interface for future image processing

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- Actual image/photo processing (vision module is stubbed only)
- Replacement of existing Phase 1 parsers (extends, not replaces)
- Real-time processing (follows queue-based pattern like existing system)
- Automated reprocessing of historical supplier data (only new files)
- Direct user-facing UI (existing admin frontend displays results)
- Custom LLM training or fine-tuning (uses pre-trained models)
- Modifications to existing products or supplier_items schema

---

## Success Metrics

How will we measure success?

- **Ingestion Coverage:** 95% of PDFs and merged-cell Excel files successfully parsed
- **Match Precision:** ≥85% of confirmed matches are actually the same product
- **Match Recall:** ≥70% of true matches discovered across suppliers
- **Processing Throughput:** 100 items processed in <2 minutes on M3 Pro
- **Admin Efficiency:** 60% reduction in match_review_queue volume
- **System Reliability:** 99% service uptime with zero data corruption incidents

---

## User Stories

### Story 1: Parse Complex Supplier Files

**As a** procurement admin
**I want** to upload PDF price lists with complex table layouts
**So that** supplier data is automatically extracted without manual data entry

**Acceptance Criteria:**

- [ ] PDF tables are converted to Markdown-formatted text preserving structure
- [ ] Excel files with merged cells are normalized via forward-fill
- [ ] Parsing errors are logged without crashing the service
- [ ] Successfully parsed items appear in supplier_items table with status 'pending_match'

### Story 2: Automatic Product Matching

**As a** procurement admin
**I want** newly ingested supplier items to be automatically matched to existing products
**So that** I don't have to manually link thousands of similar items

**Acceptance Criteria:**

- [ ] High-confidence matches (>90%) are automatically linked to products
- [ ] Medium-confidence matches (70-90%) appear in review queue for manual verification
- [ ] Low-confidence matches (<70%) are rejected and logged
- [ ] Match results are visible in existing admin UI without code changes

### Story 3: Semantic Search for Similar Products

**As a** procurement admin
**I want** the system to find semantically similar products across suppliers
**So that** variations in naming ("AA Battery" vs "Alkaline Battery Size AA") are correctly identified

**Acceptance Criteria:**

- [ ] Vector embeddings capture semantic meaning of product descriptions
- [ ] Similarity search returns Top-5 most relevant matches within 500ms
- [ ] LLM confirms matches using structured reasoning (not just keyword matching)
- [ ] System handles ambiguous cases better than existing Levenshtein matching

### Story 4: Monitor Processing Status

**As a** procurement admin
**I want** to track the progress of file analysis jobs
**So that** I know when data is ready for review

**Acceptance Criteria:**

- [ ] POST /analyze/file returns job_id immediately
- [ ] GET /analyze/status/:job_id shows current state (pending/processing/completed/failed)
- [ ] Status response includes progress percentage and error details
- [ ] Processing completes within 2 minutes for 100-item file

---

## Technical Approach

### Technology Stack

- **Language:** Python 3.12
- **Web Framework:** FastAPI (lightweight, async, auto-generates OpenAPI docs)
- **LLM Orchestration:** LangChain (industry standard for RAG pipelines)
- **LLM Provider:** Ollama (local llama3 primary, cloud fallback configurable)
- **Database:** asyncpg + pgvector (PostgreSQL extension for vector storage)
- **PDF Parsing:** pymupdf4llm (extracts tables as Markdown text)
- **Excel Parsing:** openpyxl + pandas (handles merged cells via forward-fill)
- **Embeddings:** nomic-embed-text via Ollama (efficient for CPU/M3 Pro, 256-dim vectors)
- **Queue:** arq (Redis-based, consistent with existing Python worker)
- **Validation:** Pydantic 2.x (all API requests, queue messages, database models)

### Architecture

High-level architecture: Standalone Python service with 4 main components.

```
[Admin UI] → [Bun API Proxy] → [ml-analyze FastAPI] → [Ollama API]
                                        ↓                      ↓
                                  [PostgreSQL]           [Embeddings]
                                  - supplier_items       - Vector similarity
                                  - product_embeddings
                                  - products
                                  - match_review_queue
```

**ml-analyze Service (Python/FastAPI):**

- **Responsibilities:**
  - Accept file upload requests via HTTP API
  - Parse complex files (PDF, Excel with merged cells) to normalized format
  - Generate semantic embeddings for product descriptions
  - Perform vector similarity search to find candidate matches
  - Use LLM to confirm matches with structured reasoning
  - Write results to database (update product_id links, queue uncertain matches)

- **Endpoints:**
  - `POST /analyze/file` - Trigger file analysis (accepts file URL/path, supplier_id)
  - `GET /analyze/status/:job_id` - Check processing status
  - `POST /analyze/merge` - Trigger batch matching for unlinked items
  - `POST /analyze/vision` - Stub endpoint (returns 501 Not Implemented)
  - `GET /health` - Health check

- **Data flow:**
  1. Receive file reference → Validate → Return job_id
  2. Background task: Parse file → Normalize → Chunk
  3. For each chunk: Generate embedding → Store in product_embeddings
  4. For each item: Vector search → LLM match → Update database

**Bun API (Proxy Layer):**

- **Responsibilities:**
  - Authenticate admin users (JWT validation)
  - Proxy requests to ml-analyze service
  - Return responses to frontend

- **Endpoints:**
  - `POST /admin/analyze/file` → proxies to ml-analyze `POST /analyze/file`
  - `GET /admin/analyze/status/:job_id` → proxies to ml-analyze

**Redis Queue Communication:**

- **Queue names:**
  - `ml-analyze-file-queue` - File processing tasks
  - `ml-analyze-match-queue` - Batch matching tasks

- **Message formats (Pydantic models):**
  ```python
  class FileAnalysisJob(BaseModel):
      job_id: UUID
      file_url: str
      supplier_id: UUID
      created_at: datetime

  class MatchJob(BaseModel):
      job_id: UUID
      supplier_item_ids: list[UUID]
      created_at: datetime
  ```

- **Error handling:**
  - 3 retry attempts with exponential backoff
  - Failed jobs logged to parsing_logs table
  - Dead letter queue for permanent failures

**PostgreSQL Schema:**

- **New table: product_embeddings**
  ```sql
  CREATE TABLE product_embeddings (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      supplier_item_id UUID NOT NULL REFERENCES supplier_items(id),
      embedding vector(768),  -- pgvector type
      model_name VARCHAR(100) NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT NOW(),
      CONSTRAINT unique_item_embedding UNIQUE (supplier_item_id, model_name)
  );

  CREATE INDEX idx_embeddings_similarity
  ON product_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
  ```

- **Tables affected (existing):**
  - `supplier_items` - product_id updated when matches found
  - `match_review_queue` - uncertain matches added for manual review
  - `parsing_logs` - errors logged during processing
  - `products` - referenced during matching (no modifications)

- **Migration plan:**
  1. Enable pgvector: `CREATE EXTENSION IF NOT EXISTS vector;`
  2. Create product_embeddings table with vector column
  3. Create IVFFLAT index for fast cosine similarity search
  4. Alembic migration file: `007_add_product_embeddings.py`

**Frontend (React + Vite + Tailwind v4.1):**

- **No new components required** - Existing admin UI displays results
- Existing `match_review_queue` component shows uncertain matches
- Existing `supplier_items` table shows linked products
- Future: Add "Analyze File" button to supplier detail page (Phase 2)

### Design System

- [ ] N/A - No new frontend components for MVP
- [ ] Will collect documentation via `mcp context7` for: LangChain, FastAPI, pgvector, pymupdf4llm
- [ ] Future UI: Tailwind v4.1 CSS-first approach (no `tailwind.config.js`)

### Module Structure

Following user's architecture specification, organize code into 4 main modules:

**1. Infrastructure (`src/db/`, `migrations/`):**
- `migrations/007_enable_pgvector.py` - Enable vector extension
- `migrations/008_create_embeddings_table.py` - Create product_embeddings
- `src/db/vector_repository.py` - Vector CRUD operations (insert, search)
- `src/db/models.py` - SQLAlchemy models for product_embeddings

**2. Ingestion Pipeline (`src/ingest/`):**
- `table_normalizer.py` - Abstract base class for parsers
  ```python
  class TableNormalizer(ABC):
      @abstractmethod
      async def parse(self, file_path: str) -> list[dict]:
          pass
  ```
- `excel_strategy.py` - ExcelStrategy implementation
  - Uses `openpyxl` to read workbook
  - Detects merged cells via `cell.merge` attribute
  - Forward-fills values: if cells A1:A10 merged, copy A1 value to all rows
  - Returns list of dicts (one per row)
- `pdf_strategy.py` - PdfStrategy implementation
  - Uses `pymupdf4llm.to_markdown()` to extract tables as Markdown
  - Parses Markdown tables to structured dicts
  - Preserves row/column relationships
- `chunker.py` - Splits normalized data into semantic chunks
  - Simple chunking: 1 product row = 1 chunk
  - Future: Combine related rows (e.g., multi-line descriptions)

**3. RAG Core (`src/rag/`):**
- `vector_service.py` - VectorService class
  ```python
  class VectorService:
      async def embed_query(self, text: str) -> list[float]:
          # Call Ollama nomic-embed-text

      async def similarity_search(self, embedding: list[float], top_k: int = 5) -> list[Match]:
          # Query product_embeddings with cosine similarity
  ```
- `merger_agent.py` - MergerAgent LangChain chain
  ```python
  class MergerAgent:
      def __init__(self, llm: ChatOllama, vector_service: VectorService):
          self.llm = llm
          self.vector_service = vector_service

      async def find_matches(self, item: dict) -> list[MatchResult]:
          # 1. Generate embedding for item
          # 2. Vector search for Top-5 candidates
          # 3. Construct LLM prompt with item + candidates
          # 4. Parse JSON response: [{"product_id": UUID, "confidence": 0.95}, ...]
          # 5. Return MatchResult objects
  ```
- `prompt_templates.py` - LLM prompt templates
  ```python
  MATCH_PROMPT = """
  You are a product matching expert. Given a supplier item and 5 potential matches,
  determine which (if any) refer to the same product.

  Supplier Item:
  {item}

  Potential Matches:
  {candidates}

  Return JSON array: [{"product_id": "uuid", "confidence": 0.0-1.0, "reasoning": "..."}]
  """
  ```

**4. API Layer (`src/api/`):**
- `main.py` - FastAPI app initialization, middleware, lifespan
- `routes/analyze.py` - Analysis endpoints
  ```python
  @router.post("/analyze/file")
  async def analyze_file(request: FileAnalysisRequest) -> FileAnalysisResponse:
      job_id = create_job()
      background_tasks.add_task(process_file, job_id, request.file_url)
      return {"job_id": job_id, "status": "pending"}

  @router.get("/analyze/status/{job_id}")
  async def get_status(job_id: UUID) -> JobStatus:
      return fetch_job_status(job_id)
  ```
- `routes/health.py` - Health check endpoint
- `schemas/` - Pydantic request/response models

### Algorithm Choice

Following KISS principle with AI-native approach:

- **Embedding Algorithm:** nomic-embed-text via Ollama
  - Pre-trained 256-dim embeddings (no custom training needed)
  - Optimized for CPU (fast on M3 Pro)
  - Captures semantic similarity better than keyword matching

- **Matching Algorithm:** LLM-based reasoning (llama3)
  - Approach: Prompt engineering with structured JSON output
  - Complexity: O(1) per item (Top-5 candidates only)
  - Justification: Handles ambiguous cases better than rule-based (e.g., "AA Battery 1.5V" vs "Alkaline Battery Size AA")
  - Limitations: Non-deterministic, but mitigated by confidence thresholds

- **Scalability Path:**
  - If match precision drops: Fine-tune embedding model on corrections from match_review_queue
  - If LLM costs high: Implement caching for repeated items
  - If throughput insufficient: Parallelize with multiple workers

### Data Flow

```
[Admin UI] → [Bun API /admin/analyze/file]
                ↓ (proxy)
         [ml-analyze POST /analyze/file]
                ↓ (validate, create job_id)
         [Background Task: process_file]
                ↓
         [1. TableNormalizer.parse(file_url)]
            → ExcelStrategy: openpyxl → forward-fill merged cells → list[dict]
            → PdfStrategy: pymupdf4llm → Markdown tables → list[dict]
                ↓
         [2. For each row: Chunker.chunk(row)]
                ↓
         [3. VectorService.embed_query(chunk_text)]
            → Ollama nomic-embed-text → vector(768)
            → Store in product_embeddings table
                ↓
         [4. MergerAgent.find_matches(item)]
            → VectorService.similarity_search(embedding, top_k=5)
            → Construct prompt: item + Top-5 candidates
            → ChatOllama(llama3).invoke(prompt)
            → Parse JSON: [{"product_id": ..., "confidence": ...}]
                ↓
         [5. Write results to database]
            → If confidence > 0.9: UPDATE supplier_items SET product_id
            → If 0.7 <= confidence < 0.9: INSERT INTO match_review_queue
            → If confidence < 0.7: Log to parsing_logs (no action)
                ↓
         [6. Update job status: completed]
```

---

## Type Safety

### Pydantic Models (Python)

All API requests, queue messages, and database operations use Pydantic v2 models with strict validation.

```python
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from datetime import datetime
from enum import Enum

# API Request/Response Models
class FileAnalysisRequest(BaseModel):
    file_url: HttpUrl | str  # HTTP URL or file:// path
    supplier_id: UUID
    file_type: Literal["pdf", "excel", "csv"]

class FileAnalysisResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    message: str

class JobStatus(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    progress_percentage: int = Field(ge=0, le=100)
    items_processed: int
    items_total: int
    errors: list[str] = []
    created_at: datetime
    completed_at: datetime | None = None

# Queue Message Models
class FileAnalysisJob(BaseModel):
    job_id: UUID
    file_url: str
    supplier_id: UUID
    file_type: str
    created_at: datetime

class MatchJob(BaseModel):
    job_id: UUID
    supplier_item_ids: list[UUID]
    created_at: datetime

# Domain Models
class MatchResult(BaseModel):
    product_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    similarity_score: float

class NormalizedRow(BaseModel):
    """Normalized product data from parser"""
    name: str
    description: str | None = None
    price: float | None = None
    sku: str | None = None
    category: str | None = None
    characteristics: dict[str, Any] = {}

# Database Models (SQLAlchemy + Pydantic hybrid)
class ProductEmbedding(BaseModel):
    id: UUID
    supplier_item_id: UUID
    embedding: list[float]  # vector(768) in DB
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True  # Allow SQLAlchemy model conversion
```

### TypeScript Types (Bun API Proxy)

```typescript
// services/bun-api/src/types/ml-analyze.types.ts
export interface FileAnalysisRequest {
  file_url: string;
  supplier_id: string;  // UUID string
  file_type: 'pdf' | 'excel' | 'csv';
}

export interface FileAnalysisResponse {
  job_id: string;  // UUID string
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress_percentage: number;
  items_processed: number;
  items_total: number;
  errors: string[];
  created_at: string;  // ISO datetime
  completed_at: string | null;
}
```

---

## Testing Strategy

### Unit Tests (Python)

- **Parser Modules:**
  - `test_excel_strategy.py` - Verify merged cell forward-fill logic
  - `test_pdf_strategy.py` - Verify Markdown table extraction
  - `test_chunker.py` - Verify row-to-chunk conversion

- **RAG Core:**
  - `test_vector_service.py` - Mock Ollama API, verify embedding generation
  - `test_merger_agent.py` - Mock LLM responses, verify match logic
  - `test_prompt_templates.py` - Verify template rendering

- **API Layer:**
  - `test_routes.py` - FastAPI TestClient for endpoint validation
  - `test_schemas.py` - Pydantic model validation edge cases

**Tools:** pytest, pytest-asyncio, pytest-cov, faker (for test data)

**Coverage Target:** ≥80% for all business logic

### Integration Tests

- **Database Integration:**
  - Test pgvector similarity search with real vectors
  - Test transaction handling and rollbacks
  - Verify index performance on product_embeddings

- **Ollama Integration:**
  - Test embedding generation with actual Ollama API
  - Test LLM inference with real llama3 model
  - Measure latency and timeout handling

- **Queue Integration:**
  - Test arq job enqueue/dequeue
  - Verify retry logic with failing jobs
  - Test dead letter queue for permanent failures

**Tools:** pytest with Docker Compose (spin up test DB + Ollama)

### E2E Tests

1. **PDF Upload Flow:**
   - Upload sample PDF → Parse → Embed → Match → Verify database updates
   - Assert: supplier_items updated, match_review_queue populated correctly

2. **Excel Upload Flow:**
   - Upload Excel with merged cells → Normalize → Embed → Match → Verify
   - Assert: Forward-fill correct, embeddings stored, matches found

3. **Vision Stub Flow:**
   - Upload image file → Verify 501 Not Implemented response
   - Assert: File metadata logged for future analysis

4. **Error Handling Flow:**
   - Upload corrupted PDF → Verify graceful failure → Check parsing_logs
   - Assert: Service remains stable, error logged, job status = failed

**Tools:** pytest + httpx for API calls

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **LLM non-determinism causes inconsistent matches** | High | High | Implement confidence thresholds (70-90% → manual review), log LLM reasoning for debugging, version prompts |
| **Ollama service unavailable** | High | Medium | Graceful degradation: queue jobs for retry, add cloud LLM fallback via config, health checks |
| **pgvector index performance degrades at scale** | Medium | Medium | Tune IVFFLAT lists parameter, monitor query latency, implement index rebuilds, consider HNSW index |
| **PDF parsing fails on complex layouts** | Medium | High | Per-row error isolation (log to parsing_logs), support manual CSV export as fallback, iterate on parser |
| **Memory exhaustion on large files** | High | Low | Stream processing (chunk-by-chunk), set Docker memory limits (16GB), implement file size validation |
| **LLM costs exceed budget (if using cloud)** | Medium | Low | Prioritize local Ollama, implement caching for repeated items, monitor costs with alerts |
| **Embedding model changes break existing vectors** | Low | Low | Store model_name in product_embeddings, support multiple models concurrently, versioned migrations |

---

## Dependencies

### Python Packages (requirements.txt)

```python
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9  # For pgvector
langchain==0.1.4
langchain-community==0.0.17
pymupdf4llm==0.0.5  # PDF to Markdown
openpyxl==3.1.2
pandas==2.2.0
arq==0.25.0  # Redis queue
redis==5.0.1
httpx==0.26.0  # For file downloads
python-multipart==0.0.6  # File uploads
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
mypy==1.8.0
```

### System Dependencies

- **Ollama:** Must be installed and running
  - Models required: `nomic-embed-text`, `llama3`
  - Installation: `curl -fsSL https://ollama.com/install.sh | sh`
  - Pull models: `ollama pull nomic-embed-text && ollama pull llama3`

- **PostgreSQL 16 with pgvector:**
  - Extension: `CREATE EXTENSION vector;`
  - Already installed in docker-compose.yml

- **Redis 7:**
  - Already available in existing infrastructure

### External Services

- **Ollama API:** http://localhost:11434 (local) or cloud endpoint
- **PostgreSQL:** Existing database (marketbel)
- **Redis:** Existing queue infrastructure

### Infrastructure Changes

**Docker Compose:**
```yaml
services:
  ml-analyze:
    build: ./services/ml-analyze
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/marketbel
      REDIS_URL: redis://redis:6379
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      OLLAMA_EMBEDDING_MODEL: nomic-embed-text
      OLLAMA_LLM_MODEL: llama3
    depends_on:
      - postgres
      - redis
    mem_limit: 16g
    cpus: 4
```

**Environment Variables (.env):**
```bash
# ml-analyze Service
FASTAPI_PORT=8001
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=llama3
CLOUD_LLM_API_KEY=  # Optional cloud fallback
CLOUD_LLM_PROVIDER=openai  # or anthropic
MATCH_CONFIDENCE_AUTO_THRESHOLD=0.9
MATCH_CONFIDENCE_REVIEW_THRESHOLD=0.7
LOG_LEVEL=INFO
EMBEDDING_DIMENSIONS=768
VECTOR_INDEX_LISTS=100  # IVFFLAT tuning parameter
```

---

## Implementation Phases

Following the execution steps specified by user:

### Phase 0: Infrastructure Setup (Days 1-2)

- [ ] Enable pgvector extension in PostgreSQL
- [ ] Create Alembic migration for product_embeddings table
- [ ] Add ml-analyze container to docker-compose.yml
- [ ] Set up Ollama with nomic-embed-text and llama3 models
- [ ] Initialize FastAPI project structure (src/api/, src/db/, src/ingest/, src/rag/)
- [ ] Configure environment variables and settings module

### Phase 1: Ingestion Pipeline (Days 3-5)

- [ ] Implement TableNormalizer abstract base class
- [ ] Implement ExcelStrategy with merged cell forward-fill logic
- [ ] Implement PdfStrategy using pymupdf4llm for Markdown extraction
- [ ] Implement Chunker for row-to-chunk conversion
- [ ] Write unit tests for all parser strategies (≥80% coverage)
- [ ] Test with sample PDF and Excel files

### Phase 2: RAG Core (Days 6-9)

- [ ] Implement VectorService (embed_query, similarity_search)
- [ ] Connect LangChain to Ollama nomic-embed-text for embeddings
- [ ] Implement MergerAgent LangChain chain
- [ ] Design and test LLM prompt templates for matching
- [ ] Connect ChatOllama for llama3 inference
- [ ] Implement confidence threshold logic (>0.9 auto, 0.7-0.9 review, <0.7 reject)
- [ ] Write unit tests with mocked Ollama responses
- [ ] Integration tests with real Ollama API

### Phase 3: API Layer (Days 10-12)

- [ ] Implement FastAPI endpoints (POST /analyze/file, GET /analyze/status/:job_id)
- [ ] Implement background task processing with job status tracking
- [ ] Implement POST /analyze/vision stub (returns 501)
- [ ] Add health check endpoint
- [ ] Configure OpenAPI/Swagger auto-generation
- [ ] Implement error handling and logging
- [ ] Write API integration tests

### Phase 4: Database Integration (Days 13-14)

- [ ] Implement VectorRepository for product_embeddings CRUD
- [ ] Implement database writes (update supplier_items.product_id)
- [ ] Implement match_review_queue insertions for uncertain matches
- [ ] Implement parsing_logs error logging
- [ ] Test pgvector similarity search performance
- [ ] Tune IVFFLAT index parameters

### Phase 5: End-to-End Testing & Optimization (Days 15-16)

- [ ] E2E tests: PDF upload → parse → embed → match → verify DB
- [ ] E2E tests: Excel upload → normalize → embed → match → verify
- [ ] Performance testing: 100 items in <2 minutes on M3 Pro
- [ ] Memory profiling and optimization
- [ ] Error scenario testing (corrupted files, LLM failures)

### Phase 6: Bun API Proxy & Deployment (Days 17-18)

- [ ] Add proxy endpoints to Bun API (POST /admin/analyze/file)
- [ ] Add JWT authentication to proxy layer
- [ ] Update docker-compose.yml with ml-analyze service
- [ ] Write deployment documentation (README, quickstart guide)
- [ ] Run full system integration test
- [ ] Deploy to staging environment

**Estimated Duration:** 18 days (3.5 weeks)

---

## Open Questions

- [x] **Embedding dimension:** Use 768-dim (nomic-embed-text default) or 256-dim? → Resolved: User specified 768 in requirements
- [x] **Vector index type:** IVFFLAT or HNSW? → Resolved: Start with IVFFLAT (simpler), migrate to HNSW if needed
- [x] **LLM temperature:** What temperature setting for llama3 matching? → Recommend 0.1 (low temperature for deterministic outputs)
- [x] **Batch size:** Process items one-by-one or in batches? → Resolved: One-by-one for simplicity (MVP), batch optimization later
- [ ] **Cloud LLM provider:** If Ollama fails, which cloud provider? OpenAI, Anthropic, Google? → Deferred: Make configurable via env var
- [ ] **File size limits:** Maximum PDF/Excel file size to accept? → Recommend 50MB limit, validate at API boundary

---

## References

### Feature Specification
- [Feature Spec](/Users/valecer/work/sites/marketbel/specs/007-ml-analyze/spec.md)

### External Documentation (to be collected via mcp context7)
- LangChain Documentation: https://python.langchain.com/docs/get_started/introduction
- FastAPI Documentation: https://fastapi.tiangolo.com/
- pgvector Extension: https://github.com/pgvector/pgvector
- pymupdf4llm: https://pymupdf.readthedocs.io/en/latest/
- Ollama API: https://ollama.com/

### Related Phases
- Phase 1 (Data Ingestion): `/specs/001-data-ingestion-infra/`
- Phase 4 (Product Matching): `/specs/004-product-matching-pipeline/`
- Phase 6 (Admin Sync): `/specs/006-admin-sync-scheduler/`

### Project Constitution
- [Constitutional Principles](/.specify/memory/constitution.md)

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review

---

**Next Steps:**

1. ✅ Phase 0 complete: Plan approved, ready for implementation
2. → Phase 1: Generate research.md (collect technology documentation)
3. → Phase 2: Generate data-model.md and API contracts
4. → Phase 3: Begin implementation following tasks.md
