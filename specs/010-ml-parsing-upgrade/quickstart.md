# Quickstart: ML Parsing Service Upgrade

**Time Required:** ~15 minutes

**Prerequisites:**
- Docker and Docker Compose running
- Existing Phase 7 ML-Analyze service deployed
- Ollama with llama3 model available

---

## Step 1: Verify Existing Setup (2 min)

```bash
# Check ml-analyze service is running
docker-compose ps ml-analyze

# Check Ollama is available
curl http://localhost:11434/api/tags

# Check shared volume exists
ls -la /shared/uploads 2>/dev/null || echo "Volume not mounted locally"
```

---

## Step 2: Update Environment Variables (1 min)

Add to `.env` or `docker-compose.yml` environment section:

```bash
# ML-Analyze service configuration
UPLOADS_DIR=/shared/uploads
MAX_FILE_SIZE_MB=50

# Structure analysis settings
STRUCTURE_CONFIDENCE_THRESHOLD=0.7
STRUCTURE_SAMPLE_ROWS=20

# Default parsing options
DEFAULT_CURRENCY=RUB
DEFAULT_COMPOSITE_DELIMITER=|
```

---

## Step 3: Create New Files (5 min)

### A. Create `src/utils/file_reader.py`

```python
"""Secure file reader for shared volume access."""
from pathlib import Path
from src.config.settings import get_settings
from src.utils.errors import SecurityError

def validate_and_read_file(file_path: str) -> tuple[Path, bytes]:
    """
    Validate file path and read contents securely.
    
    Returns:
        Tuple of (resolved Path, file contents as bytes)
    
    Raises:
        SecurityError: If path is outside allowed directory
        FileNotFoundError: If file doesn't exist
    """
    settings = get_settings()
    allowed_dir = Path(settings.uploads_dir).resolve()
    
    path = Path(file_path).resolve()
    
    # Security check: prevent path traversal
    if not str(path).startswith(str(allowed_dir)):
        raise SecurityError(f"Path {file_path} is outside allowed directory")
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise ValueError(f"File too large: {size_mb:.1f}MB > {settings.max_file_size_mb}MB")
    
    return path, path.read_bytes()
```

### B. Create `src/utils/name_parser.py`

```python
"""Composite product name parser."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CompositeNameResult:
    category_path: list[str]
    name: str
    description: str | None
    raw_composite: str

def parse_composite_name(
    value: str,
    delimiter: str = "|",
    category_separators: tuple[str, ...] = ("/", ">"),
) -> CompositeNameResult:
    """Parse composite product string into structured fields."""
    raw = value
    segments = [s.strip() for s in value.split(delimiter) if s.strip()]
    
    if not segments:
        return CompositeNameResult([], value.strip(), None, raw)
    
    # First segment: category
    category_raw = segments[0]
    category_path = []
    for sep in category_separators:
        if sep in category_raw:
            category_path = [c.strip() for c in category_raw.split(sep)]
            break
    else:
        category_path = [category_raw]
    
    name = segments[1] if len(segments) > 1 else category_raw
    description = " ".join(segments[2:]) if len(segments) > 2 else None
    
    return CompositeNameResult(category_path, name, description, raw)
```

### C. Create `src/utils/price_parser.py`

```python
"""Price and currency extraction utilities."""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

@dataclass(frozen=True)
class PriceResult:
    amount: Decimal
    currency_code: str | None
    raw_value: str

CURRENCY_MAP = {
    "₽": "RUB", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY",
    "руб": "RUB", "руб.": "RUB", "р": "RUB", "р.": "RUB",
    "rub": "RUB", "usd": "USD", "eur": "EUR",
}

PRICE_PATTERN = re.compile(
    r"(?P<prefix>[₽$€£¥])?\s*(?P<amount>[\d\s,.']+?)\s*(?P<suffix>[₽$€£¥]|руб\.?|р\.?)?",
    re.IGNORECASE
)

def extract_price(value: str, default_currency: str | None = None) -> PriceResult | None:
    """Extract price and currency from string."""
    match = PRICE_PATTERN.search(value)
    if not match:
        return None
    
    currency = (match.group("prefix") or match.group("suffix") or "").lower()
    currency_code = CURRENCY_MAP.get(currency, default_currency)
    
    amount_str = match.group("amount").replace(" ", "").replace(",", ".")
    if amount_str.count(".") > 1:
        parts = amount_str.rsplit(".", 1)
        amount_str = parts[0].replace(".", "") + "." + parts[1]
    
    try:
        amount = Decimal(amount_str)
    except InvalidOperation:
        return None
    
    return PriceResult(amount, currency_code, value)
```

---

## Step 4: Update Prompt Templates (3 min)

Add to `src/rag/prompt_templates.py`:

```python
# =============================================================================
# Two-Stage Parsing Prompts
# =============================================================================

STRUCTURE_ANALYSIS_SYSTEM = """You are a document structure analyst.
Analyze spreadsheet/table data to identify:
1. Which rows are headers
2. Where product data starts and ends
3. What each column contains

Return ONLY valid JSON, no other text."""

STRUCTURE_ANALYSIS_USER = """Analyze this document sample (first {sample_rows} rows):

{document_sample}

Identify the structure and return JSON:
{{
  "header_rows": [0],  // Row indices with headers (0-indexed)
  "data_start_row": 1,  // First row with actual product data
  "data_end_row": -1,   // Last row with data (-1 = until end)
  "column_mapping": {{
    "name_column": null,        // Column index for product name
    "sku_column": null,         // Column index for SKU/article
    "retail_price_column": null,
    "wholesale_price_column": null,
    "category_column": null,
    "unit_column": null
  }},
  "confidence": 0.9,
  "detected_currency": "RUB",
  "notes": "Optional notes about structure"
}}"""

STRUCTURE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", STRUCTURE_ANALYSIS_SYSTEM),
    ("human", STRUCTURE_ANALYSIS_USER),
])

EXTRACTION_SYSTEM = """You are a product data extractor.
Extract product information from table rows using the column mapping provided.
Return ONLY valid JSON array, no other text."""

EXTRACTION_USER = """Using this column mapping:
{column_mapping}

Extract products from these rows:
{data_rows}

Return JSON array:
[
  {{
    "name": "Product Name",
    "sku": "SKU123",
    "retail_price": 100.00,
    "wholesale_price": 85.00,
    "currency_code": "RUB",
    "category": "Category Name",
    "unit": "шт"
  }}
]"""

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", EXTRACTION_SYSTEM),
    ("human", EXTRACTION_USER),
])
```

---

## Step 5: Update API Route (2 min)

Modify `src/api/routes/analyze.py` to handle `file_path`:

```python
@router.post("/file", ...)
async def analyze_file(
    request: FileAnalysisRequest,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> FileAnalysisResponse:
    # Determine file source
    if request.file_path:
        # Validate path security
        from src.utils.file_reader import validate_and_read_file
        try:
            resolved_path, _ = validate_and_read_file(request.file_path)
            file_source = str(resolved_path)
        except (SecurityError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        file_source = str(request.file_url)
    
    # Create job with file source
    job_id = await job_service.create_job(
        job_type=JobType.FILE_ANALYSIS,
        supplier_id=request.supplier_id,
        file_url=file_source,
        file_type=request.file_type,
        metadata={
            "source": "file_path" if request.file_path else "file_url",
            "default_currency": request.default_currency,
            "composite_delimiter": request.composite_delimiter,
        },
    )
    # ... rest unchanged
```

---

## Step 6: Test the Changes (2 min)

```bash
# Start services
cd services/ml-analyze
source venv/bin/activate

# Run unit tests for new utilities
pytest tests/test_file_reader.py tests/test_name_parser.py tests/test_price_parser.py -v

# Test API endpoint
curl -X POST http://localhost:8001/analyze/file \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/shared/uploads/test-price-list.xlsx",
    "supplier_id": "123e4567-e89b-12d3-a456-426614174000",
    "file_type": "excel",
    "default_currency": "RUB"
  }'
```

---

## Verification Checklist

- [ ] `validate_and_read_file()` blocks path traversal (`../`)
- [ ] `parse_composite_name()` splits on `|` correctly
- [ ] `extract_price()` detects ₽, $, € symbols
- [ ] API accepts both `file_path` and `file_url`
- [ ] Two-stage prompts return valid JSON
- [ ] Metrics include token counts and timing

---

## Troubleshooting

### "Path is outside allowed directory"
- Check `UPLOADS_DIR` env var matches Docker volume mount
- Ensure file path doesn't contain `../`

### "File not found"
- Verify file was uploaded to shared volume
- Check Docker volume is mounted correctly

### "Invalid JSON from LLM"
- Increase `STRUCTURE_SAMPLE_ROWS` for more context
- Check Ollama llama3 model is loaded

### "Parsing returns empty results"
- Check `confidence` from Stage A - if < threshold, structure detection failed
- Inspect `notes` field for LLM's explanation

---

## Next Steps

1. Implement `TwoStageParsingService` using the prompts
2. Add metrics collection to `IngestionService`
3. Update frontend to display parsing metrics
4. Add retry logic for failed Stage A

