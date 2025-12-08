# Marketbel - Project Documentation Summary

**Last Updated:** December 2024  
**Status:** 9 phases complete ✅, 1 in progress 🚧

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Services Overview](#services-overview)
4. [Technology Stack](#technology-stack)
5. [Completed Phases](#completed-phases)
6. [In Progress Phases](#in-progress-phases)
7. [Key Features](#key-features)
8. [Database Schema](#database-schema)
9. [API Endpoints](#api-endpoints)
10. [Development Setup](#development-setup)
11. [Deployment](#deployment)
12. [Documentation References](#documentation-references)

---

## Project Overview

**Marketbel** is a unified catalog system for supplier price list management and product catalog aggregation. It provides a complete solution for:

- **Data Ingestion:** Automated parsing of supplier data from Google Sheets, CSV, Excel, and PDF files
- **Semantic ETL:** LLM-powered extraction from complex/unstructured supplier files
- **Product Matching:** AI-powered matching of supplier items to internal products
- **Variant Detection:** Automatic grouping of product variants (voltage, capacity, color, etc.)
- **Catalog Management:** Public-facing product catalog with role-based admin interfaces
- **Category Governance:** Hybrid fuzzy matching + manual review for category normalization

### Project Status

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Python Worker (Data Ingestion) | ✅ Complete | Core data parsing infrastructure |
| 2 | Bun API (REST API Layer) | ✅ Complete | High-performance REST API |
| 3 | React Frontend | ✅ Complete | User-facing web application |
| 4 | Product Matching Pipeline | ✅ Complete | Automated product matching |
| 5 | Frontend i18n | ✅ Complete | Internationalization (EN/RU) |
| 6 | Admin Sync Scheduler | ✅ Complete | Centralized supplier sync management |
| 7 | ML-Analyze Service (RAG Pipeline) | ✅ Complete | AI-powered file parsing |
| 8 | ML-Ingestion Integration | ✅ Complete | Courier pattern integration |
| 9 | Semantic ETL | ✅ Complete | LLM-based extraction pipeline |
| 10 | Product Variants | 🚧 In Progress | Variant grouping & detection |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  - Public catalog browsing                                      │
│  - Admin dashboards (sales, procurement)                        │
│  - Supplier management UI                                       │
│  - Category review UI                                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP/REST
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Bun API (ElysiaJS)                         │
│  - REST API endpoints                                           │
│  - JWT authentication                                           │
│  - Request validation (TypeBox)                                 │
│  - Job enqueueing                                               │
└───────────┬───────────────────────────────┬─────────────────────┘
            │                               │
            │ Redis Queue                   │ HTTP REST
            ▼                               ▼
┌──────────────────────────┐   ┌─────────────────────────────────┐
│  Python Worker           │   │  ML-Analyze Service             │
│  (Data Courier)          │   │  (Intelligence)                 │
│                          │   │                                 │
│  - File download         │──▶│  - Semantic ETL (LLM)           │
│  - Google Sheets export  │   │  - Smart sheet selection        │
│  - Job state management  │   │  - Markdown grid conversion     │
│  - ML service trigger    │   │  - Category normalization       │
│  - Status polling        │   │  - Deduplication                │
│                          │   │  - Vector embeddings            │
└───────────┬──────────────┘   └───────────┬─────────────────────┘
            │                               │
            │ Shared Volume (/uploads)      │
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │   PostgreSQL 16       │
                │   + pgvector          │
                │                       │
                │  - suppliers          │
                │  - products           │
                │  - supplier_items     │
                │  - product_embeddings │
                │  - match_review_queue │
                │  - categories         │
                │  - parsing_logs       │
                │  - product_variants   │
                └───────────────────────┘
```

### Courier Pattern (Phase 8)

The system uses a **Courier Pattern** where:
- **python-ingestion** acts as a **data courier** (downloads files, manages job state)
- **ml-analyze** provides **intelligence** (parsing, matching, enrichment)

**Communication:**
- **Shared Volume:** Zero-copy file handoff via Docker volume (`/uploads`)
- **HTTP REST:** Triggering analysis, polling status
- **Redis:** Job state management, queue tasks

### Semantic ETL Pipeline (Phase 9)

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Excel/    │    │  Markdown   │    │     LLM      │    │   Category  │
│   CSV/PDF   │───▶│    Grid     │───▶│  Extraction  │───▶│  Normalizer │
│   File      │    │ Conversion  │    │  (llama3)    │    │ (RapidFuzz) │
└─────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                                            │                    │
                                            ▼                    ▼
                                   ┌──────────────┐    ┌─────────────┐
                                   │ Deduplication│    │  Category   │
                                   │  (hash-based)│    │   Review    │
                                   └──────────────┘    │   Queue     │
                                            │          └─────────────┘
                                            ▼
                                   ┌──────────────┐
                                   │ supplier_items│
                                   │   (database)  │
                                   └──────────────┘
```

---

## Services Overview

### 1. Python Worker (`python-ingestion`)

**Purpose:** Data acquisition and job orchestration (Data Courier)

**Responsibilities:**
- Download files from Google Sheets, HTTP sources
- Export Google Sheets to XLSX/CSV
- Save files to shared volume with metadata
- Trigger ML analysis via HTTP
- Poll ML job status (5s intervals)
- Manage Redis job state
- File cleanup (24h TTL)

**Key Components:**
- `src/tasks/download_tasks.py` - File download + ML trigger
- `src/tasks/ml_polling_tasks.py` - Status polling
- `src/tasks/cleanup_tasks.py` - File cleanup cron
- `src/tasks/sync_tasks.py` - Master sheet sync
- `src/services/ml_client.py` - HTTP client for ml-analyze
- `src/services/job_state.py` - Redis job state helpers

**Technology:**
- Python 3.12+
- SQLAlchemy 2.0 (AsyncIO)
- arq (Redis-based queue)
- Pydantic 2.x

---

### 2. ML-Analyze Service (`ml-analyze`)

**Purpose:** AI-powered file parsing, semantic extraction, and product matching

**Responsibilities:**
- Smart sheet selection (find "Upload to site" or product sheets)
- Convert Excel/CSV to Markdown grid (preserves layout)
- LLM-based product extraction (sliding window, 250 rows/chunk)
- Category normalization via fuzzy matching (85% threshold)
- Within-file deduplication (hash-based)
- Vector embeddings generation (768-dim)
- Semantic product matching using LLM reasoning
- Store results in PostgreSQL

**Key Components:**
- `src/api/main.py` - FastAPI application
- `src/services/smart_parser/service.py` - ETL orchestration
- `src/services/smart_parser/markdown_converter.py` - Excel → Markdown
- `src/services/smart_parser/langchain_extractor.py` - LLM extraction
- `src/services/smart_parser/prompts.py` - LLM prompt templates
- `src/services/smart_parser/sheet_selector.py` - Multi-sheet logic
- `src/services/category_normalizer.py` - Fuzzy matching (RapidFuzz)
- `src/services/deduplication_service.py` - Hash-based deduplication
- `src/rag/vector_service.py` - Embedding + vector search
- `src/rag/merger_agent.py` - LLM-based matching
- `src/schemas/extraction.py` - ExtractedProduct Pydantic models

**Technology:**
- FastAPI + uvicorn
- LangChain + LangChain-Ollama
- Ollama (nomic-embed-text, llama3)
- pgvector (PostgreSQL extension)
- pymupdf4llm (PDF), openpyxl (Excel)
- RapidFuzz (fuzzy string matching)

**API Endpoints:**
- `POST /analyze/file` - Trigger file analysis
- `GET /analyze/status/:job_id` - Poll job progress
- `POST /analyze/merge` - Batch product matching
- `GET /health` - Service health check

---

### 3. Bun API (`bun-api`)

**Purpose:** REST API layer for frontend and external clients

**Responsibilities:**
- HTTP request handling
- JWT authentication
- Request validation
- Job enqueueing to Redis
- Database queries via Drizzle ORM
- Category review management

**Key Components:**
- `src/controllers/` - HTTP handlers (auth, catalog, admin)
- `src/services/` - Business logic layer
- `src/services/category.service.ts` - Category review backend
- `src/db/repositories/` - Data access layer
- `src/middleware/` - Auth, error handling, logging

**Technology:**
- Bun runtime
- ElysiaJS framework
- Drizzle ORM
- TypeBox validation
- @elysiajs/jwt, bcrypt

**API Endpoints:**
- `GET /api/v1/catalog` - Public product catalog
- `GET /api/v1/catalog/:id` - Product details (with variants)
- `POST /api/v1/auth/login` - Authentication
- `GET /api/v1/admin/products` - Admin product list
- `PATCH /api/v1/admin/products/:id/match` - Link/unlink supplier items
- `POST /api/v1/admin/sync` - Trigger data sync
- `GET /api/v1/admin/sync/status` - Sync status with jobs
- `POST /api/v1/admin/jobs/:id/retry` - Retry failed job
- `GET /api/v1/admin/categories/review` - Categories needing review
- `PATCH /api/v1/admin/categories/:id` - Approve/merge category

---

### 4. Frontend (`frontend`)

**Purpose:** User-facing web application

**Responsibilities:**
- Public product catalog browsing
- Admin dashboards (sales, procurement)
- Supplier management UI
- Job status monitoring
- Product matching interface
- Category review admin UI
- Variant selector component

**Key Components:**
- `src/pages/` - Route components
- `src/pages/admin/IngestionPage.tsx` - Ingestion control panel
- `src/pages/admin/CategoryReviewPage.tsx` - Category review UI
- `src/components/admin/` - Admin UI components
- `src/components/admin/JobPhaseIndicator.tsx` - Multi-phase status
- `src/components/admin/LiveLogViewer.tsx` - Real-time logs
- `src/components/catalog/VariantSelector.tsx` - Variant UI
- `src/hooks/` - Custom React hooks
- `src/lib/api-client.ts` - API client

**Technology:**
- React 18+ with TypeScript
- Vite 5+
- TanStack Query v5
- Radix UI Themes
- Tailwind CSS v4.1 (CSS-first)
- react-i18next

**Routes:**
- `/` - Public catalog
- `/product/:id` - Product details (with variant selector)
- `/admin` - Admin dashboard
- `/admin/sales` - Sales catalog
- `/admin/procurement` - Procurement matching
- `/admin/ingestion` - Ingestion control
- `/admin/categories/review` - Category review

---

## Technology Stack

### Backend Services

| Service | Runtime | Framework | ORM | Queue |
|---------|---------|-----------|-----|-------|
| Python Worker | Python 3.12+ | arq | SQLAlchemy 2.0 | Redis (arq) |
| ML-Analyze | Python 3.12+ | FastAPI | asyncpg | Redis |
| Bun API | Bun | ElysiaJS | Drizzle ORM | Redis |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18+ | UI framework |
| TypeScript | 5.9+ | Type safety |
| Vite | 5+ | Build tool |
| TanStack Query | 5.x | Server state |
| Radix UI | 3.x | UI components |
| Tailwind CSS | 4.1 | Styling (CSS-first) |
| react-i18next | Latest | i18n (EN/RU) |

### Infrastructure

| Component | Version | Purpose |
|-----------|---------|---------|
| PostgreSQL | 16 | Primary database |
| pgvector | Latest | Vector similarity search |
| Redis | 7 | Queue & cache |
| Docker Compose | v2 | Container orchestration |
| Ollama | Latest | Local LLM (nomic-embed-text, llama3) |

### ML/AI Stack

| Component | Purpose |
|-----------|---------|
| LangChain + LangChain-Ollama | LLM orchestration |
| llama3 | Product extraction & matching |
| nomic-embed-text | 768-dim vector embeddings |
| RapidFuzz | Category fuzzy matching |
| pymupdf4llm | PDF parsing |
| openpyxl | Excel parsing |

---

## Completed Phases

### Phase 1: Python Worker (Data Ingestion)

**Status:** ✅ Complete

**Features:**
- Async data parsing from Google Sheets, CSV, Excel
- Queue-based task processing (arq)
- Structured error logging to `parsing_logs`
- Database persistence (SQLAlchemy 2.0)
- Price history tracking

**Key Files:**
- `services/python-ingestion/src/parsers/` - Data source parsers
- `services/python-ingestion/src/tasks/` - Queue tasks
- `services/python-ingestion/src/db/models/` - ORM models

---

### Phase 2: Bun API (REST API Layer)

**Status:** ✅ Complete

**Features:**
- High-performance REST API (ElysiaJS)
- JWT authentication with role-based access (sales, procurement, admin)
- Type-safe request validation (TypeBox)
- OpenAPI documentation
- Database connection pooling

**Key Files:**
- `services/bun-api/src/controllers/` - HTTP handlers
- `services/bun-api/src/services/` - Business logic
- `services/bun-api/src/db/repositories/` - Data access

---

### Phase 3: React Frontend

**Status:** ✅ Complete

**Features:**
- Public product catalog with filters
- Admin dashboards (sales, procurement)
- Shopping cart functionality (mock)
- Responsive design
- Type-safe API client (TanStack Query)

**Key Files:**
- `services/frontend/src/pages/` - Route components
- `services/frontend/src/components/` - UI components
- `services/frontend/src/hooks/` - Custom hooks

---

### Phase 4: Product Matching Pipeline

**Status:** ✅ Complete

**Features:**
- Automated product matching (RapidFuzz)
- Confidence-based matching thresholds
- Review queue for uncertain matches
- Batch processing

**Matching Thresholds:**
- ≥95%: Auto-match
- 70-95%: Review queue
- <70%: Reject

---

### Phase 5: Frontend i18n

**Status:** ✅ Complete

**Features:**
- react-i18next integration
- English/Russian translations
- Translation files in `public/locales/`
- All UI text via i18n
- Browser language detection
- Language preference persistence

---

### Phase 6: Admin Sync Scheduler

**Status:** ✅ Complete

**Features:**
- Master Google Sheet parser
- Automated supplier sync (8h interval)
- Manual sync trigger
- Admin UI with status dashboard
- Live log streaming
- Supplier status tracking (Success/Error/Pending)

**Key Files:**
- `services/python-ingestion/src/parsers/master_sheet_parser.py`
- `services/python-ingestion/src/tasks/sync_tasks.py`
- `services/frontend/src/pages/admin/IngestionPage.tsx`

---

### Phase 7: ML-Analyze Service (RAG Pipeline)

**Status:** ✅ Complete

**Features:**
- Complex file parsing (PDF tables, Excel merged cells)
- Vector embeddings (768-dim via nomic-embed-text)
- Semantic search (pgvector with IVFFLAT index)
- LLM-based matching (llama3)
- Confidence-based auto-matching

**Key Files:**
- `services/ml-analyze/src/rag/vector_service.py`
- `services/ml-analyze/src/rag/merger_agent.py`
- `services/ml-analyze/src/ingest/` - File parsers

---

### Phase 8: ML-Ingestion Integration (Courier Pattern)

**Status:** ✅ Complete

**Features:**
- Courier pattern architecture
- Shared volume file handoff (`/uploads`)
- Multi-phase job status (downloading → analyzing → matching → complete)
- Retry logic (max 3 attempts)
- Automatic file cleanup (24h TTL)
- Per-supplier ML toggle

**Job Phases:** `downloading` → `analyzing` → `matching` → `complete`/`failed`

**Key Files:**
- `services/python-ingestion/src/tasks/download_tasks.py`
- `services/python-ingestion/src/services/ml_client.py`
- `services/frontend/src/components/admin/JobPhaseIndicator.tsx`

---

### Phase 9: Semantic ETL

**Status:** ✅ Complete

**Features:**
- LLM-based extraction replacing fragile pandas/regex parsing
- Smart sheet selection (find "Upload to site" or product sheets)
- Excel → Markdown grid representation (preserves layout)
- Sliding window LLM extraction (250 rows/chunk, 40-row overlap)
- Category fuzzy matching (85% threshold, RapidFuzz)
- Within-file deduplication (hash-based, 1% price tolerance)
- Partial success handling (80-99% = "completed_with_errors")
- Category review admin UI (`/admin/categories/review`)

**Extended Job Phases:** `downloading` → `analyzing` (sheet selection) → `extracting` (LLM) → `normalizing` (categories) → `complete`/`completed_with_errors`/`failed`

**Key Files:**
- `services/ml-analyze/src/schemas/extraction.py` - ExtractedProduct Pydantic models
- `services/ml-analyze/src/services/smart_parser/service.py` - Orchestration
- `services/ml-analyze/src/services/smart_parser/markdown_converter.py` - Excel → Markdown
- `services/ml-analyze/src/services/smart_parser/langchain_extractor.py` - LLM extraction
- `services/ml-analyze/src/services/smart_parser/prompts.py` - LLM prompt templates
- `services/ml-analyze/src/services/smart_parser/sheet_selector.py` - Multi-sheet logic
- `services/ml-analyze/src/services/category_normalizer.py` - Fuzzy matching
- `services/ml-analyze/src/services/deduplication_service.py` - Hash-based deduplication
- `services/bun-api/src/services/category.service.ts` - Category review backend
- `services/frontend/src/pages/admin/CategoryReviewPage.tsx` - Admin review UI

**Schema Changes:**
- `categories`: Add `parent_id`, `needs_review`, `is_active`, `supplier_id`
- `parsing_logs`: Add `chunk_id`, `row_number`, `error_type`, `extraction_phase`

---

## In Progress Phases

### Phase 10: Product Variants

**Status:** 🚧 In Progress

**Purpose:** Enable grouping of products that are essentially the same but with different specifications (e.g., different battery voltage, storage capacity, color).

**Problem Statement:**
Currently, suppliers provide products like:
- "Электровелосипед Shtenli GT 15 48V/20A" @ 1990 BYN
- "Электровелосипед Shtenli GT 15 60V/20A" @ 2090 BYN

These are stored as separate items with no relationship, leading to duplicated entries and no variant comparison for users.

**Planned Features:**
- Extract variant attributes from product names via LLM
- Automatic variant detection (name similarity + different attributes)
- Variant grouping with `product_variants` table
- Frontend variant selector component (like Onliner.by)

**Data Flow:**
1. LLM Extraction → Extract `variant_attributes` from product names
2. Variant Detection → Group similar products (RapidFuzz >85%, price within 2x)
3. Variant Grouping → Create `product_variants`, link `supplier_items`
4. Frontend → Display variant selector

**Variant Attribute Examples:**

| Category | Attributes | Example Key |
|----------|-----------|-------------|
| Electric Transport | voltage, capacity | "48V/20A" |
| Electronics | storage, color | "256GB/Black" |
| Laptops | ram, storage | "16GB/512GB" |

**Key Files (In Progress):**
- `services/ml-analyze/src/services/variant_detection_service.py`
- `services/bun-api/src/db/repositories/variant.repository.ts`
- `services/frontend/src/components/catalog/VariantSelector.tsx`
- `services/python-ingestion/migrations/versions/010_product_variants.py`

---

## Key Features

### Data Ingestion

- **Multi-source Support:** Google Sheets, CSV, Excel, PDF files
- **Automated Sync:** Scheduled synchronization from Master Sheet (8h interval)
- **Error Isolation:** Per-row logging, worker never crashes on bad data
- **Semantic ETL:** LLM-powered extraction for complex unstructured data
- **Smart Sheet Selection:** Automatically finds product data sheets

### Semantic Extraction (Phase 9)

- **Markdown Grid:** Preserves Excel layout for LLM context
- **Sliding Window:** 250 rows/chunk with 40-row overlap
- **Strict Schema:** Pydantic validation for extracted products
- **Multi-currency:** Handles various price formats, logs non-BYN currencies

### Product Matching

- **Dual Pipeline:**
  - Traditional: RapidFuzz string matching (Phase 4)
  - ML-Powered: LLM reasoning with semantic search (Phase 7)
- **Confidence Thresholds:** Auto-match, review queue, or reject
- **Batch Processing:** Efficient handling of large datasets

### Category Governance

- **Fuzzy Matching:** 85% similarity threshold (RapidFuzz)
- **Auto-Creation:** New categories created with `needs_review = true`
- **Admin Review:** Approve, merge, or rename categories
- **Hierarchy Support:** Parent-child category relationships

### Admin Features

- **Role-Based Access:** sales, procurement, admin roles
- **Supplier Management:** Create, update, sync suppliers
- **Job Monitoring:** Real-time status with phase indicators
- **Retry Logic:** Manual retry for failed jobs
- **Log Streaming:** Live ingestion logs
- **Category Review:** Admin UI for category approval

### Public Catalog

- **Product Browsing:** Filter by category, price, supplier
- **Product Variants:** Compare variants with different specs (Phase 10)
- **Shopping Cart:** Add to cart, checkout flow (mock)
- **Responsive Design:** Mobile-friendly UI
- **Internationalization:** English and Russian support

---

## Database Schema

### Core Tables

| Table | Description | Owner |
|-------|-------------|-------|
| `suppliers` | External data sources | Phase 1 |
| `products` | Internal catalog (draft/active/archived) | Phase 1 |
| `supplier_items` | Raw supplier data with JSONB characteristics | Phase 1 |
| `product_embeddings` | Vector embeddings (768-dim) | Phase 7 |
| `price_history` | Time-series price tracking | Phase 1 |
| `parsing_logs` | Structured error logging (with extraction phase) | Phase 1, 9 |
| `users` | Authentication (roles: sales, procurement, admin) | Phase 2 |
| `match_review_queue` | Pending matches for human review | Phase 4 |
| `categories` | Product categories (with needs_review, parent_id) | Phase 1, 9 |
| `product_variants` | Variant groupings | Phase 10 |

### Key Relationships

- `supplier_items.product_id` → `products.id` (nullable, for matched items)
- `supplier_items.variant_id` → `product_variants.id` (Phase 10)
- `product_embeddings.product_id` → `products.id`
- `match_review_queue.supplier_item_id` → `supplier_items.id`
- `match_review_queue.product_id` → `products.id`
- `categories.parent_id` → `categories.id` (hierarchy)

### Phase 9 Schema Extensions

```sql
-- Categories table extensions
ALTER TABLE categories ADD COLUMN parent_id UUID REFERENCES categories(id);
ALTER TABLE categories ADD COLUMN needs_review BOOLEAN DEFAULT false;
ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT true;
ALTER TABLE categories ADD COLUMN supplier_id UUID REFERENCES suppliers(id);

-- Parsing logs extensions
ALTER TABLE parsing_logs ADD COLUMN chunk_id VARCHAR(100);
ALTER TABLE parsing_logs ADD COLUMN row_number INTEGER;
ALTER TABLE parsing_logs ADD COLUMN error_type VARCHAR(50);
ALTER TABLE parsing_logs ADD COLUMN extraction_phase VARCHAR(50);
```

### Phase 10 Schema (Product Variants)

```sql
CREATE TABLE product_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    variant_key VARCHAR(255) NOT NULL,
    variant_attributes JSONB NOT NULL DEFAULT '{}',
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, variant_key)
);

ALTER TABLE products ADD COLUMN has_variants BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN variant_schema JSONB;
ALTER TABLE supplier_items ADD COLUMN variant_id UUID REFERENCES product_variants(id);
```

---

## API Endpoints

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/catalog` | Browse active products |
| GET | `/api/v1/catalog/:id` | Product details (with variants) |
| POST | `/api/v1/auth/login` | Login and get JWT token |

### Admin Endpoints (JWT Required)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/api/v1/admin/products` | any | List products with supplier details |
| PATCH | `/api/v1/admin/products/:id/match` | procurement, admin | Link/unlink supplier items |
| POST | `/api/v1/admin/products` | procurement, admin | Create new product |
| POST | `/api/v1/admin/sync` | admin | Trigger data sync |
| GET | `/api/v1/admin/sync/status` | admin | Get sync status with jobs |
| POST | `/api/v1/admin/jobs/:id/retry` | admin | Retry failed job |
| GET | `/api/v1/admin/categories/review` | admin | List categories needing review |
| PATCH | `/api/v1/admin/categories/:id` | admin | Approve/merge category |

### ML-Analyze Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check (DB, Redis, Ollama) |
| POST | `/analyze/file` | Trigger file analysis (returns job_id) |
| GET | `/analyze/status/:job_id` | Check job progress and results |
| POST | `/analyze/merge` | Trigger batch product matching |

---

## Development Setup

### Prerequisites

- **Bun** (latest) - For API and frontend
- **Python 3.12+** - For worker and ML service
- **Docker & Docker Compose** - For infrastructure
- **PostgreSQL 16+** - Database (or via Docker)
- **Redis 7+** - Queue & cache (or via Docker)
- **Ollama** - Local LLM (nomic-embed-text, llama3)

### Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd marketbel

# 2. Start infrastructure
docker-compose up -d postgres redis

# 3. Set up Python services
cd services/python-ingestion
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

cd ../ml-analyze
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. Set up Bun API
cd ../bun-api
bun install
bun run db:introspect

# 5. Set up Frontend
cd ../frontend
bun install

# 6. Install Ollama models
ollama pull nomic-embed-text
ollama pull llama3

# 7. Start all services
docker-compose up -d
```

### Development Commands

```bash
# Python Worker
cd services/python-ingestion
source venv/bin/activate
arq src.worker.WorkerSettings

# ML-Analyze Service
cd services/ml-analyze
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8001

# Bun API
cd services/bun-api
bun --watch src/index.ts

# Frontend
cd services/frontend
bun run dev
```

### Testing

```bash
# Python Worker
cd services/python-ingestion
pytest tests/ -v --cov=src

# ML-Analyze
cd services/ml-analyze
pytest tests/ -v --cov=src

# Bun API
cd services/bun-api
bun test

# Frontend
cd services/frontend
bun run type-check
```

---

## Deployment

### Docker Compose

The project includes a complete `docker-compose.yml` with all services:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f worker
docker-compose logs -f bun-api
docker-compose logs -f ml-analyze
docker-compose logs -f frontend

# Rebuild after changes
docker-compose build <service-name>
docker-compose up -d <service-name>
```

### Services

- **postgres:** PostgreSQL 16 with pgvector
- **redis:** Redis 7 with password auth
- **worker:** Python ingestion worker
- **bun-api:** REST API service
- **frontend:** React web application
- **ml-analyze:** ML analysis service

### Environment Variables

Key environment variables (see `docker-compose.yml` for full list):

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/marketbel

# Redis
REDIS_PASSWORD=secure_password

# JWT
JWT_SECRET=your-secret-key-min-32-chars

# ML Service
ML_ANALYZE_URL=http://ml-analyze:8001
USE_ML_PROCESSING=true

# Semantic ETL (Phase 9)
USE_SEMANTIC_ETL=true
FUZZY_MATCH_THRESHOLD=85
CHUNK_SIZE_ROWS=250
CHUNK_OVERLAP_ROWS=40
OLLAMA_MODEL_LLM=llama3
OLLAMA_TEMPERATURE=0.2

# Ollama
OLLAMA_BASE_URL=http://ollama:11434

# Polling & Cleanup
ML_POLL_INTERVAL_SECONDS=5
FILE_CLEANUP_TTL_HOURS=24
MAX_FILE_SIZE_MB=50
```

### Health Checks

All services include health check endpoints:
- Bun API: `GET /health`
- ML-Analyze: `GET /health`
- Python Worker: `python -m src.health_check`

---

## Documentation References

### Main Documentation

- **Project Context:** `/CLAUDE.md` - Main project documentation
- **This Summary:** `/docs/PROJECT_SUMMARY.md` - Comprehensive project overview
- **Architecture Decisions:** `/docs/adr/` - ADR documents

### Service-Specific READMEs

- **Python Worker:** `/services/python-ingestion/README.md`
- **Bun API:** `/services/bun-api/README.md`
- **Frontend:** `/services/frontend/README.md`
- **ML-Analyze:** `/services/ml-analyze/README.md`

### Phase Specifications

Each phase has detailed documentation in `/specs/00X-name/`:

| Phase | Spec Path |
|-------|-----------|
| 1 | `/specs/001-data-ingestion-infra/spec.md` |
| 2 | `/specs/002-api-layer/spec.md` |
| 3 | `/specs/003-frontend-app/spec.md` |
| 4 | `/specs/004-product-matching-pipeline/spec.md` |
| 5 | `/specs/005-frontend-i18n/spec.md` |
| 6 | `/specs/006-admin-sync-scheduler/spec.md` |
| 7 | `/specs/007-ml-analyze/spec.md` |
| 8 | `/specs/008-ml-ingestion-integration/spec.md` |
| 9 | `/specs/009-semantic-etl/spec.md` |
| 10 | `/specs/010-product-variants/spec.md` |

Each spec includes:
- `spec.md` - Feature specification
- `plan/research.md` - Technology decisions
- `plan/data-model.md` - Schema definitions
- `plan/quickstart.md` - Setup guide
- `plan/contracts/` - API contracts (JSON schemas)

### Additional Documentation

- **Deployment Guide:** `/docs/deployment.md`
- **Parser Guide:** `/docs/parser-guide.md`
- **Mocking Guide:** `/docs/mocking-guide.md`
- **Google Sheets Setup:** `/docs/guideline/02-google-sheets-setup.md`
- **Schema Diagram:** `/docs/schema-diagram.txt`

---

## Key Architectural Decisions

1. **SOLID Principles:** Controllers → Services → Repositories separation
2. **Error Isolation:** Per-row logging, worker never crashes on bad data
3. **Type Safety:** End-to-end types from DB → API → Frontend
4. **KISS:** Polling (no WebSockets), TanStack Query (no Redux), simple abstractions
5. **Queue-Based:** Python worker consumes tasks, API publishes
6. **Courier Pattern:** `python-ingestion` as data courier, `ml-analyze` as intelligence
7. **Semantic ETL:** LLM-based extraction over fragile regex/pandas parsing
8. **Hybrid Governance:** Fuzzy matching + manual review for categories

---

## Project Statistics

- **Total Phases:** 10 (9 complete, 1 in progress)
- **Services:** 4 (Python Worker, Bun API, Frontend, ML-Analyze)
- **Languages:** Python 3.12+, TypeScript, SQL
- **Frameworks:** FastAPI, ElysiaJS, React
- **Database:** PostgreSQL 16 with pgvector
- **Queue:** Redis 7 with arq
- **LLM:** Ollama (local, nomic-embed-text, llama3)
- **Localization:** English, Russian

---

**Version:** 2.0.0  
**Last Updated:** December 2024  
**Status:** Active Development 🚀
