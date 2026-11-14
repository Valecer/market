# Marketbel

A modern, principle-driven application built with strong architectural foundations.

## Project Principles

This project adheres to a strict constitutional framework based on **SOLID**, **KISS**, and **DRY** principles. See [`.specify/memory/constitution.md`](.specify/memory/constitution.md) for the complete project constitution.

### Core Principles

- **SOLID**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **KISS**: Keep It Simple, Stupid - start with simple solutions, scale when necessary
- **DRY**: Don't Repeat Yourself - single source of truth for all knowledge
- **Separation of Concerns**: Clear service boundaries with async communication
- **Strong Typing**: TypeScript strict mode, Python mypy strict mode
- **Design System Consistency**: Unified UI/UX following established patterns

## Tech Stack

### Backend

- **API Service (Phase 2)**: [Bun](https://bun.sh/) + [ElysiaJS](https://elysiajs.com/)
  - High-performance REST API for product catalog
  - Framework: ElysiaJS with TypeBox validation
  - ORM: Drizzle ORM with PostgreSQL introspection
  - Authentication: JWT with role-based access (sales, procurement, admin)
  - Documentation: Auto-generated Swagger UI at `/docs`
  - Strict TypeScript typing (`tsc --noEmit` with zero errors)

- **Data Processing Service (Phase 1)**: Python 3.12+
  - Handles data parsing and normalization (Google Sheets, CSV, Excel)
  - Libraries: Pandas, SQLAlchemy, Pydantic, arq
  - Async processing with Redis queue
  - Type-checked with mypy strict mode

### Data Layer

- **Primary Database**: PostgreSQL
  - Single source of truth for application data
  - Migrations managed per service

- **Caching & Queues**: Redis
  - Async job queues for service communication
  - Caching layer for performance

### Frontend

- **Framework**: React 18+
- **Build Tool**: Vite
- **Styling**: Tailwind CSS v4.1
  - **Important**: CSS-first configuration approach
  - Use `@import "tailwindcss";` in CSS files
  - Use `@theme` blocks for theme customization
  - Use `@tailwindcss/vite` plugin
  - **Do NOT** generate `tailwind.config.js`

### Infrastructure

- **Containerization**: Docker & Docker Compose
- **Development**: Hot reload, volume mounts
- **Production**: Multi-stage builds, health checks

## Architecture

### Service Separation

**Critical**: Services have strict separation of concerns:

1. **Bun API Service** (API/User Logic) - **Phase 2** ✅
   - HTTP endpoints for catalog, admin, authentication
   - Request validation with TypeBox schemas
   - Job enqueueing to Redis for data sync
   - Response formatting with OpenAPI documentation
   - JWT authentication with role-based access control

2. **Python Worker Service** (Data Processing) - **Phase 1** ✅
   - Queue consumption via arq
   - Data parsing (Google Sheets, CSV, Excel)
   - Normalization algorithms
   - Result persistence to PostgreSQL

3. **ML-Analyze Service** (AI Analysis) - **Phase 7** ✅
   - Complex file parsing (PDF tables, Excel merged cells)
   - Vector embeddings via Ollama (nomic-embed-text)
   - Semantic product matching with LLM reasoning (llama3)
   - pgvector for similarity search
   - Confidence-based auto-matching workflow

4. **Communication**: Services communicate **ONLY** via Redis queues
   - No direct HTTP calls between services
   - Async, decoupled architecture
   - Improves resilience and scalability

### API Endpoints (Phase 2 - Bun API)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/catalog` | None | Browse active products with filters |
| `POST /api/v1/auth/login` | None | Login and get JWT token |
| `GET /api/v1/admin/products` | JWT | List products with supplier details |
| `PATCH /api/v1/admin/products/:id/match` | JWT (procurement) | Link/unlink supplier items |
| `POST /api/v1/admin/products` | JWT (procurement) | Create new product |
| `POST /api/v1/admin/sync` | JWT (admin) | Trigger data ingestion |
| `GET /health` | None | Health check |
| `GET /docs` | None | Swagger UI documentation |

### API Endpoints (Phase 7 - ML-Analyze)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | None | Service health check (DB, Redis, Ollama) |
| `POST /analyze/file` | None | Trigger file analysis (returns job_id) |
| `GET /analyze/status/:job_id` | None | Check job progress and results |
| `POST /analyze/merge` | None | Trigger batch product matching |
| `POST /analyze/vision` | None | Vision analysis stub (501) |

### API Endpoints (Phase 11 - Pipeline Stabilization)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/admin/duplicates` | JWT | List potential duplicate products |
| `PATCH /api/v1/admin/duplicates/:id/merge` | JWT | Merge two products (keep one, archive other) |
| `PATCH /api/v1/admin/duplicates/:id/dismiss` | JWT | Dismiss duplicate as false positive |

### Phase 11: Pipeline Stabilization Features

**Problem Solved:** Eliminated duplicate products on re-import, reduced manual matching overhead, and enforced consistent catalog structure.

**Key Features:**

1. **Hash-Based Idempotency** - Re-import files without creating duplicates
   - MD5 hash of normalized row data
   - 60-80% faster re-ingestion for files with mostly unchanged rows
   - Batch lookups (1000 hashes/query) for performance

2. **Auto-Creation (<90% Confidence)** - No more manual matching queue
   - Items with <90% match confidence auto-create new products
   - Uses ML-cleaned names (not raw supplier text)
   - Internal SKU format: `AUTO-{uuid4().hex[:8]}`

3. **3-Level Category Hierarchy** - Consistent catalog structure
   - Level 1: Top Category (e.g., "Electric Transport")
   - Level 2: Sub-category (e.g., "Motorcycles")
   - Level 3: Brand/Type (e.g., "Shtenli")

4. **Duplicate Detection** - Catches auto-creation false positives
   - 85-90% name similarity threshold
   - Same category, <20% price difference
   - Admin review queue with merge/dismiss actions

5. **Variant Detection** - Groups similar products automatically
   - Products with varying attributes (voltage, capacity) become variants
   - Price ratio validation (≤2.0x) prevents incorrect grouping

### Data Flow

```
┌──────┐     HTTP      ┌──────────┐     Redis      ┌────────┐
│Client├──────────────►│Bun API   ├───────────────►│Python  │
└──────┘               │Service   │     Queue      │Worker  │
                       └────┬─────┘                └───┬────┘
                            │                          │
                            │      PostgreSQL          │
                            └──────────────────────────┘

┌──────┐     HTTP      ┌──────────┐     Ollama     ┌────────┐
│Admin ├──────────────►│ML-Analyze├───────────────►│LLM +   │
│UI    │               │Service   │     API        │Embed   │
└──────┘               └────┬─────┘                └────────┘
                            │
                ┌───────────┴───────────┐
                │     PostgreSQL        │
                │    + pgvector         │
                └───────────────────────┘
```

## Development Setup

### Prerequisites

- [Bun](https://bun.sh/) (latest)
- [Python](https://www.python.org/) 3.11+
- [Docker](https://www.docker.com/) & Docker Compose
- [PostgreSQL](https://www.postgresql.org/) 15+ (or use Docker)
- [Redis](https://redis.io/) 7+ (or use Docker)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd marketbel
```

2. **Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start services with Docker**

```bash
docker-compose up -d
```

4. **Install dependencies**

```bash
# Bun service
cd services/api
bun install

# Python service
cd ../data-processing
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

5. **Run database migrations**

```bash
# From project root
cd services/api
bun run migrate

cd ../data-processing
alembic upgrade head
```

6. **Start development servers**

```bash
# Terminal 1: Bun API
cd services/api
bun run dev

# Terminal 2: Python Worker
cd services/data-processing
python -m src.worker

# Terminal 3: Frontend (if applicable)
cd frontend
bun run dev
```

## Development Workflow

### 1. Feature Planning

Use the SpecKit system for structured development:

```bash
# Define feature specification
/speckit.specify I want to build [feature description]

# Generate task breakdown
/speckit.plan Create tasks for [feature-name]-spec.md
```

### 2. Constitutional Compliance

Every feature must:

- Align with project principles
- Include constitutional compliance statement
- Document any justified deviations
- Pass all linting and type checks

### 3. Code Quality

**TypeScript (Bun Service)**

```bash
# Type check
bun run typecheck

# Lint
bun run lint

# Tests
bun run test

# Coverage
bun run test:coverage
```

**Python (Data Processing)**

```bash
# Type check
mypy --strict src/

# Lint
ruff check .

# Format
black .

# Tests
pytest

# Coverage
pytest --cov=src --cov-report=html
```

### 4. Testing Requirements

- **Unit Tests**: ≥80% coverage for business logic
- **Integration Tests**: Service interactions, database operations
- **E2E Tests**: Critical user flows (frontend → API → processing → DB)

### 5. Commit Standards

Follow conventional commits:

```
feat: add user authentication endpoint
fix: resolve queue message serialization issue
docs: update API documentation
refactor: extract validation logic to service layer
test: add integration tests for data processing
```

## Design System

### UI Development

Before implementing UI components:

1. Query `mcp 21st-dev/magic` for design elements
2. Collect tool documentation via `mcp context7`
3. Follow Tailwind CSS v4.1 CSS-first approach

### Accessibility

- Use semantic HTML
- Include ARIA labels
- Ensure keyboard navigation
- Test with screen readers

## Algorithm Strategy (KISS Principle)

Start with **simple algorithms**, scale to **complex** when needed:

**Phase 1: Simple**
- Levenshtein distance for string matching
- Basic SQL queries for data retrieval
- Synchronous processing for small datasets

**Phase 2: Scale**
- Embedding-based matching (when dataset grows)
- Query optimization and indexing
- Async processing and batch operations

## Project Structure

```
marketbel/
├── .specify/                  # SpecKit framework
│   ├── memory/
│   │   └── constitution.md    # Project constitution
│   ├── scripts/               # SpecKit scripts
│   └── templates/             # Documentation templates
├── specs/                     # Feature specifications
│   ├── 001-data-ingestion-infra/  # Phase 1 spec (Python)
│   └── 002-api-layer/             # Phase 2 spec (Bun API)
├── services/
│   ├── bun-api/               # Bun API service (Phase 2) ✅
│   │   ├── src/               # TypeScript source
│   │   ├── tests/             # Bun test suite
│   │   ├── migrations/        # SQL migrations (users table)
│   │   ├── scripts/           # Utility scripts
│   │   └── Dockerfile         # Production container
│   ├── python-ingestion/      # Python worker (Phase 1) ✅
│   │   ├── src/               # Python source
│   │   ├── tests/             # pytest suite
│   │   ├── migrations/        # Alembic migrations
│   │   └── Dockerfile         # Production container
│   ├── frontend/              # React frontend (Phase 3) ✅
│   │   ├── src/               # React/TypeScript source
│   │   ├── public/            # Static assets + i18n
│   │   └── Dockerfile         # Production container
│   └── ml-analyze/            # ML service (Phase 7) ✅
│       ├── src/               # FastAPI + RAG pipeline
│       │   ├── api/           # FastAPI routes
│       │   ├── ingest/        # PDF/Excel parsers
│       │   ├── rag/           # Vector + LLM matching
│       │   └── services/      # Business logic
│       ├── tests/             # pytest suite
│       └── Dockerfile         # Production container
├── docs/
│   ├── adr/                   # Architecture Decision Records
│   └── *.md                   # Documentation
├── credentials/               # Service credentials (gitignored)
├── docker-compose.yml         # Service orchestration
└── README.md
```

## Configuration

### Environment Variables

**Bun Service**
```bash
BUN_PORT=3000
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel
REDIS_URL=redis://localhost:6379
```

**Python Service (python-ingestion)**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel
REDIS_URL=redis://localhost:6379
QUEUE_NAME=data-processing-queue
WORKERS=4

# Phase 11: Idempotent Re-Ingestion
HASH_CACHE_ENABLED=true          # Enable hash-based deduplication
HASH_ALGORITHM=md5               # Hash algorithm (md5, sha256)
```

**ML-Analyze Service**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/marketbel
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
ENVIRONMENT=development

# Ollama Configuration
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL_LLM=llama3
OLLAMA_MODEL_EMBED=nomic-embed-text

# Phase 11: Auto-Creation & Detection
AUTO_CREATE_THRESHOLD=90         # Confidence threshold (0-100)
VARIANT_DETECTION_ENABLED=true   # Enable variant detection
DUPLICATE_DETECTION_ENABLED=true # Enable duplicate detection
DUPLICATE_SIMILARITY_THRESHOLD=85 # Min similarity for duplicates (0-100)
DUPLICATE_PRICE_DIFF_THRESHOLD=20 # Max price diff % for duplicates (0-100)
```

### Phase 11 Metrics & Monitoring

**Key Metrics to Monitor:**
| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| `hash_hit_rate` | ≥70% | <50% |
| `auto_creation_rate` | 50-90% | >95% |
| `duplicate_queue_size` | <500 pending | >500 |
| `reingestion_time_reduction` | 60-80% | <40% |

## Troubleshooting

### Common Issues

**Issue**: TypeScript errors about `any` types
**Solution**: Enable strict mode, add explicit type annotations

**Issue**: Python worker not consuming queue messages
**Solution**: Verify Redis connection, check queue name consistency

**Issue**: Tailwind styles not applying
**Solution**: Ensure `@import "tailwindcss";` in CSS, use `@theme` blocks, verify Vite plugin

## Contributing

1. Read the [constitution](.specify/memory/constitution.md)
2. Follow the SpecKit workflow
3. Ensure constitutional compliance
4. Write tests (≥80% coverage)
5. Pass all linters and type checks
6. Submit PR with compliance statement

## License

[License Type] - See LICENSE file for details

## Support

For questions about:
- **Principles & Governance**: See `.specify/memory/constitution.md`
- **Feature Development**: Use `/speckit.specify` command
- **Technical Issues**: [Create an issue](link-to-issues)

---

Built with principles, powered by purpose. 🎯

