# Feature Specification: Data Ingestion Infrastructure

**Version:** 1.0.0

**Last Updated:** 2025-11-23

**Status:** Draft

---

## Overview

### Purpose

Build the foundational backend infrastructure for a "Unified Catalog" that ingests raw supplier price list data from multiple sources, normalizes it, and stores it in a structured PostgreSQL database for future processing.

### Scope

**In Scope:**

- PostgreSQL database schema for products, suppliers, and price history
- Python service architecture with pluggable parser interface
- Redis-based queue system for asynchronous data processing
- Google Sheets parser implementation as the first data source
- Data normalization and storage to SupplierItems table
- Docker containerization for Python service

**Out of Scope:**

- User interface or frontend components
- Machine learning-based product matching
- Internal SKU assignment logic
- Multi-supplier product deduplication
- Price comparison and analytics features
- Authentication and authorization
- API endpoints for data retrieval
- Real-time data synchronization

---

## Functional Requirements

### FR-1: Database Schema Design

**Priority:** Critical

**Description:** Design and implement a PostgreSQL schema that supports storing supplier catalog data with flexible characteristics, tracking price history, and establishing relationships between internal products and supplier items.

**Acceptance Criteria:**

- [ ] AC-1: `Products` table exists with fields for Internal SKU, name, and category reference
- [ ] AC-2: `Suppliers` table exists with fields for supplier identification and metadata
- [ ] AC-3: `SupplierItems` table exists linking to Suppliers with raw price list data
- [ ] AC-4: `Categories` table exists for product categorization
- [ ] AC-5: `PriceHistory` table exists tracking price changes over time with timestamps
- [ ] AC-6: One Internal SKU can link to multiple Supplier Items through proper foreign key relationships
- [ ] AC-7: JSONB column exists in SupplierItems for storing flexible "Characteristics" data
- [ ] AC-8: All tables have appropriate indexes for common query patterns
- [ ] AC-9: Database migration scripts are versioned and reversible

**Dependencies:** PostgreSQL database instance

### FR-2: Python Processing Service Architecture

**Priority:** Critical

**Description:** Create a modular Python service running in Docker that provides a pluggable architecture for different data source parsers, enabling easy addition of new supplier formats in the future.

**Acceptance Criteria:**

- [ ] AC-1: Python service runs successfully in Docker container
- [ ] AC-2: Abstract "Parser Interface" is defined with standard methods (parse, validate, normalize)
- [ ] AC-3: New parsers can be registered without modifying core service code
- [ ] AC-4: Service includes configuration management for parser selection
- [ ] AC-5: Service has proper logging for debugging and monitoring
- [ ] AC-6: Service handles parser errors gracefully without crashing
- [ ] AC-7: Service includes health check endpoint for container orchestration
- [ ] AC-8: Service uses type hints throughout for code clarity

**Dependencies:** Docker, Python 3.11+

### FR-3: Google Sheets Parser Implementation

**Priority:** High

**Description:** Implement the first concrete parser that can read data from a Google Sheets source, extract product information including characteristics, and normalize it into the internal data model.

**Acceptance Criteria:**

- [ ] AC-1: Parser can authenticate with Google Sheets API
- [ ] AC-2: Parser reads all rows from specified sheet
- [ ] AC-3: Parser extracts supplier name, product name, price, SKU, and characteristics
- [ ] AC-4: Parser handles missing or malformed data gracefully with appropriate error messages
- [ ] AC-5: Parser normalizes price data to consistent decimal format
- [ ] AC-6: Parser converts characteristics into JSONB-compatible format
- [ ] AC-7: Parser validates required fields before processing
- [ ] AC-8: Parser logs processing statistics (rows processed, errors encountered)

**Dependencies:** Google Sheets API credentials, FR-2

### FR-4: Redis Queue System

**Priority:** Critical

**Description:** Set up Redis-based queue infrastructure that allows the Python service to receive "Parse Task" messages asynchronously, enabling decoupled data ingestion workflows.

**Acceptance Criteria:**

- [ ] AC-1: Redis instance is running and accessible to Python service
- [ ] AC-2: Queue message structure is defined with task type, source configuration, and metadata
- [ ] AC-3: Python service successfully consumes messages from the queue
- [ ] AC-4: Messages include retry count and expiration time
- [ ] AC-5: Failed messages are moved to dead letter queue after max retries
- [ ] AC-6: Queue depth is monitored and logged
- [ ] AC-7: Service can process multiple messages concurrently with configurable worker count
- [ ] AC-8: Queue connection handles reconnection on network failures

**Dependencies:** Redis instance, FR-2

### FR-5: Data Ingestion Pipeline

**Priority:** Critical

**Description:** Implement end-to-end data flow from receiving a parse task, reading source data, normalizing it, and persisting to the SupplierItems table with proper error handling and transaction management.

**Acceptance Criteria:**

- [ ] AC-1: Service receives parse task from queue successfully
- [ ] AC-2: Service invokes appropriate parser based on source type
- [ ] AC-3: Parsed data is validated against data model constraints
- [ ] AC-4: Data is inserted into SupplierItems table within database transaction
- [ ] AC-5: Supplier record is created or updated if not exists
- [ ] AC-6: Price history entry is created for each item
- [ ] AC-7: Processing failures roll back database changes
- [ ] AC-8: Task completion status is logged with processing time and row counts
- [ ] AC-9: Duplicate detection prevents reprocessing same source data

**Dependencies:** FR-1, FR-2, FR-3, FR-4

---

## Success Criteria

The infrastructure is considered successful when:

1. **Data Ingestion Completeness:** 100% of rows from a valid Google Sheet are successfully parsed and stored in the database
2. **Processing Speed:** System processes at least 1,000 supplier items per minute
3. **Error Recovery:** Failed parse tasks are automatically retried up to 3 times with exponential backoff
4. **Data Integrity:** All stored records pass validation constraints with zero data corruption
5. **System Reliability:** Service runs continuously for 24 hours without manual intervention
6. **Parser Extensibility:** A new parser can be added and tested within 2 hours of development time
7. **Operational Visibility:** All processing errors are logged with sufficient context for debugging

---

## User Scenarios & Testing

### Scenario 1: First-Time Data Ingestion

**Context:** A supplier provides their first price list via Google Sheets

**Steps:**
1. Administrator adds parse task to Redis queue with Google Sheets URL
2. Python service picks up task from queue
3. Google Sheets parser authenticates and reads sheet data
4. Parser extracts 500 product rows with prices and characteristics
5. Service validates and normalizes data
6. Service creates Supplier record
7. Service inserts 500 records into SupplierItems table
8. Service records price history entries
9. Task completes successfully with summary logged

**Expected Outcome:** All 500 products are searchable in SupplierItems table with correct supplier reference, prices stored in PriceHistory, and characteristics accessible as JSONB

### Scenario 2: Updated Price List

**Context:** Existing supplier updates their price list with new prices

**Steps:**
1. Parse task submitted for same supplier with updated Google Sheet
2. Service processes task and identifies existing supplier
3. New prices are stored in PriceHistory with current timestamp
4. SupplierItems are updated or inserted as needed
5. Historical prices remain accessible

**Expected Outcome:** PriceHistory shows timeline of price changes, current prices reflect updates, old prices remain queryable

### Scenario 3: Malformed Data Handling

**Context:** Google Sheet contains rows with missing required fields

**Steps:**
1. Parse task submitted with sheet containing 100 rows, 10 with missing prices
2. Parser validates each row
3. Parser logs specific errors for 10 invalid rows
4. Parser successfully processes 90 valid rows
5. Task completes with partial success status
6. Error report identifies problematic rows

**Expected Outcome:** 90 valid products stored in database, 10 errors logged with row numbers and missing fields, task marked as completed with warnings

### Scenario 4: Service Failure and Recovery

**Context:** Database becomes temporarily unavailable during processing

**Steps:**
1. Parse task begins processing
2. Database connection fails mid-transaction
3. Service logs error and does not acknowledge queue message
4. Message returns to queue after visibility timeout
5. Database comes back online
6. Service retries task successfully
7. Data is fully persisted

**Expected Outcome:** No partial data in database, task eventually completes successfully, all retries logged

---

## Key Entities

### Product
- **Description:** Internal catalog item with unified SKU
- **Key Attributes:** Internal SKU (unique), name, category
- **Relationships:** Has many SupplierItems, belongs to Category

### Supplier
- **Description:** External data source providing price lists
- **Key Attributes:** Supplier ID (unique), name, contact information, source type
- **Relationships:** Has many SupplierItems

### SupplierItem
- **Description:** Raw product data from supplier price list
- **Key Attributes:** Supplier SKU, supplier reference, name, price, characteristics (JSONB), last updated
- **Relationships:** Belongs to Supplier, optionally linked to Product

### Category
- **Description:** Product classification hierarchy
- **Key Attributes:** Category ID, name, parent category
- **Relationships:** Has many Products

### PriceHistory
- **Description:** Time-series record of price changes
- **Key Attributes:** Price value, timestamp, supplier item reference
- **Relationships:** Belongs to SupplierItem

---

## Non-Functional Requirements

### NFR-1: Performance

- Queue message processing latency: < 100ms from dequeue to processing start
- Database insert throughput: > 1,000 records per minute
- Google Sheets API call response time: < 2 seconds per sheet read
- Memory usage: < 512MB per Python worker under normal load

### NFR-2: Scalability

- Support horizontal scaling by adding more Python worker containers
- Queue-based architecture enables distribution across multiple workers
- Database connection pooling supports up to 20 concurrent workers
- System handles ingestion of 100,000+ supplier items without degradation

### NFR-3: Reliability

- Message retry policy: 3 retries with exponential backoff (1s, 5s, 25s)
- Database transaction rollback on any validation or constraint failure
- Service auto-restart on crash via Docker restart policy
- Dead letter queue captures permanently failed messages for manual review

### NFR-4: Observability

- Structured JSON logging for all operations
- Log levels: DEBUG for development, INFO for production
- Metrics logged: messages processed, processing time, error rate, queue depth
- Each log entry includes request ID for tracing
- Critical errors trigger immediate log flush

### NFR-5: Data Quality

- All prices stored with 2 decimal precision
- Characteristics JSONB validated for JSON compliance
- Required fields enforced at database and application level
- Duplicate supplier items detected by supplier + supplier SKU combination
- Data encoding: UTF-8 for all text fields

---

## Technical Architecture

### System Components

```
┌─────────────────┐
│  Google Sheets  │
│   (Data Source) │
└────────┬────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────────┐
│   Python Service        │
│   ┌─────────────────┐   │
│   │ Parser Interface│   │
│   ├─────────────────┤   │
│   │ Google Parser   │   │
│   │ [Future: CSV]   │   │
│   │ [Future: Excel] │   │
│   └─────────────────┘   │
└────┬──────────────┬─────┘
     │              │
     │ Redis        │ PostgreSQL
     ▼              ▼
┌─────────┐    ┌──────────┐
│  Redis  │    │PostgreSQL│
│  Queue  │    │ Database │
└─────────┘    └──────────┘
```

### Database Schema

```sql
-- Core Tables
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- 'google_sheets', 'csv', 'excel'
    contact_email VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES categories(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    category_id UUID REFERENCES categories(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE supplier_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id), -- NULL until matched
    supplier_sku VARCHAR(255) NOT NULL,
    name VARCHAR(500) NOT NULL,
    current_price DECIMAL(10, 2) NOT NULL,
    characteristics JSONB NOT NULL DEFAULT '{}',
    last_ingested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id, supplier_sku)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_item_id UUID NOT NULL REFERENCES supplier_items(id) ON DELETE CASCADE,
    price DECIMAL(10, 2) NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_supplier_items_supplier ON supplier_items(supplier_id);
CREATE INDEX idx_supplier_items_product ON supplier_items(product_id);
CREATE INDEX idx_price_history_item ON price_history(supplier_item_id);
CREATE INDEX idx_price_history_recorded ON price_history(recorded_at DESC);
CREATE INDEX idx_supplier_items_characteristics ON supplier_items USING GIN (characteristics);
```

### Parser Interface

```python
# src/parsers/base_parser.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel

class ParsedItem(BaseModel):
    supplier_sku: str
    name: str
    price: float
    characteristics: Dict[str, Any]

class ParserInterface(ABC):
    """Abstract base class for all data source parsers"""
    
    @abstractmethod
    def parse(self, source_config: Dict[str, Any]) -> List[ParsedItem]:
        """Parse data from source and return normalized items"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate source configuration before parsing"""
        pass
    
    def get_parser_name(self) -> str:
        """Return parser identifier"""
        return self.__class__.__name__
```

### Queue Message Contract

```python
# src/models/queue_message.py
from pydantic import BaseModel
from typing import Dict, Any, Literal

class ParseTaskMessage(BaseModel):
    task_id: str
    parser_type: Literal["google_sheets", "csv", "excel"]
    supplier_name: str
    source_config: Dict[str, Any]  # Parser-specific configuration
    retry_count: int = 0
    max_retries: int = 3
```

### Google Sheets Parser Configuration

```python
# Example source_config for Google Sheets parser
{
    "sheet_url": "https://docs.google.com/spreadsheets/d/...",
    "sheet_name": "Price List",
    "column_mapping": {
        "sku": "A",
        "name": "B",
        "price": "C",
        "characteristics": ["D", "E", "F"]  # Multiple columns merged
    },
    "header_row": 1,
    "data_start_row": 2
}
```

---

## Data Models

### Python Service (Pydantic)

```python
# src/models/supplier.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

class Supplier(BaseModel):
    id: Optional[UUID] = None
    name: str = Field(..., max_length=255)
    source_type: str = Field(..., max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SupplierItem(BaseModel):
    id: Optional[UUID] = None
    supplier_id: UUID
    product_id: Optional[UUID] = None
    supplier_sku: str = Field(..., max_length=255)
    name: str = Field(..., max_length=500)
    current_price: float = Field(..., ge=0, decimal_places=2)
    characteristics: Dict[str, Any] = Field(default_factory=dict)
    last_ingested_at: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class PriceHistoryEntry(BaseModel):
    id: Optional[UUID] = None
    supplier_item_id: UUID
    price: float = Field(..., ge=0, decimal_places=2)
    recorded_at: datetime
```

---

## Error Handling

### Python Service Error Categories

```python
# src/errors/exceptions.py
class DataIngestionError(Exception):
    """Base exception for data ingestion errors"""
    pass

class ParserError(DataIngestionError):
    """Errors during data parsing"""
    pass

class ValidationError(DataIngestionError):
    """Data validation failures"""
    pass

class DatabaseError(DataIngestionError):
    """Database operation failures"""
    pass

class QueueError(DataIngestionError):
    """Queue communication failures"""
    pass
```

### Error Handling Strategy

```python
# Queue message processing
def process_message(message: ParseTaskMessage):
    try:
        # Parse data
        items = parser.parse(message.source_config)
        
        # Begin database transaction
        with db.transaction():
            supplier = get_or_create_supplier(message.supplier_name)
            for item in items:
                save_supplier_item(supplier.id, item)
                create_price_history(item)
        
        logger.info(f"Successfully processed {len(items)} items")
        
    except ValidationError as e:
        # Invalid data - move to dead letter queue
        logger.error(f"Validation failed: {e}")
        move_to_dlq(message, str(e))
        
    except (ParserError, DatabaseError) as e:
        # Retriable errors
        if message.retry_count < message.max_retries:
            message.retry_count += 1
            requeue_with_delay(message, backoff_delay(message.retry_count))
            logger.warning(f"Retrying task {message.task_id}: {e}")
        else:
            move_to_dlq(message, str(e))
            logger.error(f"Max retries exceeded: {e}")
            
    except Exception as e:
        # Unexpected errors
        logger.exception(f"Unexpected error processing task: {e}")
        move_to_dlq(message, str(e))
```

---

## Testing Requirements

### Unit Tests

**Python Service:**
- Parser interface implementations (mock Google Sheets API)
- Data validation and normalization functions
- Pydantic model validation
- Error handling for each exception type
- Queue message serialization/deserialization

**Database:**
- Schema constraint validation
- JSONB operations on characteristics
- Foreign key relationships
- Unique constraint enforcement

### Integration Tests

**End-to-End Flow:**
- Message enqueued → processed → data persisted
- Google Sheets API integration (test sheet)
- Database transaction rollback on errors
- Dead letter queue message routing
- Price history tracking across updates

**Error Scenarios:**
- Network timeout during API call
- Database connection loss mid-transaction
- Invalid JSONB format in characteristics
- Duplicate supplier SKU handling
- Missing required fields in source data

### Performance Tests

- Process 10,000 items within 10 minutes
- Measure queue throughput with 5 concurrent workers
- Database insert performance benchmarks
- Memory usage under sustained load

**Coverage Target:** ≥85% for all business logic

---

## Deployment

### Environment Variables

```bash
# Python Service
DATABASE_URL=postgresql://user:password@postgres:5432/marketbel
REDIS_URL=redis://redis:6379/0
QUEUE_NAME=price-ingestion-queue
DLQ_NAME=price-ingestion-dlq
LOG_LEVEL=INFO
WORKER_COUNT=3
GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials/google-sheets.json

# Database
POSTGRES_USER=marketbel_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=marketbel

# Redis
REDIS_PASSWORD=secure_redis_password
```

### Docker Configuration

```yaml
# docker-compose.yml excerpt
services:
  python-ingestion-service:
    build:
      context: ./services/python-ingestion
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - postgres
      - redis
    volumes:
      - ./credentials:/app/credentials:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped
```

### Migration Strategy

1. **Database Setup:**
   - Run initial schema migration
   - Create indexes
   - Verify constraints

2. **Service Deployment:**
   - Build Python service Docker image
   - Deploy with 1 worker initially
   - Monitor logs for startup errors
   - Scale to 3 workers after validation

3. **Validation:**
   - Submit test parse task with small dataset
   - Verify data in database
   - Check queue processing metrics
   - Review error logs

---

## Assumptions

1. **Data Volume:** Initial phase expects < 100,000 supplier items total
2. **Data Sources:** Google Sheets will remain primary source for Phase 1
3. **Update Frequency:** Price lists updated no more than once per day per supplier
4. **Data Format:** Google Sheets follow consistent column structure
5. **Authentication:** Google Sheets are publicly readable or service account has access
6. **Network:** Python service has stable internet connection for API calls
7. **Resources:** Docker host has minimum 2GB RAM and 2 CPU cores available
8. **Characteristics:** Flexible JSONB format allows for supplier-specific fields without schema changes
9. **Price Precision:** All prices use decimal (2 places) - no fractional currency handling needed
10. **Time Zones:** All timestamps stored in UTC

---

## Documentation

- [ ] README with setup instructions for local development
- [ ] Database schema diagram
- [ ] Parser implementation guide for adding new sources
- [ ] Queue message format specification
- [ ] Docker deployment guide
- [ ] Inline code documentation for parser interface and error handling

---

## Rollback Plan

**Trigger Conditions:**

- Database migration fails or causes data corruption
- Service crash loop prevents startup
- Data validation errors exceed 10% of processed items
- Queue message processing stops entirely

**Rollback Steps:**

1. Stop Python service containers
2. Drain Redis queue to prevent data loss
3. Rollback database migration if applied
4. Restore from database backup if data corrupted
5. Revert to previous Docker image version
6. Restart service with previous configuration
7. Verify health checks pass
8. Re-queue messages from dead letter queue manually after fixes

---

## Exceptions & Deviations

**None**

---

## Appendix

### Glossary

- **Internal SKU:** Unique identifier for unified product across all suppliers
- **Supplier Item:** Raw product record from a specific supplier's price list
- **Parser Interface:** Abstract base class defining contract for data source parsers
- **Parse Task:** Queue message requesting ingestion of data from a specific source
- **Dead Letter Queue (DLQ):** Storage for messages that failed after maximum retry attempts
- **Characteristics:** Flexible key-value metadata describing product attributes (size, color, material, etc.)
- **JSONB:** PostgreSQL binary JSON storage format with indexing support

### References

- PostgreSQL JSONB documentation: https://www.postgresql.org/docs/current/datatype-json.html
- Google Sheets API v4: https://developers.google.com/sheets/api
- Redis Queue Patterns: https://redis.io/topics/data-types-intro#redis-lists
- Pydantic Data Validation: https://docs.pydantic.dev/

---

**Approval:**

- [x] Tech Lead: [Mark] - [24.11.25]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
