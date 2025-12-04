# Marketbel - Project Documentation Summary

**Last Updated:** December 2024  
**Status:** All 8 phases complete ✅

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Services Overview](#services-overview)
4. [Technology Stack](#technology-stack)
5. [Completed Phases](#completed-phases)
6. [Key Features](#key-features)
7. [Database Schema](#database-schema)
8. [API Endpoints](#api-endpoints)
9. [Development Setup](#development-setup)
10. [Deployment](#deployment)
11. [Documentation References](#documentation-references)

---

## Project Overview

**Marketbel** is a unified catalog system for supplier price list management and product catalog. It provides a complete solution for:

- **Data Ingestion:** Automated parsing of supplier data from Google Sheets, CSV, and Excel files
- **Product Matching:** AI-powered matching of supplier items to internal products
- **Catalog Management:** Public-facing product catalog with role-based admin interfaces
- **ML-Powered Analysis:** Advanced parsing of complex unstructured data using RAG (Retrieval-Augmented Generation)

### Project Status

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Python Worker (Data Ingestion) | ✅ Complete | Core data parsing infrastructure |
| 2 | Bun API (REST API Layer) | ✅ Complete | High-performance REST API |
| 3 | React Frontend | ✅ Complete | User-facing web application |
| 4 | Product Matching Pipeline | ✅ Complete | Automated product matching |
| 5 | Frontend i18n | ✅ Complete | Internationalization support |
| 6 | Admin Sync Scheduler | ✅ Complete | Centralized supplier sync management |
| 7 | ML-Analyze Service (RAG Pipeline) | ✅ Complete | AI-powered file parsing |
| 8 | ML-Ingestion Integration | ✅ Complete | Courier pattern integration |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  - Public catalog browsing                                       │
│  - Admin dashboards (sales, procurement)                         │
│  - Supplier management UI                                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP/REST
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Bun API (ElysiaJS)                          │
│  - REST API endpoints                                            │
│  - JWT authentication                                            │
│  - Request validation (TypeBox)                                  │
│  - Job enqueueing                                                │
└───────────┬───────────────────────────────┬─────────────────────┘
            │                               │
            │ Redis Queue                   │ HTTP REST
            ▼                               ▼
┌──────────────────────────┐   ┌─────────────────────────────────┐
│  Python Worker           │   │  ML-Analyze Service             │
│  (Data Courier)          │   │  (Intelligence)                 │
│                          │   │                                 │
│  - File download         │   │  - File parsing (PDF/Excel)     │
│  - Google Sheets export  │   │  - Vector embeddings            │
│  - Job state management  │   │  - LLM-based matching          │
│  - ML service trigger    │   │  - Semantic search             │
└───────────┬──────────────┘   └───────────┬─────────────────────┘
            │                               │
            │ Shared Volume (/shared/uploads)│
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
                └───────────────────────┘
```

### Courier Pattern (Phase 8)

The system uses a **Courier Pattern** where:
- **python-ingestion** acts as a **data courier** (downloads files, manages job state)
- **ml-analyze** provides **intelligence** (parsing, matching, enrichment)

**Communication:**
- **Shared Volume:** Zero-copy file handoff via Docker volume
- **HTTP REST:** Triggering analysis, polling status
- **Redis:** Job state management, queue tasks

---

## Services Overview

### 1. Python Worker (`python-ingestion`)

**Purpose:** Data acquisition and job orchestration

**Responsibilities:**
- Download files from Google Sheets, HTTP sources
- Export Google Sheets to XLSX/CSV
- Save files to shared volume with metadata
- Trigger ML analysis via HTTP
- Poll ML job status
- Manage Redis job state
- File cleanup (24h TTL)

**Key Components:**
- `src/tasks/download_tasks.py` - File download + ML trigger
- `src/tasks/ml_polling_tasks.py` - Status polling
- `src/tasks/cleanup_tasks.py` - File cleanup cron
- `src/tasks/retry_tasks.py` - Job retry logic
- `src/services/ml_client.py` - HTTP client for ml-analyze
- `src/services/job_state.py` - Redis job state helpers

**Technology:**
- Python 3.12+
- SQLAlchemy 2.0 (AsyncIO)
- arq (Redis-based queue)
- Pydantic 2.x

---

### 2. ML-Analyze Service (`ml-analyze`)

**Purpose:** AI-powered file parsing and product matching

**Responsibilities:**
- Parse complex files (PDF tables, Excel merged cells)
- Generate vector embeddings (768-dim)
- Semantic product matching using LLM reasoning
- Store results in PostgreSQL

**Key Components:**
- `src/api/main.py` - FastAPI application
- `src/ingest/excel_strategy.py` - Excel parser
- `src/ingest/pdf_strategy.py` - PDF parser
- `src/rag/vector_service.py` - Embedding + vector search
- `src/rag/merger_agent.py` - LLM-based matching

**Technology:**
- FastAPI + uvicorn
- LangChain + LangChain-Ollama
- Ollama (nomic-embed-text, llama3)
- pgvector (PostgreSQL extension)
- pymupdf4llm (PDF), openpyxl (Excel)

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

**Key Components:**
- `src/controllers/` - HTTP handlers (auth, catalog, admin)
- `src/services/` - Business logic layer
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
- `POST /api/v1/auth/login` - Authentication
- `GET /api/v1/admin/products` - Admin product list
- `PATCH /api/v1/admin/products/:id/match` - Link/unlink supplier items
- `POST /api/v1/admin/sync` - Trigger data sync
- `POST /api/v1/admin/jobs/:id/retry` - Retry failed job

---

### 4. Frontend (`frontend`)

**Purpose:** User-facing web application

**Responsibilities:**
- Public product catalog browsing
- Admin dashboards (sales, procurement)
- Supplier management UI
- Job status monitoring
- Product matching interface

**Key Components:**
- `src/pages/` - Route components
- `src/components/admin/` - Admin UI components
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
- `/product/:id` - Product details
- `/admin` - Admin dashboard
- `/admin/sales` - Sales catalog
- `/admin/procurement` - Procurement matching
- `/admin/ingestion` - Ingestion control

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
| Tailwind CSS | 4.1 | Styling |

### Infrastructure

| Component | Version | Purpose |
|-----------|---------|---------|
| PostgreSQL | 16 | Primary database |
| pgvector | Latest | Vector similarity search |
| Redis | 7 | Queue & cache |
| Docker Compose | v2 | Container orchestration |
| Ollama | Latest | Local LLM (nomic-embed-text, llama3) |

---

## Completed Phases

### Phase 1: Python Worker (Data Ingestion)

**Status:** ✅ Complete

**Features:**
- Async data parsing from Google Sheets, CSV, Excel
- Queue-based task processing (arq)
- Structured error logging
- Database persistence (SQLAlchemy 2.0)

**Key Files:**
- `services/python-ingestion/src/parsers/` - Data source parsers
- `services/python-ingestion/src/tasks/` - Queue tasks
- `services/python-ingestion/src/db/models/` - ORM models

---

### Phase 2: Bun API (REST API Layer)

**Status:** ✅ Complete

**Features:**
- High-performance REST API (ElysiaJS)
- JWT authentication with role-based access
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
- Shopping cart functionality
- Responsive design
- Type-safe API client

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

---

### Phase 6: Admin Sync Scheduler

**Status:** ✅ Complete

**Features:**
- Master Google Sheet parser
- Automated supplier sync (8h interval)
- Manual sync trigger
- Admin UI with status dashboard
- Live log streaming

**Key Files:**
- `services/python-ingestion/src/parsers/master_sheet_parser.py`
- `services/python-ingestion/src/tasks/sync_tasks.py`
- `services/frontend/src/pages/admin/IngestionControlPage.tsx`

---

### Phase 7: ML-Analyze Service (RAG Pipeline)

**Status:** ✅ Complete

**Features:**
- Complex file parsing (PDF tables, Excel merged cells)
- Vector embeddings (768-dim via nomic-embed-text)
- Semantic search (pgvector with IVFFLAT)
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
- Shared volume file handoff
- Multi-phase job status (downloading → analyzing → matching → complete)
- Retry logic (max 3 attempts)
- Automatic file cleanup (24h TTL)
- Per-supplier ML toggle

**Key Files:**
- `services/python-ingestion/src/tasks/download_tasks.py`
- `services/python-ingestion/src/services/ml_client.py`
- `services/frontend/src/components/admin/JobPhaseIndicator.tsx`

---

## Key Features

### Data Ingestion

- **Multi-source Support:** Google Sheets, CSV, Excel files
- **Automated Sync:** Scheduled synchronization from Master Sheet
- **Error Isolation:** Per-row logging, worker never crashes on bad data
- **ML-Powered Parsing:** AI handles complex unstructured data

### Product Matching

- **Dual Pipeline:**
  - Traditional: RapidFuzz string matching (Phase 4)
  - ML-Powered: LLM reasoning with semantic search (Phase 7)
- **Confidence Thresholds:** Auto-match, review queue, or reject
- **Batch Processing:** Efficient handling of large datasets

### Admin Features

- **Role-Based Access:** sales, procurement, admin roles
- **Supplier Management:** Create, update, sync suppliers
- **Job Monitoring:** Real-time status with phase indicators
- **Retry Logic:** Manual retry for failed jobs
- **Log Streaming:** Live ingestion logs

### Public Catalog

- **Product Browsing:** Filter by category, price, supplier
- **Shopping Cart:** Add to cart, checkout flow
- **Responsive Design:** Mobile-friendly UI

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
| `parsing_logs` | Structured error logging | Phase 1 |
| `users` | Authentication (roles: sales, procurement, admin) | Phase 2 |
| `match_review_queue` | Pending matches for human review | Phase 4 |
| `categories` | Product categories | Phase 1 |

### Key Relationships

- `supplier_items.product_id` → `products.id` (nullable, for matched items)
- `product_embeddings.product_id` → `products.id`
- `match_review_queue.supplier_item_id` → `supplier_items.id`
- `match_review_queue.product_id` → `products.id`

---

## API Endpoints

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/catalog` | Browse active products |
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
- **Ollama** - Local LLM (for ML service)

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
psql $DATABASE_URL -f migrations/001_create_users.sql
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
bun test
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

- `DATABASE_URL` - PostgreSQL connection
- `REDIS_PASSWORD` - Redis password
- `JWT_SECRET` - JWT signing secret (min 32 chars)
- `ML_ANALYZE_URL` - ML service URL
- `USE_ML_PROCESSING` - Global ML toggle
- `OLLAMA_BASE_URL` - Ollama API URL

### Health Checks

All services include health check endpoints:
- Bun API: `GET /health`
- ML-Analyze: `GET /health`
- Python Worker: `python -m src.health_check`

---

## Documentation References

### Main Documentation

- **Project Context:** `/CLAUDE.md` - Main project documentation
- **Architecture Decision:** `/docs/adr/008-courier-pattern.md` - Courier pattern ADR

### Service-Specific READMEs

- **Python Worker:** `/services/python-ingestion/README.md`
- **Bun API:** `/services/bun-api/README.md`
- **Frontend:** `/services/frontend/README.md`
- **ML-Analyze:** `/services/ml-analyze/README.md`

### Phase Specifications

Each phase has detailed documentation in `/specs/00X-name/`:

- **Phase 1:** `/specs/001-data-ingestion-infra/spec.md`
- **Phase 2:** `/specs/002-api-layer/spec.md`
- **Phase 3:** `/specs/003-frontend-app/spec.md`
- **Phase 4:** `/specs/004-product-matching-pipeline/spec.md`
- **Phase 5:** `/specs/005-frontend-i18n/spec.md`
- **Phase 6:** `/specs/006-admin-sync-scheduler/spec.md`
- **Phase 7:** `/specs/007-ml-analyze/spec.md`
- **Phase 8:** `/specs/008-ml-ingestion-integration/spec.md`

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

---

## Key Architectural Decisions

1. **SOLID Principles:** Controllers → Services → Repositories separation
2. **Error Isolation:** Per-row logging, worker never crashes on bad data
3. **Type Safety:** End-to-end types from DB → API → Frontend
4. **KISS:** No WebSockets (polling), no Redux, simple abstractions
5. **Queue-Based:** Python worker consumes tasks, API publishes
6. **Courier Pattern:** `python-ingestion` as data courier, `ml-analyze` as intelligence

---

## Project Statistics

- **Total Phases:** 8 (all complete)
- **Services:** 4 (Python Worker, Bun API, Frontend, ML-Analyze)
- **Languages:** Python 3.12+, TypeScript, SQL
- **Frameworks:** FastAPI, ElysiaJS, React
- **Database:** PostgreSQL 16 with pgvector
- **Queue:** Redis 7 with arq
- **LLM:** Ollama (local, nomic-embed-text, llama3)

---

**Version:** 1.0.0  
**Last Updated:** December 2024  
**Status:** Production Ready ✅

