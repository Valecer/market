# Marketbel API Service

High-performance REST API built with **Bun** and **ElysiaJS** for unified product catalog management.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- **Bun v1.0+** installed ([install guide](https://bun.sh/docs/installation))
- **PostgreSQL 16+** running (or via Docker)
- **Redis 7+** running (or via Docker)
- Phase 1 database schema deployed (Python ingestion service)

### Setup Steps

```bash
# 1. Install dependencies
bun install

# 2. Configure environment (copy and edit)
cp .env.example .env

# 3. Run database migration (users table)
psql $DATABASE_URL -f migrations/001_create_users.sql

# 4. Seed default users (optional, for testing)
bun run scripts/seed-users.ts

# 5. Introspect Phase 1 database schema
bun run drizzle-kit introspect

# 6. Start the API server
bun --watch src/index.ts
```

### Verify Installation

```bash
# Health check (should return 200)
curl http://localhost:3000/health

# Root endpoint
curl http://localhost:3000/

# API Documentation
open http://localhost:3000/docs
```

---

## Architecture

### Layer Architecture (SOLID)

```
┌─────────────────────────────────────────────────┐
│              Controllers (HTTP Layer)            │
│  - Handles HTTP requests, validation, response   │
│  - No business logic                            │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│            Services (Business Logic)             │
│  - Pure business logic                          │
│  - Stateless, testable                          │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│         Repositories (Data Access)               │
│  - Database queries via Drizzle ORM             │
│  - Interface-based for testability              │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              Database (PostgreSQL)               │
│  - Phase 1 tables: read-only                    │
│  - Phase 2 tables: managed (users)              │
└─────────────────────────────────────────────────┘
```

### Project Structure

```
src/
├── index.ts              # Entry point with middleware chain
├── db/
│   ├── client.ts         # Drizzle connection & pool monitoring
│   ├── schema/           # Drizzle schemas (introspected + manual)
│   └── repositories/     # Repository pattern implementations
├── controllers/          # Feature-based HTTP controllers
│   ├── auth/             # Login endpoint
│   ├── catalog/          # Public catalog
│   └── admin/            # Admin operations
├── services/             # Business logic layer
├── types/                # TypeBox schemas & TypeScript types
├── middleware/           # JWT auth, error handling, logging, security
└── utils/                # Helper functions
```

### Database Strategy

| Table | Owner | API Access |
|-------|-------|------------|
| products | Phase 1 (Python/Alembic) | READ |
| supplier_items | Phase 1 | READ + UPDATE (product_id) |
| suppliers | Phase 1 | READ |
| categories | Phase 1 | READ |
| users | Phase 2 (SQL migration) | READ + WRITE |

---

## API Endpoints

### Public Endpoints (No Auth)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root endpoint with links |
| GET | `/health` | Health check with service status |
| GET | `/ready` | Kubernetes readiness probe |
| GET | `/live` | Kubernetes liveness probe |
| GET | `/docs` | Swagger UI documentation |
| GET | `/docs/json` | OpenAPI specification |
| GET | `/api/v1/catalog` | Browse active products |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Login and get JWT token |

### Admin Endpoints (JWT Required)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/api/v1/admin/products` | any | List products with supplier details |
| PATCH | `/api/v1/admin/products/:id/match` | procurement, admin | Link/unlink supplier items |
| POST | `/api/v1/admin/products` | procurement, admin | Create new product |
| POST | `/api/v1/admin/sync` | admin | Trigger data sync |

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/marketbel` |
| `REDIS_URL` | Redis connection string | `redis://:password@localhost:6379` |
| `JWT_SECRET` | Secret for JWT signing (min 32 chars) | `your-secure-secret-key-min-32-characters` |

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BUN_PORT` | `3000` | Port to listen on |
| `NODE_ENV` | `development` | Environment (development/production) |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `LOG_LEVEL` | `info` | Logging level (debug/info/warn/error) |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | ⚠️ Required | Secret key for JWT signing |
| `JWT_ISSUER` | `marketbel-api` | JWT issuer claim |
| `JWT_EXPIRATION_HOURS` | `24` | Token expiration in hours |

### Database Pool

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_MIN` | `5` | Minimum pool connections |
| `DB_POOL_MAX` | `20` | Maximum pool connections |
| `DB_IDLE_TIMEOUT` | `30000` | Idle connection timeout (ms) |
| `DB_CONNECTION_TIMEOUT` | `2000` | Connection timeout (ms) |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `SYNC_RATE_LIMIT_PER_MINUTE` | `10` | Max sync requests per minute per user |

### Example `.env` File

```bash
# Server
BUN_PORT=3000
NODE_ENV=development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Database
DATABASE_URL=postgresql://marketbel_user:dev_password@localhost:5432/marketbel
DB_POOL_MIN=5
DB_POOL_MAX=20

# Redis
REDIS_URL=redis://:dev_redis_password@localhost:6379

# JWT Authentication
JWT_SECRET=your-super-secure-secret-key-minimum-32-characters-long
JWT_ISSUER=marketbel-api
JWT_EXPIRATION_HOURS=24

# Logging
LOG_LEVEL=info
```

---

## Development

### Running the Server

```bash
# Development mode with hot reload
bun --watch src/index.ts

# Or using npm script
bun run dev

# Production mode
bun run start
```

### Database Operations

```bash
# Introspect Phase 1 schema
bun run db:introspect

# Run users table migration
bun run db:migrate

# Seed test users
bun run db:seed
```

### Code Quality

```bash
# Type checking
bun run tsc --noEmit

# Run tests
bun test

# Watch tests
bun test --watch

# Coverage report
bun test --coverage
```

### Performance Benchmarking

```bash
# Catalog endpoint benchmark (target: p95 < 500ms)
bun run scripts/benchmark-catalog.ts

# Admin endpoints benchmark (target: p95 < 1000ms)
bun run scripts/benchmark-admin.ts --username=admin --password=admin123
```

---

## Testing

### Test Structure

```
tests/
├── fixtures.ts           # Test data and helpers
├── helpers.ts            # Test app factory functions
├── auth.test.ts          # Authentication tests
├── catalog.test.ts       # Catalog endpoint tests
└── admin/
    ├── products.test.ts  # Admin products tests
    ├── matching.test.ts  # Product matching tests
    ├── creation.test.ts  # Product creation tests
    └── sync.test.ts      # Sync trigger tests
```

### Running Tests

```bash
# Run all tests
bun test

# Run specific test file
bun test tests/auth.test.ts

# Run with coverage
bun test --coverage

# Watch mode
bun test --watch
```

### Coverage Targets

- **Business logic (services):** ≥80%
- **Repositories:** ≥80%
- **Controllers:** ≥70%

---

## Deployment

### Docker Deployment

#### Build and Run

```bash
# Build the image
docker build -t marketbel-api ./services/bun-api

# Run container
docker run -p 3000:3000 \
  -e DATABASE_URL="postgresql://..." \
  -e REDIS_URL="redis://..." \
  -e JWT_SECRET="your-secret" \
  marketbel-api
```

#### Docker Compose (Recommended)

```bash
# Start all services (postgres, redis, worker, api)
docker-compose up -d

# View API logs
docker-compose logs -f bun-api

# Rebuild after changes
docker-compose build bun-api
docker-compose up -d bun-api
```

### Pre-Deployment Checklist

1. **Database Migration:**
   ```bash
   psql $DATABASE_URL -f migrations/001_create_users.sql
   ```

2. **Seed Users (if needed):**
   ```bash
   bun run scripts/seed-users.ts
   ```

3. **Environment Variables:**
   - Set `NODE_ENV=production`
   - Set secure `JWT_SECRET` (min 32 characters, random)
   - Configure `ALLOWED_ORIGINS` for production domains
   - Review `DB_POOL_MAX` based on expected load

4. **Health Check:**
   ```bash
   curl https://api.example.com/health
   ```

### Production Considerations

#### Security

- **JWT Secret:** Use strong, randomly generated secret (≥32 characters)
- **CORS:** Restrict `ALLOWED_ORIGINS` to production domains
- **HTTPS:** Use behind a reverse proxy (nginx, cloudflare) with TLS
- **Rate Limiting:** Adjust `SYNC_RATE_LIMIT_PER_MINUTE` as needed

#### Performance

- **Connection Pooling:** Tune `DB_POOL_MAX` based on:
  - Available PostgreSQL connections
  - Number of API instances
  - Expected concurrent users
- **Monitoring:** Check `/health` endpoint for pool utilization
- **Targets:**
  - Catalog: p95 < 500ms
  - Admin: p95 < 1000ms

#### Scaling

- **Horizontal:** Stateless design allows multiple instances
- **Load Balancer:** Use round-robin with health checks
- **Redis:** Single Redis instance handles queue publishing
- **Database:** Connection pool per instance (adjust max accordingly)

### Kubernetes Deployment

Example deployment configuration:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: marketbel-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: marketbel-api
  template:
    spec:
      containers:
        - name: api
          image: marketbel-api:latest
          ports:
            - containerPort: 3000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: marketbel-secrets
                  key: database-url
          readinessProbe:
            httpGet:
              path: /ready
              port: 3000
            initialDelaySeconds: 5
          livenessProbe:
            httpGet:
              path: /live
              port: 3000
            initialDelaySeconds: 10
```

---

## Troubleshooting

### Common Issues

#### Database Connection Failed

```
Error: Connection refused to localhost:5432
```

**Solution:**
- Check PostgreSQL is running: `docker-compose ps postgres`
- Verify `DATABASE_URL` is correct
- Check firewall/network access

#### Redis Connection Failed

```
Error: Redis connection refused
```

**Solution:**
- Check Redis is running: `docker-compose ps redis`
- Verify `REDIS_URL` includes password if set
- Check Redis authentication

#### JWT Token Invalid

```
Error: 401 Unauthorized - Invalid token
```

**Solution:**
- Check `JWT_SECRET` matches between token generation and verification
- Verify token hasn't expired
- Ensure `Authorization: Bearer <token>` header format

#### Database Pool Exhaustion

```
Warning: Database pool utilization high (>80%)
```

**Solution:**
- Increase `DB_POOL_MAX`
- Check for connection leaks (queries not completing)
- Scale horizontally (more instances with smaller pools)

### Debug Mode

Enable verbose logging:

```bash
LOG_LEVEL=debug bun run src/index.ts
```

### Support

- **Documentation:** `/docs` endpoint for API reference
- **Quickstart Guide:** `/specs/002-api-layer/plan/quickstart.md`
- **Architecture:** `/specs/002-api-layer/plan/research.md`
- **Contracts:** `/specs/002-api-layer/plan/contracts/`

---

## References

- [ElysiaJS Documentation](https://elysiajs.com/)
- [Drizzle ORM](https://orm.drizzle.team/)
- [Bun Documentation](https://bun.sh/docs)
- [TypeBox](https://github.com/sinclairzx81/typebox)
- Phase 1 Spec: `/specs/001-data-ingestion-infra/spec.md`
- Phase 2 Spec: `/specs/002-api-layer/spec.md`

---

**Version:** 1.0.0 | **Last Updated:** 2025-11-28
