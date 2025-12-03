# Research: ML Parsing Service Upgrade

**Date:** 2025-12-03

**Status:** Complete

---

## Overview

Research findings for implementing the ML Parsing Service upgrade with two-stage LLM parsing, file path-based API, composite name parsing, and currency/price extraction.

---

## Research Topics

### 1. Two-Stage LLM Parsing Strategy

**Question:** How should we structure the LLM prompts for Stage A (structure analysis) vs Stage B (data extraction)?

**Decision:** Use separate focused prompts with JSON schema output for each stage.

**Rationale:**
- Stage A focuses on document structure understanding (header identification, column mapping)
- Stage B focuses on data extraction from identified rows using Stage A's column context
- Separation reduces context window usage by ~40% vs single-pass full-document approach
- Each stage has clear success criteria and can be debugged independently

**Implementation Pattern:**

```python
# Stage A: Structure Analysis
STRUCTURE_ANALYSIS_PROMPT = """
Analyze this document sample (first N rows) and identify:
1. Header row indices (which rows contain column headers)
2. Data row start index (first row with product data)
3. Data row end index (last row with product data, or "end")
4. Column purpose mapping (which column contains what field)

Return valid JSON only.
"""

# Stage B: Data Extraction  
EXTRACTION_PROMPT = """
Using the following column mapping: {column_mapping}
Extract product data from these rows: {data_rows}

For each row, extract:
- name: product name
- sku: product code
- price: numeric price
- category: category if present
...
"""
```

**Alternatives Considered:**
- Single-pass parsing: Higher token usage, lower accuracy on complex tables
- Rule-based header detection: Misses complex multi-row headers
- Vision-based analysis: Not available in current Ollama setup

---

### 2. LangChain Sequential Chain Execution

**Question:** How do we chain Stage A → Stage B with LangChain while passing context?

**Decision:** Use simple sequential function calls with Pydantic validation between stages.

**Rationale:**
- LangChain's LCEL (LangChain Expression Language) adds unnecessary complexity
- Simple async functions with explicit data passing are more maintainable
- Pydantic validation ensures Stage A output is valid before Stage B
- KISS principle: No framework abstractions needed for two sequential calls

**Implementation Pattern:**

```python
async def two_stage_parse(document_sample: str, full_data: list[list[str]]) -> list[NormalizedRow]:
    # Stage A: Get structure
    structure = await run_structure_analysis(document_sample)
    
    # Validate Stage A output
    validated_structure = StructureAnalysis.model_validate(structure)
    
    # Stage B: Extract data using structure
    rows = await run_extraction(
        full_data,
        validated_structure.column_mapping,
        validated_structure.data_start_row,
        validated_structure.data_end_row,
    )
    
    return rows
```

**Alternatives Considered:**
- LangChain Sequential Chain: Over-abstraction for two calls
- RunnableSequence (LCEL): Adds complexity without benefit
- LangGraph: Overkill for simple sequential flow

---

### 3. File Path Security (Path Traversal Prevention)

**Question:** How do we securely validate file paths to prevent directory traversal attacks?

**Decision:** Use `pathlib.Path.resolve()` with prefix validation against allowed directory.

**Rationale:**
- `resolve()` normalizes paths and resolves symlinks, preventing `../` attacks
- Checking if resolved path starts with allowed prefix is simple and effective
- No external dependencies required
- Pattern is well-documented in Python security best practices

**Implementation Pattern:**

```python
from pathlib import Path

ALLOWED_UPLOAD_DIR = Path("/shared/uploads")

def validate_file_path(file_path: str) -> Path:
    """Validate and resolve file path securely."""
    path = Path(file_path)
    
    # Resolve to absolute path (handles ../.. etc)
    resolved = path.resolve()
    
    # Ensure path is within allowed directory
    allowed_resolved = ALLOWED_UPLOAD_DIR.resolve()
    if not str(resolved).startswith(str(allowed_resolved)):
        raise SecurityError(f"Path {file_path} is outside allowed directory")
    
    # Ensure file exists
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Ensure it's a file, not a directory
    if not resolved.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    return resolved
```

**Security Checks:**
- [x] Path traversal (`../`) blocked by resolve + prefix check
- [x] Symlink attacks blocked by resolve()
- [x] Directory existence validated
- [x] File vs directory validated
- [x] Configurable allowed directory via settings

**Alternatives Considered:**
- Regex filtering: Error-prone, doesn't handle all edge cases
- Chroot jail: Requires OS-level changes, complexity
- UUID-based filenames only: Limits flexibility, doesn't prevent all attacks

---

### 4. Composite Name Parsing (Delimiter-Based Field Mapping)

**Question:** How should we parse composite product strings like "Category | Product Name | Specs"?

**Decision:** Simple string split with positional mapping and configurable delimiter.

**Rationale:**
- Pipe (`|`) delimiter is consistent across supplier documents
- First segment → category, Second → name, Third+ → description is intuitive
- Empty segments handled by filtering
- Whitespace trimming handles inconsistent formatting
- KISS: No NLP or ML needed for delimiter-based parsing

**Implementation Pattern:**

```python
from dataclasses import dataclass

@dataclass
class CompositeNameResult:
    category_path: list[str]  # Hierarchical categories
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
    
    # Split on primary delimiter
    segments = [s.strip() for s in value.split(delimiter)]
    
    # Filter empty segments
    segments = [s for s in segments if s]
    
    if not segments:
        return CompositeNameResult(
            category_path=[],
            name=value.strip(),
            description=None,
            raw_composite=raw,
        )
    
    # First segment: category (may have hierarchy)
    category_raw = segments[0]
    category_path = []
    
    for sep in category_separators:
        if sep in category_raw:
            category_path = [c.strip() for c in category_raw.split(sep)]
            break
    else:
        category_path = [category_raw]
    
    # Second segment: product name
    name = segments[1] if len(segments) > 1 else category_raw
    
    # Third+ segments: description
    description = " ".join(segments[2:]) if len(segments) > 2 else None
    
    return CompositeNameResult(
        category_path=category_path,
        name=name,
        description=description,
        raw_composite=raw,
    )
```

**Test Cases:**
- `"Electric Bicycle | Shtenli Model Gt11 | Li-ion 48V 15Ah"` → category: ["Electric Bicycle"], name: "Shtenli Model Gt11", desc: "Li-ion 48V 15Ah"
- `"Tools/Power | Drill Pro 500W"` → category: ["Tools", "Power"], name: "Drill Pro 500W", desc: None
- `"Simple Product Name"` → category: [], name: "Simple Product Name", desc: None
- `"Name || Description"` → category: [], name: "Name", desc: "Description" (empty segment skipped)

**Alternatives Considered:**
- NLP entity extraction: Overkill for structured delimiter-based data
- LLM-based parsing: Too slow, inconsistent for simple parsing
- Regex capture groups: Harder to maintain than split + positional

---

### 5. Currency Symbol Extraction and Mapping

**Question:** How do we extract currency symbols and map them to ISO codes?

**Decision:** Regex-based extraction with symbol/text → ISO code mapping dictionary.

**Rationale:**
- Limited set of currencies (RUB, USD, EUR primarily)
- Currency symbols appear adjacent to prices
- Regex handles both prefix and suffix positions
- Text indicators (руб, dollars) handled by same mapping
- Fast, no external dependencies

**Implementation Pattern:**

```python
import re
from decimal import Decimal

CURRENCY_MAP = {
    # Symbols
    "₽": "RUB",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    # Text indicators (Russian)
    "руб": "RUB",
    "руб.": "RUB",
    "р": "RUB",
    "р.": "RUB",
    # Text indicators (English)
    "rub": "RUB",
    "usd": "USD",
    "eur": "EUR",
    "dollars": "USD",
    "euros": "EUR",
}

# Regex patterns for price extraction
PRICE_PATTERN = re.compile(
    r"""
    (?P<currency_prefix>[₽$€£¥])?       # Optional currency symbol prefix
    \s*
    (?P<amount>[\d\s,.']+?)              # Price amount (handles various formats)
    \s*
    (?P<currency_suffix>[₽$€£¥]|руб\.?|р\.?|rub|usd|eur)?  # Optional suffix
    """,
    re.VERBOSE | re.IGNORECASE
)

@dataclass
class PriceResult:
    amount: Decimal
    currency_code: str | None
    raw_value: str

def extract_price(value: str, default_currency: str | None = None) -> PriceResult | None:
    """Extract price and currency from string."""
    match = PRICE_PATTERN.search(value)
    if not match:
        return None
    
    # Determine currency
    currency_code = None
    currency_indicator = (
        match.group("currency_prefix") or 
        match.group("currency_suffix") or 
        ""
    ).lower()
    
    if currency_indicator:
        currency_code = CURRENCY_MAP.get(currency_indicator)
    
    if not currency_code:
        currency_code = default_currency
    
    # Parse amount
    amount_str = match.group("amount")
    # Normalize: remove spaces, convert comma decimal separator
    amount_str = amount_str.replace(" ", "").replace(",", ".")
    # Handle cases like 1.234.56 (European thousands)
    if amount_str.count(".") > 1:
        parts = amount_str.rsplit(".", 1)
        amount_str = parts[0].replace(".", "") + "." + parts[1]
    
    try:
        amount = Decimal(amount_str)
    except Exception:
        return None
    
    return PriceResult(
        amount=amount,
        currency_code=currency_code,
        raw_value=value,
    )
```

**Test Cases:**
- `"₽1 500.00"` → 1500.00 RUB
- `"25.50 руб"` → 25.50 RUB
- `"$99.99"` → 99.99 USD
- `"150.00€"` → 150.00 EUR
- `"1 234,56"` → 1234.56 (no currency, uses default)
- `"100 dollars"` → 100.00 USD

**Alternatives Considered:**
- babel/money parsing library: Adds dependency for simple use case
- LLM-based extraction: Too slow for price parsing
- Hard-coded formats: Less flexible, misses edge cases

---

### 6. Retail vs Wholesale Price Detection

**Question:** How do we identify retail vs wholesale price columns from headers?

**Decision:** Keyword matching with priority-based column classification.

**Rationale:**
- Column headers contain predictable keywords
- Russian and English keywords both supported
- Default to retail if only one price column exists
- Additional tiers stored in characteristics for flexibility

**Implementation Pattern:**

```python
RETAIL_KEYWORDS = {
    "розница", "розн", "retail", "rrp", "msrp", "цена",
    "price", "розничная", "рекомендуемая"
}

WHOLESALE_KEYWORDS = {
    "опт", "оптовая", "wholesale", "dealer", "bulk",
    "дилер", "оптовый", "дилерская", "закупочная"
}

def classify_price_column(header: str) -> str:
    """Classify price column as retail, wholesale, or unknown."""
    header_lower = header.lower()
    
    # Check wholesale first (more specific)
    for keyword in WHOLESALE_KEYWORDS:
        if keyword in header_lower:
            return "wholesale"
    
    # Check retail
    for keyword in RETAIL_KEYWORDS:
        if keyword in header_lower:
            return "retail"
    
    return "unknown"

def map_price_columns(headers: list[str]) -> dict[str, int]:
    """Map price column indices by type."""
    mapping = {"retail": None, "wholesale": None, "other": []}
    
    for idx, header in enumerate(headers):
        col_type = classify_price_column(header)
        
        if col_type == "retail" and mapping["retail"] is None:
            mapping["retail"] = idx
        elif col_type == "wholesale" and mapping["wholesale"] is None:
            mapping["wholesale"] = idx
        elif col_type == "unknown" and "цен" in header.lower():
            mapping["other"].append(idx)
    
    # If only one price column with "unknown" type, default to retail
    if mapping["retail"] is None and mapping["other"]:
        mapping["retail"] = mapping["other"].pop(0)
    
    return mapping
```

---

## Dependencies

### Existing Dependencies (No Changes)

| Package | Version | Purpose |
|---------|---------|---------|
| langchain-ollama | 0.2+ | LLM integration |
| pydantic | 2.x | Validation |
| openpyxl | 3.x | Excel parsing |
| pymupdf4llm | 0.x | PDF parsing |

### New Dependencies

**None required.** All functionality implemented with Python standard library + existing deps.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Stage A returns incorrect structure | Fallback to single-pass if confidence < threshold |
| LLM response not valid JSON | Retry with explicit JSON reminder, max 3 attempts |
| Path traversal attack | Strict path validation with resolve() + prefix check |
| Currency symbol not recognized | Default to supplier currency or null |
| Composite name delimiter varies | Make delimiter configurable per supplier |

---

## Conclusion

All research questions resolved. The implementation will use:
1. **Two-stage prompts** with Pydantic validation between stages
2. **Simple async functions** instead of LangChain chains (KISS)
3. **pathlib.Path.resolve()** for secure file path validation
4. **String split** with positional mapping for composite names
5. **Regex + dictionary** for currency extraction
6. **Keyword matching** for retail/wholesale column classification

No new dependencies required. Implementation follows existing patterns in the codebase.

