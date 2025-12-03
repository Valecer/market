# Claude Agent Context

## Project Overview

**Name:** Marketbel - Unified Catalog System  
**Type:** Multi-service application for supplier price list management and product catalog

| Phase | Name | Status |
|-------|------|--------|
| 1 | Python Worker (Data Ingestion) | ✅ Complete |
| 2 | Bun API (REST API Layer) | ✅ Complete |
| 3 | React Frontend | ✅ Complete |
| 4 | Product Matching Pipeline | ✅ Complete |
| 5 | Frontend i18n | ✅ Complete |
| 6 | Admin Sync Scheduler | ✅ Complete |
| 7 | ML-Analyze Service (RAG Pipeline) | ✅ Complete |
| 8 | ML-Ingestion Integration (Courier Pattern) | ✅ Complete |
| 9 | Advanced Pricing & Categorization | 🚧 In Progress |

**Before implementation:** Use mcp context7 to collect up-to-date documentation.  
**For frontend:** Use i18n (add text to translation files in `public/locales/`).
**For frontend:** Use mcp 21st-dev/magic For design elements.

---

## Technology Stack

### Backend (Phases 1, 4, 6, 7)
- **Runtime:** Python 3.12+ (venv)
- **ORM:** SQLAlchemy 2.0+ AsyncIO
- **Queue:** arq (Redis-based)
- **Validation:** Pydantic 2.x
- **Matching:** RapidFuzz (Phase 4)

### ML-Analyze Service (Phase 7)
- **Framework:** FastAPI + uvicorn
- **RAG:** LangChain + LangChain-Ollama
- **LLM:** Ollama (nomic-embed-text for embeddings, llama3 for matching)
- **Vector DB:** pgvector (PostgreSQL extension)
- **File Parsing:** pymupdf4llm (PDF), openpyxl (Excel)
- **Database:** asyncpg (async PostgreSQL driver)

### API (Phase 2)
- **Runtime:** Bun
- **Framework:** ElysiaJS
- **ORM:** Drizzle ORM + node-postgres
- **Auth:** @elysiajs/jwt, bcrypt
- **Validation:** TypeBox

### Frontend (Phases 3, 5)
- **Framework:** React 18+ with TypeScript
- **Build:** Vite 5+
- **State:** TanStack Query v5
- **UI:** Radix UI Themes
- **Styling:** Tailwind CSS v4.1 (CSS-first, NO tailwind.config.js)
- **i18n:** react-i18next

### Infrastructure
- **Database:** PostgreSQL 16 (JSONB)
- **Cache/Queue:** Redis 7
- **Containers:** Docker Compose v2

---

## Project Structure

```
marketbel/
├── services/
│   ├── python-ingestion/    # Phases 1, 4, 6, 8, 9 - Worker (Data Courier)
│   │   ├── src/
│   │   │   ├── db/models/   # SQLAlchemy ORM
│   │   │   ├── parsers/     # Data source parsers
│   │   │   ├── services/    # Matching, ML client (Phase 8)
│   │   │   │   ├── ml_client.py      # HTTP client for ml-analyze
│   │   │   │   └── job_state.py      # Redis job state management
│   │   │   └── tasks/       # arq tasks
│   │   │       ├── download_tasks.py # File download + ML trigger (Phase 8)
│   │   │       ├── ml_polling_tasks.py # ML job status polling (Phase 8)
│   │   │       ├── cleanup_tasks.py  # Shared file cleanup (Phase 8)
│   │   │       └── retry_tasks.py    # Failed job retry (Phase 8)
│   │   └── migrations/      # Alembic
│   ├── ml-analyze/          # Phase 7 - AI Service (Intelligence)
│   │   └── src/
│   │       ├── api/         # FastAPI endpoints
│   │       ├── db/          # Repositories, models
│   │       ├── ingest/      # File parsers (PDF, Excel)
│   │       ├── rag/         # VectorService, MergerAgent
│   │       └── services/    # Business logic orchestration
│   ├── bun-api/             # Phase 2 - API
│   │   └── src/
│   │       ├── controllers/ # auth/, catalog/, admin/
│   │       ├── services/    # Business logic, job.service.ts (Phase 8)
│   │       └── db/          # Drizzle schemas
│   └── frontend/            # Phases 3, 5, 8, 9 - UI
│       └── src/
│           ├── components/  # catalog/, admin/, cart/, shared/
│           │   └── admin/
│           │       ├── JobPhaseIndicator.tsx  # Phase 8
│           │       └── SupplierStatusTable.tsx # Phase 8 enhancements
│           ├── pages/       # Route components
│           ├── hooks/       # Custom hooks
│           │   └── useRetryJob.ts  # Phase 8
│           └── lib/         # API client, utils
├── uploads/                 # Shared Docker volume for file handoff
├── specs/                   # Feature specifications
│   ├── 001-data-ingestion-infra/
│   ├── 002-api-layer/
│   ├── 003-frontend-app/
│   ├── 004-product-matching-pipeline/
│   ├── 005-frontend-i18n/
│   ├── 006-admin-sync-scheduler/
│   ├── 007-ml-analyze/
│   ├── 008-ml-ingestion-integration/
│   └── 009-advanced-pricing-categories/
└── docker-compose.yml
```

---

## Code Style & Patterns

### Python (Worker)
- Async/await for all I/O
- Type hints required
- Pydantic models for validation
- SQLAlchemy 2.0 style (no legacy Query API)
- Use `patch.object()` for mocking (never direct assignment)

### TypeScript (Bun API)
- Strict mode, no `any`
- Controllers → Services → Repositories (SOLID)
- TypeBox schemas for validation
- Feature-based structure

### React (Frontend)
- Strict mode, no `any`
- Components → Hooks → API Client
- TanStack Query for server state
- Tailwind v4.1: `@import "tailwindcss"` + `@theme` blocks
- All UI text via i18n: `t('namespace.key')`

---

## Quick Commands

```bash
# Docker
docker-compose up -d
docker-compose logs -f worker|bun-api|frontend|ml-analyze

# Python Worker
cd services/python-ingestion
source venv/bin/activate
pytest tests/ -v --cov=src
alembic upgrade head

# ML-Analyze Service
cd services/ml-analyze
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8001
pytest tests/ -v --cov=src

# Bun API
cd services/bun-api
bun install && bun --watch src/index.ts
bun test

# Frontend
cd services/frontend
bun install && bun run dev
bun run type-check
```

---

## Phase 6: Admin Sync Scheduler

### Purpose
Centralized admin panel for monitoring and controlling supplier data ingestion with automated scheduled synchronization from Master Google Sheet.

### Key Features
- **Master Sheet Parser:** Reads supplier configurations from central Google Sheet
- **Supplier Sync:** Create/update suppliers in DB based on Master Sheet
- **Cascading Parse:** Auto-enqueue parsing for all active suppliers after sync
- **Scheduled Sync:** Default 8h interval via `SYNC_INTERVAL_HOURS`
- **Admin UI:** Status dashboard, manual sync trigger, live log stream

### Key Files (Phase 6)
- `services/python-ingestion/src/parsers/master_sheet_parser.py`
- `services/python-ingestion/src/tasks/sync_tasks.py`
- `services/bun-api/src/controllers/admin/sync.controller.ts`
- `services/frontend/src/pages/admin/IngestionControlPage.tsx`

### Spec Reference
- `/specs/006-admin-sync-scheduler/spec.md`

---

## Phase 7: ML-Analyze Service

### Purpose
AI-powered service for parsing complex unstructured supplier data (PDFs with tables, Excel with merged cells) using RAG (Retrieval-Augmented Generation) pipeline with local LLM for intelligent product matching.

### Key Features
- **Complex File Parsing:** Handles PDF tables and Excel merged cells using pymupdf4llm + openpyxl
- **Vector Embeddings:** Generates 768-dim semantic embeddings with nomic-embed-text (Ollama)
- **Semantic Search:** pgvector with IVFFLAT indexing for cosine similarity search
- **LLM Matching:** llama3 (Ollama) for reasoning-based product matching with confidence scores
- **Confidence Thresholds:** >90% auto-match, 70-90% review queue, <70% reject

### API Endpoints
- `POST /analyze/file` - Trigger file analysis (returns job_id)
- `GET /analyze/status/:job_id` - Poll job progress and results
- `POST /analyze/merge` - Trigger batch product matching
- `GET /health` - Service health check (DB, Ollama, Redis)

### Key Files (Phase 7)
- `services/ml-analyze/src/api/main.py` - FastAPI application
- `services/ml-analyze/src/ingest/excel_strategy.py` - Excel parser
- `services/ml-analyze/src/ingest/pdf_strategy.py` - PDF parser
- `services/ml-analyze/src/rag/vector_service.py` - Embedding + vector search
- `services/ml-analyze/src/rag/merger_agent.py` - LLM-based matching

### Spec Reference
- `/specs/007-ml-analyze/spec.md`

---

## Phase 8: ML-Ingestion Integration (Courier Pattern)

### Purpose
Refactored ingestion pipeline where `python-ingestion` acts as a **data courier** (fetching/downloading files) and delegates all parsing intelligence to the `ml-analyze` service for superior data extraction quality.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Admin UI (React)                                   │
│  ┌──────────────┐  ┌───────────────────┐  ┌─────────────────────────────┐   │
│  │ Upload File  │  │ JobPhaseIndicator │  │ Retry Button (failed jobs)  │   │
│  └──────┬───────┘  └─────────┬─────────┘  └──────────────┬──────────────┘   │
└─────────┼───────────────────┼────────────────────────────┼──────────────────┘
          │                   │ Poll status                │
          ▼                   ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Bun API (ElysiaJS)                                 │
│  POST /admin/suppliers    GET /admin/sync/status    POST /admin/jobs/:id/retry │
└─────────┬───────────────────────────────────────────────┬──────────────────┘
          │ Enqueue task                                  │ Enqueue retry
          ▼                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Redis Queue                                     │
│  ┌────────────────┐  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │ job:{job_id}   │  │ download tasks   │  │ retry_job_task             │   │
│  │ (phase, progress)│ │ poll_ml_status   │  │ cleanup_shared_files       │   │
│  └────────────────┘  └──────────────────┘  └────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Python Worker (Data Courier)                            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ download_and_trigger_ml task                                          │   │
│  │   1. Download file (Google Sheets → XLSX, CSV, Excel)                 │   │
│  │   2. Save to /shared/uploads/{supplier_id}_{timestamp}_{filename}     │   │
│  │   3. Write metadata sidecar (.meta.json)                              │   │
│  │   4. HTTP POST → ml-analyze /analyze/file                             │   │
│  │   5. Update Redis job state: phase=downloading → analyzing            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐     │
│  │ poll_ml_status   │  │ cleanup_files    │  │ retry_job_task         │     │
│  │ (every 10s)      │  │ (every 6h, 24h   │  │ (max 3 retries)        │     │
│  │                  │  │  TTL)            │  │                        │     │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘     │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   │                 │                 │
                   ▼                 ▼                 ▼
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  Shared Volume       │  │  HTTP REST       │  │  PostgreSQL              │
│  /shared/uploads     │  │  (Internal       │  │  (Results)               │
│  (Docker volume)     │  │   Docker net)    │  │                          │
└──────────┬───────────┘  └────────┬─────────┘  └──────────────────────────┘
           │                       │                          ▲
           │ Read file             │ POST /analyze/file       │ Save items
           ▼                       ▼                          │
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ML-Analyze Service (Intelligence)                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ /analyze/file endpoint                                              │     │
│  │   1. Read file from shared volume                                   │     │
│  │   2. Parse (PDF via pymupdf4llm, Excel via openpyxl)                │     │
│  │   3. Generate embeddings (nomic-embed-text via Ollama)              │     │
│  │   4. Match products (llama3 via Ollama, pgvector similarity)        │     │
│  │   5. Save to supplier_items table                                   │     │
│  │   6. Return job status with progress                                │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
[Admin Upload] → [Bun API] → [Redis: job created] → [Worker picks up]
                                                           │
                                                           ▼
[Google Sheets API] ← authenticate ← [Worker: download_task]
         │                                    │
         │ export XLSX                        │ save file
         ▼                                    ▼
[/shared/uploads/file.xlsx]           [Redis: phase=downloading]
         │                                    │
         │                                    │ trigger ML
         ▼                                    ▼
[ml-analyze reads file] ← HTTP POST ← [Worker: ml_client]
         │                                    │
         │ parse + match                      │ poll status
         ▼                                    ▼
[PostgreSQL: supplier_items] → [Redis: phase=complete] → [Frontend polls]
```

### Key Features
- **Courier Pattern:** `python-ingestion` downloads files only; no parsing logic
- **Shared Volume:** Zero-copy file handoff via Docker volume (`/shared/uploads`)
- **Multi-Phase Status:** Downloading → Analyzing → Matching → Complete/Failed
- **ML Toggle:** Per-supplier `use_ml_processing` flag (default: true)
- **Retry Logic:** Failed jobs can be retried via Admin UI (max 3 attempts)
- **File Cleanup:** Automatic 24-hour TTL cleanup cron task

### API Endpoints (Phase 8)
- `POST /admin/jobs/:id/retry` - Retry a failed job (admin only)
- `GET /admin/sync/status` - Extended with `jobs` array and `current_phase`

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `ML_ANALYZE_URL` | `http://ml-analyze:8001` | ML service URL |
| `USE_ML_PROCESSING` | `true` | Global toggle for ML pipeline |
| `ML_POLL_INTERVAL_SECONDS` | `5` | Status polling interval |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `FILE_CLEANUP_TTL_HOURS` | `24` | File retention before cleanup |

### Key Files (Phase 8)
- `services/python-ingestion/src/services/ml_client.py` - HTTP client for ml-analyze
- `services/python-ingestion/src/services/job_state.py` - Redis job state helpers
- `services/python-ingestion/src/tasks/download_tasks.py` - Download + ML trigger
- `services/python-ingestion/src/tasks/ml_polling_tasks.py` - ML status polling
- `services/python-ingestion/src/tasks/cleanup_tasks.py` - File cleanup cron
- `services/python-ingestion/src/tasks/retry_tasks.py` - Job retry logic
- `services/bun-api/src/services/job.service.ts` - Job retry service
- `services/frontend/src/components/admin/JobPhaseIndicator.tsx` - Phase UI
- `services/frontend/src/hooks/useRetryJob.ts` - Retry mutation hook

### Spec Reference
- `/specs/008-ml-ingestion-integration/spec.md`
- `/specs/008-ml-ingestion-integration/plan.md`
- `/docs/adr/008-courier-pattern.md` - Architecture Decision Record

---

## Phase 9: Advanced Pricing & Categorization

### Purpose
Enable advanced pricing models by supporting dual pricing (retail and wholesale) with currency tracking on products. Leverages existing category hierarchy for product organization.

### Key Features
- **Dual Pricing:** Products store both `retail_price` (end-customer) and `wholesale_price` (bulk/dealer)
- **Currency Tracking:** ISO 4217 currency code per product (e.g., USD, EUR, RUB)
- **Exact Decimals:** All monetary fields use `DECIMAL(10,2)` to avoid floating-point errors
- **Category Hierarchy:** Existing adjacency list pattern (`parent_id`) supports infinite nesting
- **Non-Negative Constraints:** Database CHECK constraints prevent negative prices

### New Product Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `retail_price` | `DECIMAL(10,2)` | Yes | End-customer price |
| `wholesale_price` | `DECIMAL(10,2)` | Yes | Bulk/dealer price |
| `currency_code` | `VARCHAR(3)` | Yes | ISO 4217 currency code |

**Note:** These are **canonical product-level prices**, distinct from `min_price` which is an aggregate of supplier prices.

### API Endpoints (Phase 9)
- `GET /api/products` - Returns pricing fields in response
- `GET /api/products/{id}` - Returns pricing fields in detail
- `PATCH /api/admin/products/{id}/pricing` - Update pricing (admin only)

### Key Files (Phase 9)
- `services/python-ingestion/migrations/versions/009_add_pricing_fields.py` - Migration
- `services/python-ingestion/src/db/models/product.py` - SQLAlchemy model (updated)
- `services/python-ingestion/src/models/product_pricing.py` - Pydantic validation
- `services/bun-api/src/db/schema/schema.ts` - Drizzle schema (updated)
- `services/bun-api/src/controllers/admin/products.controller.ts` - Pricing endpoint
- `services/frontend/src/components/shared/PriceDisplay.tsx` - Price formatting
- `services/frontend/src/components/catalog/ProductCard.tsx` - List display
- `services/frontend/src/components/catalog/ProductDetail.tsx` - Detail display

### Spec Reference
- `/specs/009-advanced-pricing-categories/spec.md`
- `/specs/009-advanced-pricing-categories/plan.md`
- `/specs/009-advanced-pricing-categories/tasks.md`

---

## Database Schema (Key Tables)

| Table | Description |
|-------|-------------|
| `suppliers` | External data sources (google_sheets, csv, excel) |
| `products` | Internal catalog with dual pricing (retail/wholesale + currency) |
| `supplier_items` | Raw supplier data with JSONB characteristics |
| `product_embeddings` | Vector embeddings (768-dim) for semantic search (Phase 7) |
| `price_history` | Time-series price tracking |
| `parsing_logs` | Structured error logging |
| `users` | Authentication (roles: sales, procurement, admin) |
| `match_review_queue` | Pending matches for human review (Phase 4) |
| `categories` | Hierarchical product categories (adjacency list via `parent_id`) |

---

## Key Architectural Decisions

1. **SOLID everywhere:** Controllers handle HTTP only, Services handle logic, Repositories handle data
2. **Error isolation:** Per-row logging to `parsing_logs` - worker never crashes on bad data
3. **Type safety:** End-to-end types from DB → API → Frontend
4. **KISS:** No WebSockets (polling), no Redux, no complex abstractions
5. **Queue-based:** Python worker consumes tasks, API publishes
6. **Courier Pattern (Phase 8):** `python-ingestion` acts as data courier; `ml-analyze` handles intelligence (see [ADR-008](/docs/adr/008-courier-pattern.md))

---

## Spec References

Each phase has detailed documentation in `/specs/00X-name/`:
- `spec.md` - Feature specification
- `plan/research.md` - Technology decisions
- `plan/data-model.md` - Schema definitions
- `plan/quickstart.md` - 15-minute setup guide
- `plan/contracts/` - API contracts (JSON schemas)
