# Marketbel API Service

High-performance REST API built with Bun and ElysiaJS for product catalog management.

## Quick Start

### Prerequisites

- Bun v1.0+ installed
- PostgreSQL 16+ running (from Phase 1)
- Redis 7+ running (from Phase 1)
- Phase 1 database schema deployed

### Setup

1. **Install dependencies:**
   ```bash
   bun install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis credentials
   ```

3. **Run database migration:**
   ```bash
   psql $DATABASE_URL -f migrations/001_create_users.sql
   ```

4. **Seed default users:**
   ```bash
   bun run scripts/seed-users.ts
   ```

5. **Introspect database schema:**
   ```bash
   bun run drizzle-kit introspect:pg
   ```

6. **Start the API:**
   ```bash
   bun --watch src/index.ts
   ```

### Verify Installation

- Health check: `curl http://localhost:3000/health`
- API docs: `open http://localhost:3000/docs`
- Root endpoint: `curl http://localhost:3000/`

## Development

### Project Structure

```
src/
├── index.ts              # Entry point
├── db/
│   ├── client.ts         # Database connection
│   ├── schema/           # Drizzle schemas
│   └── repositories/     # Repository pattern
├── controllers/          # Feature-based controllers
│   ├── auth/
│   ├── catalog/
│   └── admin/
├── services/             # Business logic
├── types/                # TypeScript types & TypeBox schemas
├── middleware/           # JWT auth, error handling
└── utils/                # Helpers
```

### Environment Variables

See `.env.example` for all required environment variables.

### Database

- **Phase 1 tables:** Read-only, introspected via Drizzle
- **Phase 2 tables:** Managed locally (users table)

### Testing

```bash
# Run tests
bun test

# Watch mode
bun test --watch

# Coverage
bun test --coverage
```

## API Endpoints

### Public

- `GET /health` - Health check
- `GET /api/v1/catalog` - Public catalog (no auth required)

### Authentication

- `POST /api/v1/auth/login` - Login and get JWT token

### Admin (Requires JWT)

- `GET /api/v1/admin/products` - List products with supplier details
- `PATCH /api/v1/admin/products/:id/match` - Link/unlink supplier items
- `POST /api/v1/admin/products` - Create new product
- `POST /api/v1/admin/sync` - Trigger data sync

## Documentation

- Swagger UI: `/docs`
- OpenAPI spec: `/docs/json`

## Docker

```bash
# Build
docker build -t marketbel-api .

# Run
docker run -p 3000:3000 --env-file .env marketbel-api
```

## Troubleshooting

See the quickstart guide in `/specs/002-api-layer/plan/quickstart.md` for detailed troubleshooting steps.
