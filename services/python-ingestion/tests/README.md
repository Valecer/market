# Test Suite Documentation

**Service:** Python Ingestion Worker  
**Test Framework:** pytest  
**Coverage Target:** ≥85%

---

## Quick Start

### Prerequisites

1. **Docker Services** (for integration tests):
   ```bash
   docker-compose up -d
   ```

2. **Python Dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Database Migrations** (for integration tests):
   ```bash
   alembic upgrade head
   ```

### Run All Tests

```bash
# From services/python-ingestion directory
pytest tests/ -v
```

### Run Specific Test Types

```bash
# Unit tests only (fast, no Docker required)
pytest tests/unit/ -v

# Integration tests (requires Docker services)
pytest tests/integration/ -v -m integration

# Performance tests (slow, requires Docker)
pytest tests/integration/test_performance.py -v -m integration -s

# All tests except slow ones
pytest tests/ -v -m "not slow"
```

---

## Test Structure

```
tests/
├── README.md                    # This file
├── conftest.py                  # Root-level fixtures and configuration
├── unit/                        # Unit tests (isolated, fast)
│   ├── test_parsers.py         # Parser unit tests with mocked dependencies
│   ├── test_models.py          # Pydantic model validation tests
│   ├── test_db_models.py      # SQLAlchemy model constraint tests
│   └── test_phase4_independent_criteria.py  # Phase 4 acceptance criteria
└── integration/                 # Integration tests (require Docker services)
    ├── conftest.py             # Integration-specific fixtures
    ├── helpers.py              # Test helper functions
    ├── google_sheets_helper.py # Google Sheets test utilities
    ├── test_end_to_end.py      # End-to-end pipeline tests
    └── test_performance.py     # Performance benchmarks
```

---

## Test Types

### Unit Tests (`tests/unit/`)

**Purpose:** Test individual components in isolation with mocked dependencies.

**Characteristics:**
- Fast execution (< 1 second per test)
- No external dependencies (database, Redis, APIs)
- Use mocks for external services (gspread, database)
- Can run without Docker services

**Examples:**
- Parser logic with mocked Google Sheets API
- Pydantic model validation
- SQLAlchemy model constraints (in-memory SQLite)

**Note on SQLite vs PostgreSQL:**
Unit tests use SQLite for speed and simplicity, but SQLite has limitations:
- ENUMs are converted to strings (tested as strings)
- Self-referential CASCADE deletes may not work reliably
- JSONB is converted to JSON

These limitations are acceptable for unit tests because:
1. **Speed**: SQLite tests run 10-100x faster than PostgreSQL
2. **Isolation**: Each test gets a fresh in-memory database
3. **No dependencies**: Tests run without Docker/PostgreSQL server
4. **Coverage**: Integration tests verify real PostgreSQL behavior

**When to use each:**
- **Unit tests (SQLite)**: Model constraints, relationships, basic ORM behavior
- **Integration tests (PostgreSQL)**: Full feature support, CASCADE behavior, production-like scenarios

**Run:**
```bash
pytest tests/unit/ -v
```

**Coverage:**
- `test_parsers.py`: Google Sheets parser with mocked gspread
- `test_models.py`: All Pydantic models (ParsedSupplierItem, ParseTaskMessage, GoogleSheetsConfig)
- `test_db_models.py`: SQLAlchemy models and constraints

---

### Integration Tests (`tests/integration/`)

**Purpose:** Test complete workflows with real Docker services (PostgreSQL, Redis).

**Characteristics:**
- Require Docker services running
- Use real database and Redis connections
- Test end-to-end data flow
- Slower execution (seconds to minutes per test)

**Prerequisites:**
```bash
# Start Docker services
docker-compose up -d

# Verify services are healthy
docker-compose ps

# Run migrations
alembic upgrade head
```

**Examples:**
- End-to-end: Queue → Parser → Database
- Database transaction rollback
- Price history tracking
- Error logging to parsing_logs

**Run:**
```bash
pytest tests/integration/ -v -m integration
```

**Coverage:**
- `test_end_to_end.py`: Complete pipeline scenarios
- `test_performance.py`: Throughput benchmarks (10,000 items)

---

### Performance Tests

**Purpose:** Validate system meets performance targets (>1,000 items/min).

**Characteristics:**
- Marked with `@pytest.mark.slow`
- Process large datasets (10,000+ items)
- Measure throughput and latency
- Require Docker services

**Targets:**
- Throughput: >1,000 items/minute
- Max time: <10 minutes for 10,000 items

**Run:**
```bash
pytest tests/integration/test_performance.py -v -m integration -s
```

**Output:**
```
PERFORMANCE TEST RESULTS
========================================
Items processed:     10,000 / 10,000
Ingest time:         450.23 seconds (7.50 minutes)
Ingest throughput:   1,333 items/minute
✅ PERFORMANCE TEST PASSED
```

---

## Test Markers

Tests are organized using pytest markers:

| Marker | Description | Example |
|--------|-------------|---------|
| `@pytest.mark.unit` | Unit tests (fast, isolated) | `test_parsers.py` |
| `@pytest.mark.integration` | Integration tests (require Docker) | `test_end_to_end.py` |
| `@pytest.mark.slow` | Slow tests (performance, large datasets) | `test_performance.py` |
| `@pytest.mark.asyncio` | Async test functions | All database tests |

**Run by marker:**
```bash
# Only unit tests
pytest -m unit -v

# Only integration tests
pytest -m integration -v

# Skip slow tests
pytest -m "not slow" -v

# Only async tests
pytest -m asyncio -v
```

---

## Test Configuration

### pytest.ini

Located at `services/python-ingestion/pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: Integration tests that require Docker services
    unit: Unit tests that can run in isolation
    slow: Tests that take a long time to run
asyncio_mode = auto
```

### Environment Variables

Tests use environment variables for configuration:

**Unit Tests** (from `tests/conftest.py`):
```python
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test
REDIS_PASSWORD=test_password
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=INFO
```

**Integration Tests** (from `tests/integration/conftest.py`):
```python
DATABASE_URL=postgresql+asyncpg://marketbel_user:dev_password@localhost:5432/marketbel_test
REDIS_PASSWORD=dev_redis_password
REDIS_HOST=localhost
REDIS_PORT=6379
LOG_LEVEL=DEBUG
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run specific test file
pytest tests/unit/test_parsers.py

# Run specific test function
pytest tests/unit/test_parsers.py::TestGoogleSheetsParserInitialization::test_parser_initializes_with_credentials_path

# Run tests matching pattern
pytest -k "test_parser"

# Run with coverage report
pytest --cov=src --cov-report=html --cov-report=term
```

### Coverage Reports

```bash
# Terminal report
pytest --cov=src --cov-report=term

# HTML report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Check coverage threshold
pytest --cov=src --cov-report=term --cov-fail-under=85
```

**Coverage Target:** ≥85% for business logic

---

## Test Fixtures

### Unit Test Fixtures

**Location:** `tests/conftest.py`

- `setup_test_environment`: Sets default environment variables

### Integration Test Fixtures

**Location:** `tests/integration/conftest.py`

- `event_loop`: Async event loop for async tests
- `setup_database`: Runs migrations before all tests
- `db_session`: Database session with automatic cleanup

**Usage:**
```python
@pytest.mark.asyncio
async def test_example(db_session: AsyncSession):
    # db_session is automatically cleaned before/after test
    supplier = Supplier(name="Test", source_type="csv")
    db_session.add(supplier)
    await db_session.commit()
    # Database is cleaned automatically after test
```

---

## Helper Functions

**Location:** `tests/integration/helpers.py`

### `create_test_parsed_items(count, start_price)`

Generate test `ParsedSupplierItem` objects:

```python
from tests.integration.helpers import create_test_parsed_items

items = create_test_parsed_items(100, start_price=Decimal("10.00"))
# Returns 100 items with prices 10.00, 10.50, 11.00, ...
```

### `create_test_parsed_items_with_same_price(count, price)`

Generate items with identical prices:

```python
items = create_test_parsed_items_with_same_price(50, price=Decimal("19.99"))
# Returns 50 items all with price 19.99
```

---

## Common Test Scenarios

### Testing Parsers

```python
from unittest.mock import Mock, patch
from src.parsers.google_sheets_parser import GoogleSheetsParser

@patch('src.parsers.google_sheets_parser.gspread.service_account')
def test_parser(mock_service_account):
    mock_client = Mock()
    mock_service_account.return_value = mock_client
    
    parser = GoogleSheetsParser(credentials_path="/test/path.json")
    # Test parser logic...
```

### Testing Pydantic Models

```python
from src.models.parsed_item import ParsedSupplierItem
from pydantic import ValidationError

def test_valid_item():
    item = ParsedSupplierItem(
        supplier_sku="SKU-001",
        name="Product",
        price=Decimal("19.99")
    )
    assert item.price == Decimal("19.99")

def test_invalid_price():
    with pytest.raises(ValidationError):
        ParsedSupplierItem(
            supplier_sku="SKU-001",
            name="Product",
            price=Decimal("-10.00")  # Negative price should fail
        )
```

### Testing Database Operations

```python
@pytest.mark.asyncio
async def test_database_operation(db_session: AsyncSession):
    supplier = await get_or_create_supplier(
        db_session,
        name="Test Supplier",
        source_type="csv"
    )
    assert supplier.id is not None
    
    # Database is automatically cleaned after test
```

### Testing End-to-End Pipeline

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end(db_session: AsyncSession):
    message = {
        "task_id": "test-001",
        "parser_type": "stub",
        "supplier_name": "Test Supplier",
        "source_config": {"test": "config"}
    }
    
    result = await parse_task({}, message)
    assert result["status"] == "success"
    assert result["items_parsed"] > 0
```

---

## Troubleshooting

### Tests Fail with "Database connection refused"

**Problem:** Integration tests can't connect to PostgreSQL.

**Solution:**
```bash
# Start Docker services
docker-compose up -d

# Verify database is running
docker-compose ps postgres

# Check database is accessible
docker-compose exec postgres pg_isready -U marketbel_user
```

### Tests Fail with "Redis connection refused"

**Problem:** Integration tests can't connect to Redis.

**Solution:**
```bash
# Start Redis
docker-compose up -d redis

# Verify Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Tests Fail with "Table does not exist"

**Problem:** Database migrations not applied.

**Solution:**
```bash
# Run migrations
alembic upgrade head

# Verify tables exist
docker-compose exec postgres psql -U marketbel_user -d marketbel_test -c "\dt"
```

### Unit Tests Fail with Import Errors

**Problem:** Python path not set correctly.

**Solution:**
```bash
# Run from project root
cd services/python-ingestion
pytest tests/unit/ -v

# Or set PYTHONPATH
PYTHONPATH=. pytest tests/unit/ -v
```

### Performance Test Fails with Timeout

**Problem:** Performance test takes too long (>10 minutes).

**Solution:**
- Check database performance (indexes, connection pool)
- Verify Docker has enough resources (CPU, memory)
- Check for database locks or slow queries
- Review batch size in test (default: 100 items)

### Async Tests Show Warnings

**Problem:** `RuntimeWarning: coroutine '...' was never awaited`

**Solution:**
- Warnings are suppressed in `tests/integration/conftest.py`
- These occur during cleanup and are harmless
- If persistent, check event loop cleanup in fixtures

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: marketbel_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test_password@localhost:5432/marketbel_test
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration/ -v -m integration
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test_password@localhost:5432/marketbel_test
          REDIS_HOST: localhost
          REDIS_PORT: 6379
```

---

## Test Coverage

### Current Coverage

Run coverage report:
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

**Target:** ≥85% coverage for business logic

**Coverage by Module:**
- `src/parsers/`: Parser implementations
- `src/models/`: Pydantic validation models
- `src/db/models/`: SQLAlchemy ORM models
- `src/db/operations.py`: Database operations
- `src/worker.py`: Worker task processing

### Excluded from Coverage

- `src/config.py`: Configuration loading (simple)
- `src/health_check.py`: Health check utilities
- Migration files: Database schema migrations

---

## Best Practices

### Writing Unit Tests

1. **Use mocks for external dependencies:**
   ```python
   @patch('module.external_api')
   def test_function(mock_api):
       mock_api.return_value = expected_result
       # Test logic...
   ```

2. **Test edge cases:**
   - Empty inputs
   - Invalid inputs
   - Boundary values
   - Error conditions

3. **Keep tests isolated:**
   - Each test should be independent
   - No shared state between tests
   - Clean up after each test

### Writing Integration Tests

1. **Use fixtures for setup:**
   ```python
   @pytest.mark.asyncio
   async def test_example(db_session: AsyncSession):
       # db_session is automatically cleaned
   ```

2. **Test real workflows:**
   - End-to-end scenarios
   - Error handling
   - Transaction rollback

3. **Clean up test data:**
   - Use fixtures for automatic cleanup
   - Don't leave test data in database

### Performance Testing

1. **Measure actual performance:**
   - Use real datasets (10,000+ items)
   - Measure throughput (items/minute)
   - Verify targets are met

2. **Test different scenarios:**
   - Small batches
   - Large batches
   - Different data sizes

---

## Additional Resources

- **pytest Documentation:** https://docs.pytest.org/
- **pytest-asyncio:** https://pytest-asyncio.readthedocs.io/
- **pytest-cov:** https://pytest-cov.readthedocs.io/
- **Project Documentation:** `docs/` directory
- **Implementation Plan:** `specs/001-data-ingestion-infra/plan/implementation-plan.md`

---

## Questions?

- Check test code comments for detailed explanations
- Review integration test examples in `test_end_to_end.py`
- Check helper functions in `helpers.py`
- Review pytest configuration in `pytest.ini`

---

**Last Updated:** 2025-11-24  
**Test Framework Version:** pytest 8.x  
**Python Version:** 3.12+

