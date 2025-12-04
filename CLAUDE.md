> **For high-level architecture, roadmap, and core logic, strictly refer to: [[docs/PROJECT_SUMMARY.md]]**

# Claude Agent Context - Marketbel

## Project Structure

```
marketbel/
├── services/
│   ├── python-ingestion/    # Worker (Data Courier) - Python 3.12+, SQLAlchemy 2.0, arq
│   ├── ml-analyze/          # AI Service - FastAPI, LangChain, Ollama, pgvector
│   ├── bun-api/             # REST API - Bun, ElysiaJS, Drizzle ORM
│   └── frontend/            # React 18+, Vite, TanStack Query, Tailwind v4.1
├── uploads/                 # Shared Docker volume for file handoff
└── specs/                   # Feature specs (001-009)
```

## Tech Stack (Project-Specific)

- **Python:** SQLAlchemy 2.0 style (no legacy Query API), Pydantic 2.x, arq (Redis queue)
- **Bun API:** ElysiaJS, Drizzle ORM, TypeBox validation, @elysiajs/jwt
- **Frontend:** Tailwind CSS v4.1 (CSS-first, NO tailwind.config.js), react-i18next
- **ML:** LangChain + LangChain-Ollama, pgvector, pymupdf4llm, nomic-embed-text/llama3

## Code Conventions (STRICT)

### Python
- Async/await for all I/O
- Use `patch.object()` for mocking (never direct assignment)
- Type hints required

### TypeScript
- Strict mode, no `any`
- Controllers → Services → Repositories (layered)

### React
- Tailwind v4.1: `@import "tailwindcss"` + `@theme` blocks (NO tailwind.config.js)
- All UI text via i18n: `t('namespace.key')` (add to `public/locales/`)

- **Before implementation:** Use mcp context7 for docs

### Frontend Tools
- **UI components:** Use mcp 21st-dev/magic

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

# ML-Analyze
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

## Phase 8: Courier Pattern (Current)

**Architecture:** `python-ingestion` downloads files → shared volume (`/uploads`) → `ml-analyze` parses

**Key Files:**
- `services/python-ingestion/src/services/ml_client.py` - HTTP client for ml-analyze
- `services/python-ingestion/src/services/job_state.py` - Redis job state
- `services/python-ingestion/src/tasks/download_tasks.py` - Download + ML trigger
- `services/python-ingestion/src/tasks/ml_polling_tasks.py` - Status polling (10s)
- `services/python-ingestion/src/tasks/cleanup_tasks.py` - File cleanup (24h TTL)

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `ML_ANALYZE_URL` | `http://ml-analyze:8001` | ML service URL |
| `USE_ML_PROCESSING` | `true` | Global ML toggle |
| `ML_POLL_INTERVAL_SECONDS` | `5` | Polling interval |
| `MAX_FILE_SIZE_MB` | `50` | Upload limit |
| `FILE_CLEANUP_TTL_HOURS` | `24` | File retention |

**Job Phases:** `downloading` → `analyzing` → `matching` → `complete`/`failed`

## Phase 9: Semantic ETL (COMPLETE)

**Purpose:** LLM-based extraction replacing fragile pandas/regex parsing

**Status:** ✅ Implementation complete. See `/docs/adr/009-semantic-etl.md` for architecture details.

**Key Changes:**
- Excel → Markdown grid representation (preserves layout)
- Sliding window LLM extraction (250 rows/chunk, 40-row overlap)
- Category fuzzy matching (85% threshold, RapidFuzz)
- Within-file deduplication (hash-based, 1% price tolerance)
- Partial success handling (80-99% = "completed_with_errors")
- Category review admin UI (`/admin/categories/review`)

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SEMANTIC_ETL` | `false` | Feature flag |
| `FUZZY_MATCH_THRESHOLD` | `85` | Category matching (0-100) |
| `CHUNK_SIZE_ROWS` | `250` | Rows per chunk |
| `CHUNK_OVERLAP_ROWS` | `40` | Chunk overlap (16%) |
| `OLLAMA_MODEL_LLM` | `llama3` | LLM for extraction |
| `OLLAMA_TEMPERATURE` | `0.2` | Deterministic extraction |

**Key Files:**
- `services/ml-analyze/src/schemas/extraction.py` - ExtractedProduct Pydantic models
- `services/ml-analyze/src/services/smart_parser/service.py` - Orchestration
- `services/ml-analyze/src/services/smart_parser/markdown_converter.py` - Excel → Markdown
- `services/ml-analyze/src/services/smart_parser/langchain_extractor.py` - LLM extraction
- `services/ml-analyze/src/services/smart_parser/prompts.py` - LLM prompt templates
- `services/ml-analyze/src/services/smart_parser/sheet_selector.py` - Multi-sheet logic
- `services/ml-analyze/src/services/category_normalizer.py` - Fuzzy matching (optimized for 1K+ categories)
- `services/ml-analyze/src/services/deduplication_service.py` - Hash-based deduplication
- `services/bun-api/src/services/category.service.ts` - Category review backend
- `services/frontend/src/pages/admin/CategoryReviewPage.tsx` - Admin review UI

**New Dependencies:**
- `langchain-core==0.3.21`
- `langchain-ollama==0.2.0`
- `openpyxl==3.1.5`

**Schema Changes:**
- `categories`: Add `parent_id`, `needs_review`, `is_active`, `supplier_id`
- `parsing_logs`: Add `chunk_id`, `row_number`, `error_type`, `extraction_phase`

**Job Phases (Extended):** `downloading` → `analyzing` (sheet selection) → `extracting` (LLM) → `normalizing` (categories) → `complete`/`completed_with_errors`/`failed`

## Key Decisions

1. **Courier Pattern (Phase 8):** `python-ingestion` = data courier, `ml-analyze` = intelligence (see `/docs/adr/008-courier-pattern.md`)
2. **Error Isolation:** Per-row logging to `parsing_logs`, worker never crashes on bad data
3. **KISS:** Polling (no WebSockets), TanStack Query (no Redux)

## Spec References

Each phase: `/specs/00X-name/` with `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`
