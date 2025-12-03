# Claude Agent Context

## Project Overview

**Marketbel** - Multi-service supplier price list management and catalog system

**Current Phase:** 10 (ML Parsing Service Upgrade) - 🚧 In Progress

**Completed:** Phases 1-9 (Data Ingestion, API, Frontend, Matching, i18n, Scheduler, ML-Analyze, Courier Integration, Pricing)

**Before implementation:** Use MCP context7 for up-to-date docs | Use i18n for frontend text | Use MCP 21st-dev for UI components

---

## Technology Stack

**Python Backend** (Worker + ML-Analyze): Python 3.12+ | SQLAlchemy 2.0 AsyncIO | arq (Redis) | Pydantic 2.x | FastAPI | LangChain + Ollama | pgvector

**Bun API**: Bun | ElysiaJS | Drizzle ORM | @elysiajs/jwt

**Frontend**: React 18 + TS | Vite 5 | TanStack Query v5 | Radix UI | Tailwind v4.1 (CSS-first) | react-i18next

**Infrastructure**: PostgreSQL 16 | Redis 7 | Docker Compose v2

---

## Project Structure

```
marketbel/
├── services/
│   ├── python-ingestion/  # Phases 1,4,6,8,9 - Data Courier
│   │   ├── src/{db,parsers,services,tasks}/
│   │   └── migrations/
│   ├── ml-analyze/        # Phases 7,10 - AI/RAG Service
│   │   └── src/{api,db,ingest,rag,services,utils}/
│   ├── bun-api/          # Phase 2 - REST API
│   │   └── src/{controllers,services,db}/
│   └── frontend/         # Phases 3,5,8,9 - React UI
│       └── src/{components,pages,hooks,lib}/
├── uploads/              # Shared Docker volume
├── specs/                # Feature specifications (001-010)
│   └── 0XX-name/{spec,plan,tasks,research,data-model,contracts}.md
└── docker-compose.yml
```

---

## Code Style

**Python**: Async/await | Type hints required | Pydantic validation | SQLAlchemy 2.0 | `patch.object()` for mocking

**TypeScript**: Strict mode, no `any` | SOLID pattern | TypeBox validation

**React**: Strict mode | TanStack Query | Tailwind v4.1 (`@import "tailwindcss"` + `@theme`) | i18n for all text

---

## Quick Commands

```bash
# Docker
docker-compose up -d
docker-compose logs -f worker|bun-api|frontend|ml-analyze

# Python Worker
cd services/python-ingestion && source venv/bin/activate
pytest tests/ -v --cov=src
alembic upgrade head

# ML-Analyze
cd services/ml-analyze && source venv/bin/activate
uvicorn src.api.main:app --reload --port 8001

# Bun API
cd services/bun-api && bun --watch src/index.ts

# Frontend
cd services/frontend && bun run dev
```

---

## Architecture Patterns

1. **SOLID**: Controllers (HTTP) → Services (logic) → Repositories (data)
2. **Courier Pattern**: python-ingestion downloads files → ml-analyze parses/matches (see `/docs/adr/008-courier-pattern.md`)
3. **Two-Stage Parsing**: LLM Structure analysis → Data extraction (40% token reduction)
4. **Error Isolation**: Per-row logging to `parsing_logs` - never crash on bad data
5. **Queue-Based**: Python worker consumes arq tasks, API publishes to Redis

---

## Current Phase (10): ML Parsing Service Upgrade

**Goal**: Enhance ml-analyze with two-stage LLM parsing, file path API, composite name parsing, currency extraction

**Key Improvements**:
- Two-stage parsing: Stage A (structure) → Stage B (data extraction)
- Accept `file_path` parameter (zero-copy from shared volume)
- Split composite names ("Category | Name | Description")
- Extract currency symbols (₽, $, €) → ISO 4217 codes
- Track parsing metrics (tokens, timing, field extraction rates)

**API**: `POST /analyze/file` - New params: `file_path`, `default_currency`, `composite_delimiter`

**Key Files**:
- `services/ml-analyze/src/utils/{file_reader,name_parser,price_parser}.py`
- `services/ml-analyze/src/services/two_stage_parser.py`
- `services/ml-analyze/src/rag/prompt_templates.py`
- `services/ml-analyze/src/schemas/domain.py`

**Spec**: `/specs/010-ml-parsing-upgrade/{spec,plan,tasks,research,data-model}.md`

**ENV**: `STRUCTURE_CONFIDENCE_THRESHOLD=0.7` | `STRUCTURE_SAMPLE_ROWS=20`

---

## Database Schema (Key Tables)

`suppliers` | `products` (dual pricing + currency) | `supplier_items` | `product_embeddings` (768-dim vectors) | `price_history` | `parsing_logs` | `users` | `match_review_queue` | `categories`

---

## Phase Quick Reference

All phases have detailed documentation in `/specs/00X-name/`:

**Phase 1-5**: Data Ingestion | API Layer | Frontend | Matching | i18n
**Phase 6**: Admin Sync Scheduler - Master Sheet parser, scheduled sync (8h interval)
**Phase 7**: ML-Analyze Service - RAG pipeline, Ollama LLM, pgvector, 768-dim embeddings
**Phase 8**: Courier Integration - python-ingestion (courier) + ml-analyze (intelligence), shared volume handoff
**Phase 9**: Advanced Pricing - Dual pricing (retail/wholesale), currency tracking (ISO 4217)
**Phase 10**: ML Parsing Upgrade - Two-stage parsing, composite names, currency extraction (current)

**Phase 8 ENV**: `ML_ANALYZE_URL=http://ml-analyze:8001` | `USE_ML_PROCESSING=true` | `ML_POLL_INTERVAL_SECONDS=5` | `MAX_FILE_SIZE_MB=50` | `FILE_CLEANUP_TTL_HOURS=24`

**Spec Structure**:
- `spec.md` - Requirements
- `plan.md` - Implementation plan
- `tasks.md` - Task checklist
- `research.md` - Technology decisions
- `data-model.md` - Schema definitions
- `contracts/*.{yaml,json}` - API contracts

---

## Key Phase Files (Quick Lookup)

**Phase 6**: `parsers/master_sheet_parser.py` | `tasks/sync_tasks.py` | `admin/sync.controller.ts` | `IngestionControlPage.tsx`

**Phase 7**: `api/main.py` | `ingest/{excel,pdf}_strategy.py` | `rag/{vector_service,merger_agent}.py`

**Phase 8**: `services/{ml_client,job_state}.py` | `tasks/{download,ml_polling,cleanup,retry}_tasks.py` | `JobPhaseIndicator.tsx` | `useRetryJob.ts`

**Phase 9**: `migrations/009_add_pricing_fields.py` | `models/product.py` | `admin/products.controller.ts` | `PriceDisplay.tsx`

**Phase 10**: `utils/{file_reader,name_parser,price_parser}.py` | `services/two_stage_parser.py` | `rag/prompt_templates.py` | `schemas/domain.py`
