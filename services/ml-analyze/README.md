# ML-Analyze Service

AI-powered product analysis and matching service for Marketbel.

## Overview

The ml-analyze service uses RAG (Retrieval-Augmented Generation) pipeline to:

1. **Parse Complex Files**: Extract data from PDFs with tables and Excel files with merged cells
2. **Generate Embeddings**: Create vector representations using local Ollama models
3. **Semantic Matching**: Use LLM reasoning to match supplier items to existing products

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16 with pgvector extension
- Redis 7
- Ollama with `nomic-embed-text` and `llama3` models

### Installation

```bash
# Navigate to service directory
cd services/ml-analyze

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Edit .env with your database credentials
```

### Install Ollama Models

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull nomic-embed-text
ollama pull llama3

# Verify models are available
ollama list
```

### Run Database Migrations

```bash
# From python-ingestion directory (shared migrations)
cd ../python-ingestion
source venv/bin/activate
alembic upgrade head
```

### Start the Service

```bash
# Development mode (with auto-reload)
uvicorn src.api.main:app --reload --port 8001

# Production mode
uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

### Verify Installation

```bash
# Check health endpoint
curl http://localhost:8001/health

# View API documentation
open http://localhost:8001/docs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| GET | `/` | API information |
| POST | `/analyze/file` | Trigger file analysis (TBD) |
| GET | `/analyze/status/:job_id` | Check job status (TBD) |

## Docker Deployment

```bash
# Build and run with Docker Compose (from project root)
docker-compose up -d ml-analyze

# View logs
docker-compose logs -f ml-analyze
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Admin UI      │────▶│   Bun API       │────▶│  ml-analyze     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────────┐
                              ▼                         ▼                         ▼
                     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
                     │   PostgreSQL    │     │     Redis       │     │     Ollama      │
                     │   + pgvector    │     │   (Job Queue)   │     │   (LLM + Embed) │
                     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Development

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=html

# Unit tests only
pytest tests/unit/ -v
```

### Type Checking

```bash
mypy src/ --strict
```

### Linting

```bash
ruff check src/
ruff format src/
```

## Configuration

See `.env.example` for all available configuration options.

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `EMBEDDING_DIMENSIONS` | `768` | Vector dimension (nomic-embed-text) |
| `MATCH_CONFIDENCE_AUTO_THRESHOLD` | `0.9` | Auto-match confidence |

## Related Documentation

- [Phase 7 Specification](../../specs/007-ml-analyze/spec.md)
- [Implementation Plan](../../specs/007-ml-analyze/plan.md)
- [Research Notes](../../specs/007-ml-analyze/plan/research.md)

## License

MIT

