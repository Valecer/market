# Python Worker Service Context

## Overview
Data ingestion worker for Marketbel. Parses supplier price lists, matches products, handles scheduled sync.

**Queue:** Redis (arq)  
**Phases:** 1 (Ingestion), 4 (Matching), 6 (Sync Scheduler)

---

## Stack
- **Runtime:** Python 3.12+ (venv)
- **ORM:** SQLAlchemy 2.0 AsyncIO
- **Queue:** arq (Redis-based)
- **Validation:** Pydantic 2.x
- **Matching:** RapidFuzz

---

## Structure

```
src/
├── db/
│   ├── models/         # SQLAlchemy ORM models
│   └── operations.py   # DB operations
├── parsers/            # Data source parsers
│   ├── base_parser.py  # Abstract interface
│   ├── google_sheets_parser.py
│   ├── csv_parser.py
│   ├── excel_parser.py
│   └── parser_registry.py
├── services/
│   ├── matching/       # RapidFuzz matcher
│   ├── extraction/     # Feature extractors
│   └── aggregation/    # Price aggregation
├── tasks/              # arq task handlers
│   ├── matching_tasks.py
│   └── sync_tasks.py
├── models/             # Pydantic models
├── errors/             # Custom exceptions
├── config.py           # Environment config
└── worker.py           # arq worker entry point
```

---

## Commands

```bash
cd services/python-ingestion
source venv/bin/activate

# Run worker
python -m src.worker

# Tests
pytest tests/ -v --cov=src

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

---

## Critical Rules

### 1. Async/Await for All I/O

```python
# ❌ Wrong
def get_product(id: str):
    return session.query(Product).get(id)

# ✅ Correct
async def get_product(id: str) -> Product | None:
    async with get_session() as session:
        return await session.get(Product, id)
```

### 2. Type Hints Required

```python
# ❌ Wrong
def parse_row(row, mapping):
    return ParsedItem(...)

# ✅ Correct
def parse_row(row: dict[str, Any], mapping: ColumnMapping) -> ParsedItem:
    return ParsedItem(...)
```

### 3. Pydantic for Validation

```python
from pydantic import BaseModel, Field

class ParsedItem(BaseModel):
    name: str = Field(..., min_length=1)
    price: Decimal = Field(..., gt=0)
    sku: str | None = None
```

### 4. Error Isolation - Never Crash Worker

```python
# ❌ Wrong - one bad row crashes entire parse
for row in rows:
    item = parse_row(row)  # Exception kills worker

# ✅ Correct - log error, continue with next row
for row in rows:
    try:
        item = parse_row(row)
        items.append(item)
    except ValidationError as e:
        await log_parsing_error(supplier_id, row, str(e))
        continue
```

### 5. Use `patch.object()` for Mocking

```python
# ❌ Wrong - leaks between tests
parser._client.open_by_url = Mock(return_value=mock_sheet)

# ✅ Correct - auto-restores after test
with patch.object(parser._client, 'open_by_url', return_value=mock_sheet):
    result = await parser.parse(config)
```

---

## Key Models

### SQLAlchemy (db/models/)

```python
class Supplier(Base):
    __tablename__ = 'suppliers'
    id: Mapped[UUID]
    name: Mapped[str]
    source_type: Mapped[str]  # google_sheets, csv, excel
    source_url: Mapped[str]
    is_active: Mapped[bool]

class SupplierItem(Base):
    __tablename__ = 'supplier_items'
    id: Mapped[UUID]
    supplier_id: Mapped[UUID]
    product_id: Mapped[UUID | None]
    name: Mapped[str]
    price: Mapped[Decimal]
    characteristics: Mapped[dict]  # JSONB
    match_status: Mapped[str]
```

### Pydantic (models/)

```python
class GoogleSheetsConfig(BaseModel):
    spreadsheet_url: str
    sheet_name: str | None = None
    column_mapping: ColumnMapping

class ParsedItem(BaseModel):
    name: str
    price: Decimal
    sku: str | None
    characteristics: dict[str, Any]
```

---

## Tasks (arq)

| Task | Description | Trigger |
|------|-------------|---------|
| `parse_task` | Parse supplier price list | API, sync |
| `match_items_task` | Fuzzy match items to products | After parse |
| `enrich_item_task` | Extract features from text | After match |
| `recalc_aggregates_task` | Update product min_price | After match/price change |
| `master_sync_task` | Sync from Master Google Sheet | Scheduled (8h) |

### Enqueue Task

```python
from arq import create_pool

async def trigger_parse(supplier_id: str):
    redis = await create_pool(RedisSettings())
    await redis.enqueue_job('parse_task', supplier_id=supplier_id)
```

---

## Matching Pipeline (Phase 4)

```
Unmatched Item → Find Candidates (same category) → RapidFuzz
  │
  ├─ Score ≥95% → Auto-link to product
  ├─ Score 70-94% → Add to review queue
  └─ Score <70% → Create new product (draft)
```

---

## Sync Pipeline (Phase 6)

```
Master Sheet → Parse suppliers → Sync to DB → Enqueue parse tasks
```

- Default interval: 8 hours (`SYNC_INTERVAL_HOURS`)
- Only one sync at a time (skip if running)

---

## Common Issues

1. **"greenlet" error** → Use `async with get_session()`, not sync session
2. **Test pollution** → Use `patch.object()` instead of direct assignment
3. **Missing characteristics** → Check column mapping in parser config
4. **Slow parsing** → Check batch_size, use `executemany` for inserts

