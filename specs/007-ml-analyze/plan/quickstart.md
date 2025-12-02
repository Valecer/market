# Quickstart Guide: ml-analyze Service

**Estimated Time:** 15 minutes

**Prerequisites:**
- Docker + Docker Compose v2
- Ollama installed locally (or willingness to install)
- Basic familiarity with Python async/await

---

## Step 1: Install Ollama (2 minutes)

### macOS / Linux

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull nomic-embed-text  # Embedding model (256-dim vectors)
ollama pull llama3            # LLM for product matching

# Verify installation
ollama list
# Should show: nomic-embed-text, llama3
```

### Windows

Download from https://ollama.com/download and follow installer instructions.

---

## Step 2: Setup Database (3 minutes)

### Enable pgvector Extension

```bash
# Start PostgreSQL (if not already running)
docker-compose up -d postgres

# Connect to database
docker-compose exec postgres psql -U marketbel -d marketbel

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify installation
\dx vector
# Should show version 0.5.0 or later

\q
```

### Run Migrations

```bash
cd services/python-ingestion

# Activate virtual environment
source venv/bin/activate

# Run migrations
alembic upgrade head

# Verify product_embeddings table exists
psql -U marketbel -d marketbel -c "\d product_embeddings"
```

---

## Step 3: Install ml-analyze Service (5 minutes)

### Create Project Structure

```bash
# From repo root
mkdir -p services/ml-analyze/src/{api,db,ingest,rag,tests}
cd services/ml-analyze
```

### Create requirements.txt

```bash
cat > requirements.txt <<'EOF'
# Web Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0

# Data Validation
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
asyncpg==0.29.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.25
alembic==1.13.1

# LLM & RAG
langchain==0.1.4
langchain-community==0.0.17
langchain-ollama==0.1.0
pgvector==0.3.0

# File Parsing
pymupdf4llm==0.0.5
openpyxl==3.1.2
pandas==2.2.0

# Queue
arq==0.25.0
redis==5.0.1

# HTTP Client
httpx==0.26.0

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0

# Type Checking
mypy==1.8.0
EOF
```

### Create Virtual Environment

```bash
# Create and activate venv
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify LangChain + Ollama integration
python -c "from langchain_ollama import OllamaEmbeddings; print('OK')"
```

### Create .env File

```bash
cat > .env <<'EOF'
# FastAPI
FASTAPI_PORT=8001

# Database
DATABASE_URL=postgresql://marketbel:password@localhost:5432/marketbel

# Redis
REDIS_URL=redis://localhost:6379/0

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=llama3

# Matching Thresholds
MATCH_CONFIDENCE_AUTO_THRESHOLD=0.9
MATCH_CONFIDENCE_REVIEW_THRESHOLD=0.7

# Performance
EMBEDDING_DIMENSIONS=768
VECTOR_INDEX_LISTS=100

# Logging
LOG_LEVEL=INFO
EOF
```

---

## Step 4: Create Minimal Service (3 minutes)

### Create src/api/main.py

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="ml-analyze API",
    description="AI-powered product matching service",
    version="1.0.0"
)

class HealthResponse(BaseModel):
    status: str
    version: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Test the Service

```bash
# Start the service
python src/api/main.py

# In another terminal, test health endpoint
curl http://localhost:8001/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}

# View auto-generated docs
open http://localhost:8001/docs
```

---

## Step 5: Test Ollama Integration (2 minutes)

### Create test_ollama.py

```python
import asyncio
from langchain_ollama import OllamaEmbeddings, ChatOllama

async def test_embeddings():
    """Test embedding generation."""
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )

    text = "Energizer AA Alkaline Batteries, 24 Pack"
    vector = await embeddings.aembed_query(text)

    print(f"✅ Embedding generated: {len(vector)} dimensions")
    print(f"Sample values: {vector[:5]}")

async def test_llm():
    """Test LLM inference."""
    llm = ChatOllama(
        model="llama3",
        base_url="http://localhost:11434",
        temperature=0.1
    )

    response = await llm.ainvoke("Say 'Hello from llama3!'")
    print(f"✅ LLM response: {response.content}")

if __name__ == "__main__":
    asyncio.run(test_embeddings())
    asyncio.run(test_llm())
```

### Run the Test

```bash
python test_ollama.py

# Expected output:
# ✅ Embedding generated: 768 dimensions
# Sample values: [0.123, -0.456, 0.789, ...]
# ✅ LLM response: Hello from llama3!
```

---

## Step 6: Test pgvector Integration (2 minutes)

### Create test_pgvector.py

```python
import asyncio
import asyncpg
from pgvector.asyncpg import register_vector
import numpy as np

async def test_vector_operations():
    """Test pgvector similarity search."""
    # Connect to database
    conn = await asyncpg.connect(
        "postgresql://marketbel:password@localhost:5432/marketbel"
    )

    # Register pgvector types
    await register_vector(conn)

    # Create test embedding
    test_embedding = np.random.rand(768).astype(np.float32)

    print(f"✅ Connected to PostgreSQL")
    print(f"✅ Generated test embedding: {len(test_embedding)} dimensions")

    # Test vector distance calculation (without inserting)
    result = await conn.fetchval(
        "SELECT $1::vector <=> $2::vector AS distance",
        test_embedding,
        test_embedding
    )

    print(f"✅ Vector distance calculation: {result} (should be ~0.0)")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(test_vector_operations())
```

### Run the Test

```bash
python test_pgvector.py

# Expected output:
# ✅ Connected to PostgreSQL
# ✅ Generated test embedding: 768 dimensions
# ✅ Vector distance calculation: 0.0
```

---

## Step 7: Add to Docker Compose (Optional, 1 minute)

### Update docker-compose.yml

```yaml
services:
  # ... existing services (postgres, redis, bun-api, frontend)

  ml-analyze:
    build: ./services/ml-analyze
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://marketbel:password@postgres:5432/marketbel
      REDIS_URL: redis://redis:6379/0
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      OLLAMA_EMBEDDING_MODEL: nomic-embed-text
      OLLAMA_LLM_MODEL: llama3
    depends_on:
      - postgres
      - redis
    mem_limit: 16g
    cpus: 4
```

### Create Dockerfile

```dockerfile
# services/ml-analyze/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY .env .

# Run FastAPI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Start with Docker Compose

```bash
docker-compose up -d ml-analyze

# Check logs
docker-compose logs -f ml-analyze

# Test health endpoint
curl http://localhost:8001/health
```

---

## Verification Checklist

After completing all steps, verify:

- [ ] Ollama is running: `ollama list` shows nomic-embed-text and llama3
- [ ] pgvector is enabled: `psql -c "SELECT * FROM pg_extension WHERE extname='vector'"`
- [ ] product_embeddings table exists: `psql -c "\d product_embeddings"`
- [ ] ml-analyze service responds: `curl http://localhost:8001/health`
- [ ] Embedding generation works: `python test_ollama.py`
- [ ] Vector operations work: `python test_pgvector.py`
- [ ] API docs are accessible: http://localhost:8001/docs

---

## Next Steps

Once the quickstart is complete, you can:

1. **Implement Parsers:**
   - Create `src/ingest/excel_strategy.py`
   - Create `src/ingest/pdf_strategy.py`

2. **Implement RAG Core:**
   - Create `src/rag/vector_service.py`
   - Create `src/rag/merger_agent.py`

3. **Implement API Endpoints:**
   - Add `POST /analyze/file` endpoint
   - Add `GET /analyze/status/:job_id` endpoint

4. **Run Tests:**
   ```bash
   pytest tests/ -v --cov=src
   ```

5. **Start Development:**
   ```bash
   # Run with auto-reload
   uvicorn src.api.main:app --reload --port 8001
   ```

---

## Troubleshooting

### Ollama Connection Error

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve

# Re-pull models if needed
ollama pull nomic-embed-text
ollama pull llama3
```

### pgvector Extension Not Found

```sql
-- Check PostgreSQL version (must be 11+)
SELECT version();

-- Install pgvector if missing
-- macOS: brew install pgvector
-- Linux: apt-get install postgresql-16-pgvector

-- Then enable in database
CREATE EXTENSION vector;
```

### Database Connection Error

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection string
psql "postgresql://marketbel:password@localhost:5432/marketbel"

# Verify credentials in .env match docker-compose.yml
```

### Import Error: langchain_ollama

```bash
# Reinstall with correct package name
pip uninstall langchain-ollama
pip install langchain-ollama==0.1.0

# Verify
python -c "from langchain_ollama import OllamaEmbeddings; print('OK')"
```

---

## Performance Tips

1. **Ollama Model Loading:** First request is slow (~5s) as model loads. Subsequent requests are fast (<100ms).

2. **pgvector Index:** With <10K products, index overhead is minimal. With >100K, tune `ivfflat.probes`:
   ```sql
   SET ivfflat.probes = 10;  -- Better recall, slightly slower
   ```

3. **Memory Usage:** llama3 uses ~10GB RAM. Ensure Docker has sufficient memory allocation.

4. **Batch Processing:** Embed multiple items in a single batch call for 3-5x speedup:
   ```python
   vectors = embeddings.embed_documents(["item1", "item2", "item3"])
   ```

---

**Ready to build!** You now have a fully functional development environment for the ml-analyze service. 🚀
