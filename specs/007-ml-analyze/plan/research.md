# Technology Research: ML-Based Product Analysis & Merging Service

**Date:** 2025-12-03

**Status:** Complete

**Purpose:** Document technology decisions and implementation patterns for the ml-analyze RAG pipeline.

---

## Research Summary

This document consolidates research findings for key technologies used in the ml-analyze service. All decisions prioritize local-first deployment, CPU optimization (Apple M3 Pro), and integration with existing Marketbel infrastructure.

---

## 1. LLM Orchestration: LangChain

### Decision

Use **LangChain** as the primary framework for orchestrating RAG (Retrieval-Augmented Generation) pipelines with Ollama integration.

### Rationale

- **Industry Standard:** LangChain is the de facto framework for RAG pipelines with extensive community support
- **Ollama Integration:** First-class support via `langchain-ollama` package for both embeddings and chat models
- **Abstraction Layer:** Provides clean interfaces for swapping LLM providers (Ollama local ↔ cloud fallback)
- **Component Ecosystem:** Pre-built tools for vector stores, retrievers, and chains
- **Type Safety:** Strong typing with Pydantic models for all data structures

### Key Implementation Patterns

**Ollama Embeddings:**
```python
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",  # Optimized for CPU, 256-dim vectors
    base_url="http://localhost:11434"
)

# Generate embedding for a single query
vector = embeddings.embed_query("Product description text")

# Batch embed multiple documents
vectors = embeddings.embed_documents(["doc1", "doc2", "doc3"])
```

**Vector Store Integration:**
```python
from langchain.vectorstores import InMemoryVectorStore

# For testing/development (in-memory)
vector_store = InMemoryVectorStore(embeddings)

# For production: Custom PostgreSQL + pgvector implementation
# (LangChain doesn't have native asyncpg support, we'll implement custom)
```

**RAG Retrieval Tool:**
```python
from langchain.tools import tool

@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Retrieve similar products for matching."""
    retrieved_docs = vector_store.similarity_search(query, k=5)

    serialized = "\n\n".join(
        f"Product: {doc.metadata['name']}\n"
        f"Description: {doc.page_content}\n"
        f"Supplier: {doc.metadata['supplier_id']}"
        for doc in retrieved_docs
    )

    return serialized, retrieved_docs
```

### Alternatives Considered

- **LlamaIndex:** More opinionated framework, better for RAG-specific use cases
  - ❌ Rejected: LangChain has better Ollama support and is more flexible for custom pipelines

- **Custom Implementation:** Build RAG pipeline from scratch with direct Ollama API calls
  - ❌ Rejected: Reinventing the wheel, LangChain provides battle-tested abstractions

### Dependencies

```python
langchain==0.1.4
langchain-community==0.0.17
langchain-ollama==0.1.0  # Ollama-specific integration
```

### References

- LangChain Docs: https://docs.langchain.com/oss/python/langchain/
- Ollama Integration: https://docs.langchain.com/oss/python/langchain/rag

---

## 2. Web Framework: FastAPI

### Decision

Use **FastAPI** with async/await for all HTTP endpoints and background task processing.

### Rationale

- **Async Native:** Built on Starlette, supports async operations out of the box
- **Auto Documentation:** Generates OpenAPI/Swagger docs automatically (constitutional requirement)
- **Pydantic Integration:** Deep integration with Pydantic v2 for request/response validation
- **Performance:** High throughput, low latency (critical for 100 items/2 minutes target)
- **Type Safety:** Strong typing with Python type hints for all endpoints

### Key Implementation Patterns

**Async Endpoint with Pydantic Validation:**
```python
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID

app = FastAPI(
    title="ml-analyze API",
    description="AI-powered product matching service",
    version="1.0.0"
)

class FileAnalysisRequest(BaseModel):
    file_url: HttpUrl | str
    supplier_id: UUID
    file_type: Literal["pdf", "excel", "csv"]

class FileAnalysisResponse(BaseModel):
    job_id: UUID
    status: Literal["pending"]
    message: str

@app.post("/analyze/file", response_model=FileAnalysisResponse)
async def analyze_file(
    request: FileAnalysisRequest,
    background_tasks: BackgroundTasks
):
    job_id = uuid4()

    # Enqueue background processing
    background_tasks.add_task(
        process_file_task,
        job_id=job_id,
        file_url=request.file_url,
        supplier_id=request.supplier_id
    )

    return FileAnalysisResponse(
        job_id=job_id,
        status="pending",
        message="File analysis started"
    )
```

**Custom Validation with AfterValidator:**
```python
from pydantic import AfterValidator
from typing import Annotated

def validate_file_url(url: str) -> str:
    if not (url.startswith("http") or url.startswith("file://")):
        raise ValueError("Invalid file URL format")
    return url

FileUrl = Annotated[str, AfterValidator(validate_file_url)]

class AnalysisRequest(BaseModel):
    file_url: FileUrl
    # ... other fields
```

**Background Tasks for Long-Running Operations:**
```python
async def process_file_task(job_id: UUID, file_url: str, supplier_id: UUID):
    """Background task for file processing."""
    try:
        # Update job status to 'processing'
        await update_job_status(job_id, "processing")

        # Parse file
        parser = get_parser(file_url)
        normalized_data = await parser.parse(file_url)

        # Embed and match
        for row in normalized_data:
            embedding = await vector_service.embed_query(row['description'])
            matches = await merger_agent.find_matches(row, embedding)
            await save_matches(matches)

        # Update job status to 'completed'
        await update_job_status(job_id, "completed")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await update_job_status(job_id, "failed", error=str(e))
```

### Alternatives Considered

- **Flask:** Simpler but lacks async support, Pydantic integration, auto-docs
  - ❌ Rejected: Not async-native, would require significant boilerplate

- **Django + DRF:** Full-featured but heavyweight for a microservice
  - ❌ Rejected: Overkill for our use case, slower performance

### Dependencies

```python
fastapi==0.109.0
uvicorn[standard]==0.27.0  # ASGI server
pydantic==2.5.0
pydantic-settings==2.1.0  # For environment variable management
```

### References

- FastAPI Docs: https://fastapi.tiangolo.com/
- Async Operations: https://fastapi.tiangolo.com/async/
- Background Tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/

---

## 3. Vector Database: PostgreSQL + pgvector

### Decision

Use **pgvector** extension on existing PostgreSQL database with **asyncpg** for async database operations.

### Rationale

- **Infrastructure Reuse:** Leverages existing PostgreSQL 16 setup (no new database)
- **ACID Guarantees:** Full transactional support for embedding storage and updates
- **Performance:** Optimized indexes (HNSW, IVFFLAT) for fast similarity search
- **Async Support:** asyncpg provides high-performance async PostgreSQL access
- **Distance Metrics:** Supports L2, cosine, and inner product similarity

### Key Implementation Patterns

**Enable pgvector Extension:**
```sql
-- Migration: 007_enable_pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Create Embeddings Table:**
```sql
-- Migration: 008_create_product_embeddings.sql
CREATE TABLE product_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
    embedding vector(768),  -- 768-dim for nomic-embed-text
    model_name VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_item_embedding UNIQUE (supplier_item_id, model_name)
);

-- IVFFLAT index for fast cosine similarity search
-- lists parameter = sqrt(rows), tune as data grows
CREATE INDEX idx_embeddings_cosine_similarity
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Async Similarity Search with asyncpg:**
```python
import asyncpg
from pgvector.asyncpg import register_vector
import numpy as np

# Connection setup
conn = await asyncpg.connect(DATABASE_URL)
await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
await register_vector(conn)

# Insert embedding
embedding = np.array([0.1, 0.2, 0.3, ...])  # 768-dim vector
await conn.execute('''
    INSERT INTO product_embeddings (supplier_item_id, embedding, model_name)
    VALUES ($1, $2, $3)
    ON CONFLICT (supplier_item_id, model_name)
    DO UPDATE SET embedding = EXCLUDED.embedding
''', item_id, embedding, 'nomic-embed-text')

# Similarity search with cosine distance
query_embedding = np.array([...])  # Query vector
results = await conn.fetch('''
    SELECT
        si.id,
        si.name,
        si.description,
        pe.embedding <=> $1 AS distance
    FROM product_embeddings pe
    JOIN supplier_items si ON pe.supplier_item_id = si.id
    WHERE si.product_id IS NOT NULL  -- Only search existing products
    ORDER BY distance
    LIMIT $2
''', query_embedding, 5)  # Top-5 matches

for row in results:
    print(f"Product: {row['name']}, Distance: {row['distance']:.4f}")
```

**Distance Operators:**
- `<->` : L2 (Euclidean) distance
- `<=>` : Cosine distance (1 - cosine similarity)
- `<#>` : Max inner product (negative dot product for ranking)

**Index Types:**

1. **IVFFLAT** (chosen for MVP):
   - Faster build time
   - Lower memory usage
   - Good for initial deployment
   - Tuning: `lists` parameter = sqrt(total_rows)

2. **HNSW** (future upgrade):
   - Better recall (accuracy)
   - Higher memory usage
   - Slower build, faster search
   - Tuning: `m` (connections), `ef_construction` (quality)

### Alternatives Considered

- **Dedicated Vector DB (Pinecone, Weaviate, Milvus):**
  - ❌ Rejected: Adds infrastructure complexity, costs, and another service to maintain
  - pgvector is "good enough" for our scale (< 1M products)

- **In-Memory Vector Store:**
  - ❌ Rejected: No persistence, not suitable for production

### Dependencies

```python
asyncpg==0.29.0
psycopg2-binary==2.9.9  # For pgvector registration (sync fallback)
pgvector==0.3.0  # Python client for pgvector types
```

### Performance Tuning

**IVFFLAT Index Parameters:**
```sql
-- For 10,000 products: lists = 100 (sqrt(10000))
-- For 100,000 products: lists = 316 (sqrt(100000))
-- For 1,000,000 products: lists = 1000

-- Rebuild index when dataset doubles:
REINDEX INDEX idx_embeddings_cosine_similarity;
```

**Query Optimization:**
```sql
-- Set probes for better recall (trade-off: slower queries)
SET ivfflat.probes = 10;  -- Default is 1, higher = better recall

-- Use EXPLAIN ANALYZE to monitor performance
EXPLAIN ANALYZE
SELECT * FROM product_embeddings
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;
```

### References

- pgvector GitHub: https://github.com/pgvector/pgvector
- pgvector-python: https://github.com/pgvector/pgvector-python
- Distance Metrics: https://github.com/pgvector/pgvector#distances

---

## 4. PDF Parsing: pymupdf4llm

### Decision

Use **pymupdf4llm** for extracting PDF tables as Markdown-formatted text.

### Rationale

- **Markdown Output:** Preserves table structure in a format LLMs can understand
- **Table Detection:** Automatically identifies and extracts table regions
- **Lightweight:** Fast, CPU-efficient (no GPU required)
- **Column Preservation:** Maintains row/column relationships critical for product data

### Key Implementation Patterns

**Basic PDF to Markdown:**
```python
import pymupdf4llm

# Extract entire PDF as Markdown
markdown_text = pymupdf4llm.to_markdown("supplier_catalog.pdf")

# Extract specific pages
markdown_text = pymupdf4llm.to_markdown(
    "supplier_catalog.pdf",
    pages=[0, 1, 2]  # First 3 pages
)

# Parse Markdown tables to structured data
import re

def parse_markdown_table(md_text: str) -> list[dict]:
    """Convert Markdown table to list of dicts."""
    lines = md_text.strip().split('\n')

    # Extract header row
    headers = [h.strip() for h in lines[0].split('|') if h.strip()]

    # Skip separator line (|---|---|)
    # Parse data rows
    rows = []
    for line in lines[2:]:  # Skip header and separator
        if not line.strip():
            continue
        values = [v.strip() for v in line.split('|') if v.strip()]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))

    return rows
```

**Integration with TableNormalizer:**
```python
from abc import ABC, abstractmethod

class TableNormalizer(ABC):
    @abstractmethod
    async def parse(self, file_path: str) -> list[dict]:
        """Parse file and return normalized rows."""
        pass

class PdfStrategy(TableNormalizer):
    async def parse(self, file_path: str) -> list[dict]:
        """Extract tables from PDF as Markdown, then parse."""
        # Extract Markdown
        markdown = pymupdf4llm.to_markdown(file_path)

        # Parse Markdown tables
        tables = self.extract_tables(markdown)

        # Normalize to standard format
        normalized = []
        for table in tables:
            for row in table:
                normalized.append({
                    'name': row.get('Product Name', row.get('Name', '')),
                    'description': row.get('Description', ''),
                    'price': self.parse_price(row.get('Price', '0')),
                    'sku': row.get('SKU', row.get('Code', '')),
                    'category': row.get('Category', ''),
                    'raw_data': row  # Preserve original for debugging
                })

        return normalized

    def extract_tables(self, markdown: str) -> list[list[dict]]:
        """Extract all tables from Markdown text."""
        # Split by double newlines to find table blocks
        blocks = markdown.split('\n\n')
        tables = []

        for block in blocks:
            if '|' in block and '---' in block:  # Markdown table format
                table = self.parse_markdown_table(block)
                if table:
                    tables.append(table)

        return tables
```

### Alternatives Considered

- **pdfplumber:** More detailed table extraction
  - ✅ Keep as fallback option if pymupdf4llm fails on complex PDFs

- **PyPDF2:** Basic PDF parsing
  - ❌ Rejected: Doesn't preserve table structure

- **Camelot/Tabula:** Table extraction libraries
  - ❌ Rejected: Requires Java (Tabula) or complex dependencies

### Dependencies

```python
pymupdf4llm==0.0.5
PyMuPDF==1.23.8  # Core dependency of pymupdf4llm
```

### References

- pymupdf4llm: https://pymupdf.readthedocs.io/en/latest/

---

## 5. Excel Parsing: openpyxl + pandas

### Decision

Use **openpyxl** for merged cell detection and **pandas** for data normalization.

### Rationale

- **Merged Cell Support:** openpyxl can detect and handle merged cells
- **Forward-Fill Logic:** pandas `fillna(method='ffill')` handles forward-filling elegantly
- **Type Coercion:** pandas automatically infers data types (dates, numbers, strings)
- **Familiar API:** Standard library in data engineering, well-documented

### Key Implementation Patterns

**Detect and Forward-Fill Merged Cells:**
```python
from openpyxl import load_workbook
import pandas as pd

class ExcelStrategy(TableNormalizer):
    async def parse(self, file_path: str) -> list[dict]:
        """Parse Excel with merged cell handling."""
        wb = load_workbook(file_path)
        ws = wb.active

        # Extract data with merged cell markers
        data = []
        for row in ws.iter_rows(values_only=False):
            row_data = []
            for cell in row:
                # If cell is part of a merged range, use the top-left value
                if cell.coordinate in ws.merged_cells:
                    # Find the merged range
                    for merged_range in ws.merged_cells.ranges:
                        if cell.coordinate in merged_range:
                            # Get top-left cell of merge
                            top_left = ws.cell(
                                merged_range.min_row,
                                merged_range.min_col
                            )
                            row_data.append(top_left.value)
                            break
                else:
                    row_data.append(cell.value)
            data.append(row_data)

        # Convert to DataFrame for easy forward-fill
        df = pd.DataFrame(data[1:], columns=data[0])  # First row = headers

        # Forward-fill merged cells (NaN values)
        df = df.fillna(method='ffill')

        # Convert to list of dicts
        return df.to_dict('records')
```

**Alternative: Pandas with merged cell handling:**
```python
import pandas as pd

class ExcelStrategy(TableNormalizer):
    async def parse(self, file_path: str) -> list[dict]:
        """Simpler pandas-based approach."""
        # Read Excel (pandas doesn't handle merged cells by default)
        df = pd.read_excel(file_path, engine='openpyxl')

        # Forward-fill all NaN values (simple but effective)
        df = df.fillna(method='ffill')

        # Normalize column names
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

        # Convert to standard format
        normalized = []
        for _, row in df.iterrows():
            normalized.append({
                'name': row.get('product_name', row.get('name', '')),
                'description': row.get('description', ''),
                'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else None,
                'sku': str(row.get('sku', row.get('code', ''))),
                'category': row.get('category', ''),
                'raw_data': row.to_dict()
            })

        return normalized
```

### Alternatives Considered

- **xlrd:** Older library, doesn't support .xlsx well
  - ❌ Rejected: Deprecated for .xlsx files

- **pyexcel:** Unified API for multiple formats
  - ❌ Rejected: openpyxl + pandas is more standard

### Dependencies

```python
openpyxl==3.1.2
pandas==2.2.0
```

### References

- openpyxl Docs: https://openpyxl.readthedocs.io/
- pandas Excel I/O: https://pandas.pydata.org/docs/user_guide/io.html#excel-files

---

## 6. Embedding Model: nomic-embed-text (via Ollama)

### Decision

Use **nomic-embed-text** embedding model via Ollama for local, CPU-optimized vector generation.

### Rationale

- **CPU Optimized:** Efficient on Apple M3 Pro (no GPU required)
- **Small Footprint:** 256-dimension vectors (vs 1536 for OpenAI) = faster search, less storage
- **Local Execution:** No API costs, no data privacy concerns
- **Good Quality:** Competitive with OpenAI embeddings for semantic similarity

### Key Implementation Patterns

**Install and Pull Model:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text
```

**Generate Embeddings:**
```python
from langchain_ollama import OllamaEmbeddings

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"
)

# Single embedding
text = "Energizer AA Alkaline Batteries, 24 Pack"
vector = embeddings.embed_query(text)
print(f"Embedding dimensions: {len(vector)}")  # 768

# Batch embeddings (more efficient)
texts = [
    "Product 1 description",
    "Product 2 description",
    "Product 3 description"
]
vectors = embeddings.embed_documents(texts)
```

### Alternatives Considered

- **OpenAI Embeddings (text-embedding-3-small):**
  - ✅ Higher quality, 1536 dimensions
  - ❌ Rejected: Requires API calls, costs money, 90ms latency

- **SentenceTransformers (all-MiniLM-L6-v2):**
  - ✅ Very lightweight (384 dims), fast
  - ❌ Rejected: Ollama integration is more consistent with LLM setup

### Performance Characteristics

- **Embedding Time:** ~50-100ms per text on M3 Pro
- **Batch Processing:** 10 items/second
- **Vector Size:** 768 floats * 4 bytes = 3KB per embedding
- **Index Size:** 1M products = 3GB of embeddings

### Dependencies

Ollama manages model downloads, no Python dependencies beyond `langchain-ollama`.

### References

- Ollama Models: https://ollama.com/library/nomic-embed-text
- Nomic AI: https://www.nomic.ai/

---

## 7. LLM for Matching: llama3 (via Ollama)

### Decision

Use **llama3** via Ollama for product matching with structured JSON output.

### Rationale

- **Local Execution:** Runs on M3 Pro (quantized 8-bit), ~10GB RAM
- **Structured Output:** Can generate JSON reliably with proper prompting
- **Reasoning Quality:** Handles ambiguous product name variations well
- **No API Costs:** Free local inference vs $0.50/1M tokens (cloud)

### Key Implementation Patterns

**Initialize LLM:**
```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3",
    base_url="http://localhost:11434",
    temperature=0.1,  # Low temperature for deterministic outputs
    format="json"  # Request JSON output format
)
```

**Structured Matching Prompt:**
```python
from langchain.prompts import ChatPromptTemplate

MATCH_PROMPT = ChatPromptTemplate.from_template("""
You are a product matching expert. Analyze if the following supplier item matches any of the candidate products.

Supplier Item:
- Name: {item_name}
- Description: {item_description}
- Price: {item_price}
- SKU: {item_sku}

Candidate Matches (from other suppliers):
{candidates}

For each candidate, determine:
1. Is it the SAME product (not just similar)?
2. Confidence score (0.0 - 1.0)
3. Reasoning for your decision

Output JSON array:
[
  {{
    "product_id": "uuid-here",
    "is_match": true/false,
    "confidence": 0.95,
    "reasoning": "Both are Energizer AA 24-packs with identical specs"
  }},
  ...
]

Only mark as match if you are CERTAIN they are identical products.
""")

# Invoke LLM
chain = MATCH_PROMPT | llm
response = chain.invoke({
    "item_name": "Energizer AA Batteries 24pk",
    "item_description": "Alkaline batteries, long-lasting",
    "item_price": "$19.99",
    "item_sku": "EN-AA-24",
    "candidates": candidates_text
})

# Parse JSON response
import json
matches = json.loads(response.content)
```

**Error Handling for Non-JSON Responses:**
```python
import json
from pydantic import BaseModel, ValidationError

class MatchResult(BaseModel):
    product_id: UUID
    is_match: bool
    confidence: float
    reasoning: str

def parse_llm_response(response: str) -> list[MatchResult]:
    """Safely parse LLM JSON response."""
    try:
        data = json.loads(response)
        return [MatchResult(**item) for item in data]
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.debug(f"Raw response: {response}")
        return []  # Return empty list, treat as no matches
```

### Alternatives Considered

- **GPT-4 / Claude (cloud APIs):**
  - ✅ Higher quality reasoning
  - ❌ Rejected: Costs, latency, requires internet, data privacy concerns

- **Smaller Ollama models (mistral, phi):**
  - ✅ Faster, less RAM
  - ❌ Rejected: Lower reasoning quality for nuanced product matching

### Performance Characteristics

- **Inference Time:** 2-5 seconds per item on M3 Pro (5 candidates)
- **Throughput:** 12-30 items/minute (single-threaded)
- **Memory:** ~10GB RAM for llama3:8b quantized
- **Determinism:** Temperature 0.1 gives ~80% consistency on same input

### Dependencies

```bash
ollama pull llama3
```

### References

- Ollama llama3: https://ollama.com/library/llama3
- Structured Output: https://ollama.com/blog/structured-outputs

---

## 8. Queue System: arq (Redis-based)

### Decision

Use **arq** for background job processing, consistent with existing Python worker (Phase 1).

### Rationale

- **Consistency:** Same queue system as existing python-ingestion service
- **Redis-based:** Leverages existing Redis infrastructure
- **Async Native:** Built on asyncio, integrates with FastAPI
- **Retry Logic:** Built-in exponential backoff and failure handling
- **Job Status Tracking:** Can query job state for `/analyze/status/:job_id` endpoint

### Key Implementation Patterns

**Define Worker Functions:**
```python
from arq import create_pool
from arq.connections import RedisSettings

async def process_file_job(ctx, job_id: str, file_url: str, supplier_id: str):
    """ARQ worker function for file processing."""
    logger.info(f"Processing job {job_id}: {file_url}")

    # Update job status
    await update_job_status(job_id, "processing")

    try:
        # Execute processing pipeline
        parser = get_parser(file_url)
        data = await parser.parse(file_url)

        for row in data:
            await embed_and_match(row, supplier_id)

        await update_job_status(job_id, "completed")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        await update_job_status(job_id, "failed", error=str(e))
        raise  # Trigger retry

class WorkerSettings:
    functions = [process_file_job]
    redis_settings = RedisSettings(
        host='localhost',
        port=6379,
        database=0
    )
    max_jobs = 5  # Parallel worker limit
    job_timeout = 600  # 10 minutes max per job
    max_tries = 3  # Retry up to 3 times
    retry_jobs = True

# Run worker
if __name__ == '__main__':
    from arq import run_worker
    run_worker(WorkerSettings)
```

**Enqueue Jobs from FastAPI:**
```python
from arq import create_pool
from arq.connections import RedisSettings

# Create Redis pool at startup
redis_pool = None

@app.on_event("startup")
async def startup():
    global redis_pool
    redis_pool = await create_pool(RedisSettings())

@app.on_event("shutdown")
async def shutdown():
    await redis_pool.close()

@app.post("/analyze/file")
async def analyze_file(request: FileAnalysisRequest):
    job_id = str(uuid4())

    # Enqueue job
    job = await redis_pool.enqueue_job(
        'process_file_job',
        job_id,
        str(request.file_url),
        str(request.supplier_id)
    )

    return {"job_id": job_id, "status": "pending"}
```

### Alternatives Considered

- **Celery:** More mature, feature-rich
  - ❌ Rejected: Heavier, not asyncio-native, overkill for our use case

- **FastAPI BackgroundTasks:** Simple built-in solution
  - ❌ Rejected: No persistence, no retry logic, lost on server restart

### Dependencies

```python
arq==0.25.0
redis==5.0.1
```

### References

- arq Documentation: https://arq-docs.helpmanual.io/

---

## Summary of Key Decisions

| Technology | Decision | Rationale |
|------------|----------|-----------|
| **LLM Framework** | LangChain | Industry standard, Ollama integration, RAG tools |
| **Web Framework** | FastAPI | Async-native, auto-docs, Pydantic integration |
| **Vector DB** | pgvector + asyncpg | Reuses existing Postgres, ACID guarantees, async |
| **PDF Parser** | pymupdf4llm | Markdown output, table preservation, lightweight |
| **Excel Parser** | openpyxl + pandas | Merged cell support, forward-fill, familiar API |
| **Embeddings** | nomic-embed-text (Ollama) | CPU-optimized, local, 768-dim, no API costs |
| **Matching LLM** | llama3 (Ollama) | Local inference, JSON output, good reasoning |
| **Queue System** | arq (Redis) | Consistent with existing worker, async, retry |

---

**Next Steps:**

1. ✅ Research complete
2. → Generate data-model.md (database schema design)
3. → Generate API contracts (OpenAPI schemas)
4. → Create quickstart.md (development setup guide)
