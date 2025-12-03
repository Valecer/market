# ML-Analyze Service Deployment Guide

## Overview

This document provides deployment instructions for the ML-Analyze service in various environments.

## Prerequisites

### Infrastructure Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| PostgreSQL | 15+ with pgvector | 16+ with pgvector |
| Redis | 7.0+ | 7.2+ |
| Ollama | Latest | Latest with GPU |
| Memory | 8GB | 16GB+ |
| CPU | 2 cores | 4+ cores |
| Disk | 20GB | 50GB+ SSD |

### Required Models

Ensure Ollama has the following models:

```bash
ollama pull nomic-embed-text
ollama pull llama3
```

Verify:

```bash
ollama list
# Should show:
# nomic-embed-text:latest
# llama3:latest
```

## Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database

# Redis
REDIS_HOST=redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password
REDIS_DB=0

# Ollama
OLLAMA_BASE_URL=http://ollama-host:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=llama3

# Service
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8001
ENVIRONMENT=production
LOG_LEVEL=INFO

# Matching thresholds
MATCH_CONFIDENCE_AUTO_THRESHOLD=0.9
MATCH_CONFIDENCE_REVIEW_THRESHOLD=0.7
EMBEDDING_DIMENSIONS=768
```

### Optional Environment Variables

```bash
# Database pool
DB_POOL_MIN=2
DB_POOL_MAX=10

# Job processing
MAX_WORKERS=5
JOB_TIMEOUT=600
MAX_RETRIES=3

# File handling
UPLOADS_DIR=/shared/uploads
MAX_FILE_SIZE_MB=50

# Vector index
VECTOR_INDEX_LISTS=100
```

## Deployment Methods

### 1. Docker Compose (Recommended)

```bash
# From project root
docker-compose up -d ml-analyze

# Verify health
curl http://localhost:8001/health

# View logs
docker-compose logs -f ml-analyze
```

### 2. Kubernetes (Production)

Example deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-analyze
  labels:
    app: ml-analyze
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ml-analyze
  template:
    metadata:
      labels:
        app: ml-analyze
    spec:
      containers:
        - name: ml-analyze
          image: marketbel/ml-analyze:latest
          ports:
            - containerPort: 8001
          resources:
            requests:
              memory: "2Gi"
              cpu: "500m"
            limits:
              memory: "8Gi"
              cpu: "2"
          envFrom:
            - configMapRef:
                name: ml-analyze-config
            - secretRef:
                name: ml-analyze-secrets
          livenessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: ml-analyze
spec:
  selector:
    app: ml-analyze
  ports:
    - port: 8001
      targetPort: 8001
  type: ClusterIP
```

### 3. Manual Deployment

```bash
# Navigate to service directory
cd services/ml-analyze

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (from python-ingestion)
cd ../python-ingestion
source venv/bin/activate
alembic upgrade head

# Start service
cd ../ml-analyze
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --workers 4
```

## Database Migrations

The ML-Analyze service uses shared migrations from `python-ingestion`:

```bash
cd services/python-ingestion
source venv/bin/activate
alembic upgrade head
```

Required migrations for Phase 7:
- `007_enable_pgvector.py` - Enable pgvector extension
- `008_create_product_embeddings.py` - Create embeddings table

## Health Checks

### Endpoint

```bash
curl http://localhost:8001/health
```

### Expected Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "ml-analyze",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 1.23
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 0.45
    },
    "ollama": {
      "status": "healthy",
      "url": "http://localhost:11434"
    }
  }
}
```

### Degraded State

Service continues operating with degraded dependencies:

```json
{
  "status": "degraded",
  "checks": {
    "ollama": {
      "status": "unhealthy",
      "error": "Connection refused"
    }
  }
}
```

## Scaling Considerations

### Horizontal Scaling

1. **Stateless Design**: The API layer is stateless and can be horizontally scaled
2. **Load Balancing**: Use round-robin or least-connections for API instances
3. **Redis**: Ensure Redis connection pool is shared across instances
4. **Database**: Consider read replicas for search-heavy workloads

### Vertical Scaling

1. **Memory**: Increase for larger embedding batches
2. **CPU**: More cores improve concurrent request handling
3. **GPU**: Ollama benefits significantly from GPU acceleration

### Performance Tuning

```bash
# Database pool sizing
DB_POOL_MAX = 2 * number_of_workers + 2

# Worker count
MAX_WORKERS = (2 * CPU_CORES) + 1

# Vector index optimization (after 100k+ embeddings)
VECTOR_INDEX_LISTS = sqrt(total_rows)
```

## Monitoring

### Key Metrics

| Metric | Warning | Critical |
|--------|---------|----------|
| Response Time (p95) | >500ms | >2s |
| Error Rate | >1% | >5% |
| Memory Usage | >70% | >90% |
| CPU Usage | >70% | >90% |
| Embedding Latency | >200ms | >1s |
| LLM Latency | >10s | >30s |

### Logging

Structured JSON logs are written to stdout:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/analyze/file",
  "status_code": 202,
  "duration_ms": 45.32
}
```

## Security

### Production Checklist

- [ ] Use HTTPS/TLS termination at load balancer
- [ ] Set `ENVIRONMENT=production` to disable docs
- [ ] Configure specific CORS origins (not `*`)
- [ ] Use strong Redis password
- [ ] Secure database credentials
- [ ] Enable network isolation between services
- [ ] Rate limit API endpoints
- [ ] Validate file uploads

### Network Security

```yaml
# Example: Restrict Ollama to internal network only
OLLAMA_BASE_URL=http://ollama.internal:11434
```

## Troubleshooting

### Common Issues

1. **"Cannot connect to Ollama"**
   - Verify Ollama is running: `curl http://localhost:11434/api/tags`
   - Check OLLAMA_BASE_URL environment variable
   - For Docker: use `http://host.docker.internal:11434`

2. **"pgvector extension not found"**
   - Run migration: `alembic upgrade head`
   - Verify: `SELECT extname FROM pg_extension WHERE extname = 'vector';`

3. **"Connection pool exhausted"**
   - Increase `DB_POOL_MAX`
   - Check for connection leaks
   - Monitor active connections

4. **"Embedding dimension mismatch"**
   - Ensure `EMBEDDING_DIMENSIONS=768` for nomic-embed-text
   - Check model consistency across environments

### Debug Mode

```bash
LOG_LEVEL=DEBUG uvicorn src.api.main:app --reload
```

## Support

For issues:
1. Check logs: `docker-compose logs -f ml-analyze`
2. Review health endpoint: `curl localhost:8001/health`
3. Consult [ROLLBACK.md](./ROLLBACK.md) for recovery procedures

