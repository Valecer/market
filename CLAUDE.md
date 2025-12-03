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
│   ├── python-ingestion/    # Phases 1, 4, 6 - Worker
│   │   ├── src/
│   │   │   ├── db/models/   # SQLAlchemy ORM
│   │   │   ├── parsers/     # Data source parsers
│   │   │   ├── services/    # Matching, extraction (Phase 4)
│   │   │   └── tasks/       # arq tasks
│   │   └── migrations/      # Alembic
│   ├── ml-analyze/          # Phase 7 - AI Service
│   │   └── src/
│   │       ├── api/         # FastAPI endpoints
│   │       ├── db/          # Repositories, models
│   │       ├── ingest/      # File parsers (PDF, Excel)
│   │       ├── rag/         # VectorService, MergerAgent
│   │       └── services/    # Business logic orchestration
│   ├── bun-api/             # Phase 2 - API
│   │   └── src/
│   │       ├── controllers/ # auth/, catalog/, admin/
│   │       ├── services/    # Business logic
│   │       └── db/          # Drizzle schemas
│   └── frontend/            # Phases 3, 5 - UI
│       └── src/
│           ├── components/  # catalog/, admin/, cart/, shared/
│           ├── pages/       # Route components
│           ├── hooks/       # Custom hooks
│           └── lib/         # API client, utils
├── specs/                   # Feature specifications
│   ├── 001-data-ingestion-infra/
│   ├── 002-api-layer/
│   ├── 003-frontend-app/
│   ├── 004-product-matching-pipeline/
│   ├── 005-frontend-i18n/
│   ├── 006-admin-sync-scheduler/
│   └── 007-ml-analyze/
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

## Phase 6: Admin Sync Scheduler (Current)

### Purpose
Centralized admin panel for monitoring and controlling supplier data ingestion with automated scheduled synchronization from Master Google Sheet.

### Key Features
- **Master Sheet Parser:** Reads supplier configurations from central Google Sheet
- **Supplier Sync:** Create/update suppliers in DB based on Master Sheet
- **Cascading Parse:** Auto-enqueue parsing for all active suppliers after sync
- **Scheduled Sync:** Default 8h interval via `SYNC_INTERVAL_HOURS`
- **Admin UI:** Status dashboard, manual sync trigger, live log stream

### New API Endpoints
- `POST /admin/sync/trigger` - Manual sync trigger (admin only)
- `GET /admin/sync/status` - Current sync state + progress + logs

### Key Files (Phase 6)
- `services/python-ingestion/src/parsers/master_sheet_parser.py`
- `services/python-ingestion/src/tasks/sync_tasks.py`
- `services/bun-api/src/controllers/admin/sync.controller.ts`
- `services/frontend/src/pages/admin/IngestionControlPage.tsx`

### Spec Reference
- `/specs/006-admin-sync-scheduler/spec.md`
- `/specs/006-admin-sync-scheduler/plan/`

---

## Phase 7: ML-Analyze Service (Planned)

### Purpose
AI-powered service for parsing complex unstructured supplier data (PDFs with tables, Excel with merged cells) using RAG (Retrieval-Augmented Generation) pipeline with local LLM for intelligent product matching.

### Key Features
- **Complex File Parsing:** Handles PDF tables and Excel merged cells using pymupdf4llm + openpyxl
- **Vector Embeddings:** Generates 768-dim semantic embeddings with nomic-embed-text (Ollama)
- **Semantic Search:** pgvector with IVFFLAT indexing for cosine similarity search
- **LLM Matching:** llama3 (Ollama) for reasoning-based product matching with confidence scores
- **Confidence Thresholds:** >90% auto-match, 70-90% review queue, <70% reject
- **Background Jobs:** arq-based async processing with job status tracking

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
- `/specs/007-ml-analyze/plan/`
- `/specs/007-ml-analyze/plan/quickstart.md` - 15-minute setup guide

---

## Database Schema (Key Tables)

| Table | Description |
|-------|-------------|
| `suppliers` | External data sources (google_sheets, csv, excel) |
| `products` | Internal catalog (status: draft/active/archived) |
| `supplier_items` | Raw supplier data with JSONB characteristics |
| `product_embeddings` | Vector embeddings (768-dim) for semantic search (Phase 7) |
| `price_history` | Time-series price tracking |
| `parsing_logs` | Structured error logging |
| `users` | Authentication (roles: sales, procurement, admin) |
| `match_review_queue` | Pending matches for human review (Phase 4) |

---

## Key Architectural Decisions

1. **SOLID everywhere:** Controllers handle HTTP only, Services handle logic, Repositories handle data
2. **Error isolation:** Per-row logging to `parsing_logs` - worker never crashes on bad data
3. **Type safety:** End-to-end types from DB → API → Frontend
4. **KISS:** No WebSockets (polling), no Redux, no complex abstractions
5. **Queue-based:** Python worker consumes tasks, API publishes

---

## Spec References

Each phase has detailed documentation in `/specs/00X-name/`:
- `spec.md` - Feature specification
- `plan/research.md` - Technology decisions
- `plan/data-model.md` - Schema definitions
- `plan/quickstart.md` - 15-minute setup guide
- `plan/contracts/` - API contracts (JSON schemas)
