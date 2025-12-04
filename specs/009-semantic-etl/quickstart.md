# Quickstart: Semantic ETL Pipeline

**Goal:** Get the Semantic ETL pipeline running in 15 minutes.

**Prerequisites:**
- Docker & Docker Compose v2 installed
- Git repository cloned
- Existing Marketbel stack running (Phase 8 complete)
- Ollama service with llama3 model (Phase 7)

---

## Step 1: Database Migrations (2 minutes)

Run Alembic migrations to add category hierarchy and semantic ETL fields:

```bash
# Navigate to ml-analyze service
cd services/ml-analyze

# Activate virtual environment
source venv/bin/activate

# Run migrations
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade ... -> 009_add_category_hierarchy
# INFO  [alembic.runtime.migration] Running upgrade ... -> 009_validate_supplier_items
# INFO  [alembic.runtime.migration] Running upgrade ... -> 009_enhance_parsing_logs

# Verify categories table has new columns
psql -U marketbel -d marketbel -c "\d categories"
# Should show: parent_id, needs_review, is_active, supplier_id
```

**Troubleshooting:**
- If migration fails with "relation already exists", check if columns were manually added
- If Alembic history is out of sync, run `alembic stamp head` first

---

## Step 2: Install Python Dependencies (2 minutes)

Install LangChain and related packages:

```bash
# Still in services/ml-analyze directory
pip install langchain-core==0.3.21 \
            langchain-ollama==0.2.0 \
            openpyxl==3.1.5

# Verify installations
python -c "from langchain_ollama import ChatOllama; print('✅ LangChain installed')"
python -c "import openpyxl; print('✅ openpyxl installed')"

# Update requirements.txt
pip freeze | grep -E 'langchain|openpyxl' >> requirements.txt
```

---

## Step 3: Environment Variables (1 minute)

Add semantic ETL configuration to `.env` file:

```bash
# Edit docker-compose.yml or .env file
cat >> .env <<EOF

# Semantic ETL Configuration (Phase 9)
USE_SEMANTIC_ETL=true
FUZZY_MATCH_THRESHOLD=85
CHUNK_SIZE_ROWS=250
CHUNK_OVERLAP_ROWS=40
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL_LLM=llama3
EOF
```

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SEMANTIC_ETL` | `false` | Enable semantic ETL (feature flag) |
| `FUZZY_MATCH_THRESHOLD` | `85` | Category matching threshold (0-100) |
| `CHUNK_SIZE_ROWS` | `250` | Rows per LLM extraction chunk |
| `CHUNK_OVERLAP_ROWS` | `40` | Overlap between chunks |
| `OLLAMA_MODEL_LLM` | `llama3` | LLM model for extraction |

---

## Step 4: Implement Core Services (5 minutes)

Create placeholder files for the semantic ETL components:

```bash
cd services/ml-analyze/src

# Create schemas directory
mkdir -p schemas

# Create extraction schema
cat > schemas/extraction.py <<'PYTHON'
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal

class ExtractedProduct(BaseModel):
    """Product extracted from supplier file via LLM."""
    name: str = Field(..., min_length=1, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price_opt: Optional[Decimal] = Field(None, ge=0, description="Wholesale price")
    price_rrc: Decimal = Field(..., ge=0, description="Retail price (required)")
    category_path: list[str] = Field(default_factory=list, description="Category hierarchy")
    raw_data: dict = Field(default_factory=dict, description="Original row data")

    @field_validator('name')
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return ' '.join(v.strip().split())

    @field_validator('category_path')
    @classmethod
    def normalize_categories(cls, v: list[str]) -> list[str]:
        return [c.strip() for c in v if c.strip()]

class ExtractionResult(BaseModel):
    """Result of file extraction process."""
    products: list[ExtractedProduct] = Field(default_factory=list)
    sheet_name: str
    total_rows: int
    successful_extractions: int
    failed_extractions: int
    duplicates_removed: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return (self.successful_extractions / self.total_rows) * 100

    @property
    def status(self) -> str:
        if self.success_rate == 100:
            return "success"
        elif self.success_rate >= 80:
            return "completed_with_errors"
        else:
            return "failed"
PYTHON

# Create services directory structure
mkdir -p services/smart_parser

# Create SmartParserService stub
cat > services/smart_parser/service.py <<'PYTHON'
from langchain_ollama import ChatOllama
import os

class SmartParserService:
    """Orchestrates semantic extraction workflow."""

    def __init__(self):
        self.llm = ChatOllama(
            model=os.getenv("OLLAMA_MODEL_LLM", "llama3"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            temperature=0.2,
            num_predict=2048,
            format="json",
        )

    async def parse_file(self, file_path: str, supplier_id: int):
        """Main entry point for semantic ETL."""
        # TODO: Implement full workflow
        # 1. Smart sheet selection
        # 2. Markdown conversion
        # 3. LLM extraction (sliding window)
        # 4. Category normalization
        # 5. Deduplication
        raise NotImplementedError("Semantic ETL implementation in progress")
PYTHON

echo "✅ Core service files created"
```

---

## Step 5: Test Ollama Connection (2 minutes)

Verify that Ollama is accessible and llama3 model is available:

```bash
# Test from ml-analyze container
docker exec ml-analyze python <<PYTHON
from langchain_ollama import ChatOllama
import asyncio

async def test_ollama():
    llm = ChatOllama(
        model="llama3",
        base_url="http://ollama:11434",
        temperature=0.2,
        format="json"
    )
    response = await llm.ainvoke("Say 'OK' in JSON format: {\"status\": \"OK\"}")
    print(f"✅ Ollama response: {response}")

asyncio.run(test_ollama())
PYTHON
```

**Expected Output:**
```
✅ Ollama response: {"status": "OK"}
```

**Troubleshooting:**
- If connection fails, check Ollama logs: `docker logs ollama`
- Verify llama3 model is pulled: `docker exec ollama ollama list`
- If model missing: `docker exec ollama ollama pull llama3`

---

## Step 6: Enable Feature Flag (1 minute)

Enable semantic ETL for a test supplier:

```bash
# Connect to PostgreSQL
psql -U marketbel -d marketbel

# Add use_semantic_etl column to suppliers table (if not exists)
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS use_semantic_etl BOOLEAN DEFAULT false;

# Enable for test supplier (ID=1)
UPDATE suppliers SET use_semantic_etl = true WHERE id = 1;

# Verify
SELECT id, name, use_semantic_etl FROM suppliers WHERE id = 1;

# Expected output:
#  id |       name       | use_semantic_etl
# ----+------------------+------------------
#   1 | Test Supplier    | t
```

---

## Step 7: Restart Services (1 minute)

Restart ml-analyze and python-ingestion services to load new code:

```bash
# From project root
docker-compose restart ml-analyze python-ingestion

# Check logs for errors
docker-compose logs -f ml-analyze | grep -i "error\|exception"

# Expected: No critical errors, service should start cleanly
```

---

## Step 8: Verify Health (1 minute)

Check ml-analyze health endpoint:

```bash
curl http://localhost:8001/health | jq

# Expected output:
# {
#   "status": "healthy",
#   "version": "2.0.0",
#   "dependencies": {
#     "postgresql": "connected",
#     "ollama": "available",
#     "redis": "connected"
#   }
# }
```

---

## Step 9: Test Extraction (End-to-End) (Optional, 5 minutes)

Upload a test Excel file and verify semantic extraction:

```bash
# Create test Excel file
cat > /tmp/test_products.xlsx <<'CSV'
Product Name,Price,Category
Laptop Dell XPS 15,1500,Electronics | Laptops
Mouse Logitech MX,75,Electronics | Accessories
Desk Chair Ergonomic,350,Furniture | Office
CSV

# Convert to Excel using Python
python <<PYTHON
import pandas as pd
df = pd.read_csv('/tmp/test_products.csv')
df.to_excel('/tmp/test_products.xlsx', index=False)
PYTHON

# Upload via API
curl -X POST http://localhost:3000/admin/suppliers/1/upload \
  -F "file=@/tmp/test_products.xlsx" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# Poll job status
JOB_ID="<returned_job_id>"
curl http://localhost:3000/admin/sync/status | jq ".jobs[] | select(.job_id == \"$JOB_ID\")"

# Expected phases: downloading → analyzing → extracting → normalizing → complete
```

**Verify Results:**

```sql
-- Check extracted products
SELECT name, price_rrc, category_path
FROM supplier_items
WHERE supplier_id = 1
ORDER BY created_at DESC
LIMIT 3;

-- Check new categories
SELECT id, name, parent_id, needs_review
FROM categories
WHERE needs_review = true;
```

---

## Troubleshooting

### Issue: LLM Timeout

**Symptom:** Jobs fail with "LLM timeout after 3 retries"

**Solution:**
1. Check Ollama service is running: `docker ps | grep ollama`
2. Verify llama3 model loaded: `docker exec ollama ollama list`
3. Increase timeout in `.env`: `LLM_TIMEOUT_SECONDS=120`

### Issue: Category Duplication

**Symptom:** Too many categories with `needs_review=true`

**Solution:**
1. Lower fuzzy threshold: `FUZZY_MATCH_THRESHOLD=80`
2. Run category merge script: `python scripts/merge_similar_categories.py`
3. Review and approve categories in Admin UI: `/admin/categories/review`

### Issue: Low Extraction Accuracy (<95%)

**Symptom:** Many products fail validation or have missing fields

**Solution:**
1. Check prompt template in `services/ml-analyze/src/services/smart_parser/prompts.py`
2. Add more examples to LLM prompt (few-shot learning)
3. Adjust temperature: `OLLAMA_TEMPERATURE=0.1` (more deterministic)
4. Check raw data in `parsing_logs` table for common patterns

### Issue: Slow Processing (>5 min for 500 rows)

**Symptom:** Jobs take too long to complete

**Solution:**
1. Reduce chunk size: `CHUNK_SIZE_ROWS=200` (fewer rows per LLM call)
2. Optimize prompt length: Remove verbose instructions
3. Check Ollama resource allocation: `docker stats ollama`
4. Consider parallel chunk processing (advanced)

---

## Next Steps

1. **Implement Full Pipeline:** Complete SmartParserService methods (see `plan.md` Phase 3-7)
2. **Add Tests:** Create unit tests for extraction logic (target: ≥90% coverage)
3. **Admin UI:** Implement CategoryReviewPage component in React frontend
4. **Monitor Metrics:** Track extraction accuracy, processing time, category match rate
5. **Gradual Rollout:** Enable semantic ETL for more suppliers (canary release)

---

## Rollback

If you need to disable semantic ETL:

```bash
# Disable feature flag globally
export USE_SEMANTIC_ETL=false

# Disable for specific suppliers
psql -U marketbel -d marketbel -c "UPDATE suppliers SET use_semantic_etl = false;"

# Restart services
docker-compose restart ml-analyze python-ingestion

# Revert migrations (if needed, DANGEROUS)
cd services/ml-analyze
alembic downgrade -1  # Undo last migration
```

---

## Resources

- **Feature Spec:** `/specs/009-semantic-etl/spec.md`
- **Implementation Plan:** `/specs/009-semantic-etl/plan.md`
- **Research Findings:** `/specs/009-semantic-etl/research.md`
- **Data Model:** `/specs/009-semantic-etl/data-model.md`
- **API Contracts:** `/specs/009-semantic-etl/contracts/ml-analyze-api.json`
- **LangChain Docs:** https://python.langchain.com/docs/get_started/introduction
- **Ollama API:** https://ollama.com/docs

---

**Estimated Total Time:** 15 minutes (+ 5 minutes optional testing)

**Status:** Ready for implementation (placeholder services created, dependencies installed)
