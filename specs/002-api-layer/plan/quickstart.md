# Quickstart Guide: Bun API Layer

**Estimated Setup Time:** 15-20 minutes

**Prerequisites:**
- Bun v1.0+ installed
- PostgreSQL 16+ running (from Phase 1)
- Redis 7+ running (from Phase 1)
- Phase 1 database schema deployed

---

## 1. Install Bun

```bash
# macOS/Linux
curl -fsSL https://bun.sh/install | bash

# Verify installation
bun --version
# Should output: 1.x.x
```

---

## 2. Project Setup

### Create Project Directory

```bash
cd /Users/valecer/work/sites/marketbel
mkdir -p services/bun-api
cd services/bun-api
```

### Initialize Bun Project

```bash
bun init -y

# Install dependencies
bun add elysia @elysiajs/jwt @elysiajs/swagger @elysiajs/cors
bun add drizzle-orm drizzle-typebox pg
bun add ioredis
bun add -d @types/pg drizzle-kit
```

### Project Structure

```bash
mkdir -p src/{db/{schema,repositories},controllers,services,types,middleware,utils}
mkdir -p migrations tests

# Expected structure:
# src/
# ├── index.ts              # Entry point
# ├── db/
# │   ├── client.ts         # Database connection
# │   ├── schema/           # Drizzle schemas (auto-generated + manual)
# │   └── repositories/     # Repository pattern implementations
# ├── controllers/          # Feature-based controllers
# │   ├── auth/
# │   ├── catalog/
# │   └── admin/
# ├── services/             # Business logic
# ├── types/                # TypeScript types & TypeBox schemas
# ├── middleware/           # JWT auth, error handling
# └── utils/                # Helpers
```

---

## 3. Environment Configuration

### Create `.env` File

```bash
cat > .env <<EOF
# Server
BUN_PORT=3000
NODE_ENV=development

# Database (ensure Phase 1 is running)
DATABASE_URL=postgresql://marketbel_user:your_password@localhost:5432/marketbel

# Redis
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_NAME=parse-tasks

# Authentication
JWT_SECRET=$(openssl rand -base64 32)
JWT_ISSUER=marketbel-api
JWT_EXPIRATION_HOURS=24

# CORS (comma-separated for multiple origins)
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Rate Limiting
SYNC_RATE_LIMIT_PER_MINUTE=10

# Logging
LOG_LEVEL=info
EOF

echo "✅ .env file created"
```

**Important:** Update `DATABASE_URL` password to match your Phase 1 setup.

---

## 4. Database Migration (Users Table)

### Create Migration File

```bash
cat > migrations/001_create_users.sql <<EOF
-- Create user role enum
CREATE TYPE user_role AS ENUM ('sales', 'procurement', 'admin');

-- Create users table
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role user_role NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for login performance
CREATE INDEX idx_users_username ON users(username);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS \$\$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Seed default users (hashed passwords generated with bcrypt)
-- Password for all users: admin123
INSERT INTO users (username, password_hash, role) VALUES
  ('admin', '\$2b\$10\$YourHashedPasswordHere', 'admin'),
  ('sales', '\$2b\$10\$YourHashedPasswordHere', 'sales'),
  ('procurement', '\$2b\$10\$YourHashedPasswordHere', 'procurement');
EOF

echo "✅ Migration file created"
```

### Generate Password Hashes

```bash
# Create helper script to generate bcrypt hashes
cat > scripts/hash-password.ts <<EOF
const password = Bun.argv[2] || 'admin123'
const hash = await Bun.password.hash(password, { algorithm: 'bcrypt', cost: 10 })
console.log(\`Password: \${password}\`)
console.log(\`Hash: \${hash}\`)
EOF

# Generate hashes
bun run scripts/hash-password.ts admin123
# Copy the hash and update migration file
```

### Run Migration

```bash
psql $DATABASE_URL -f migrations/001_create_users.sql

# Verify
psql $DATABASE_URL -c "SELECT username, role FROM users;"
# Should show: admin, sales, procurement
```

---

## 5. Introspect Database Schema

### Configure Drizzle Kit

```bash
cat > drizzle.config.ts <<EOF
import type { Config } from 'drizzle-kit'

export default {
  schema: './src/db/schema/index.ts',
  out: './src/db/schema',
  driver: 'pg',
  dbCredentials: {
    connectionString: process.env.DATABASE_URL!
  },
  verbose: true,
  strict: true
} satisfies Config
EOF
```

### Run Introspection

```bash
# Introspect existing schema from Phase 1 + users table
bun run drizzle-kit introspect:pg

# This generates:
# src/db/schema/index.ts - Auto-generated schemas
# src/db/schema/schema.ts - Exported types
```

### Verify Generated Schema

```bash
cat src/db/schema/index.ts
# Should contain: products, supplier_items, suppliers, categories, users, etc.
```

---

## 6. Create Database Client

```bash
cat > src/db/client.ts <<EOF
import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as schema from './schema'

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  min: 5,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
})

export const db = drizzle(pool, { schema })

// Health check function
export async function checkDatabaseConnection(): Promise<boolean> {
  try {
    await pool.query('SELECT 1')
    return true
  } catch (error) {
    console.error('Database connection failed:', error)
    return false
  }
}
EOF

echo "✅ Database client created"
```

---

## 7. Create Minimal API

### Entry Point (`src/index.ts`)

```typescript
import { Elysia } from 'elysia'
import { swagger } from '@elysiajs/swagger'
import { cors } from '@elysiajs/cors'
import { jwt } from '@elysiajs/jwt'
import { checkDatabaseConnection } from './db/client'

const app = new Elysia()
  .use(cors({
    origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000']
  }))
  .use(swagger({
    documentation: {
      info: {
        title: 'Marketbel API',
        version: '1.0.0',
        description: 'High-performance API for product catalog management'
      }
    }
  }))
  .use(jwt({
    name: 'jwt',
    secret: process.env.JWT_SECRET!,
    exp: `${process.env.JWT_EXPIRATION_HOURS || 24}h`
  }))
  .get('/health', async () => {
    const dbHealthy = await checkDatabaseConnection()
    return {
      status: dbHealthy ? 'healthy' : 'unhealthy',
      database: dbHealthy ? 'connected' : 'disconnected',
      timestamp: new Date().toISOString()
    }
  })
  .get('/', () => ({
    message: 'Marketbel API v1.0.0',
    docs: '/docs'
  }))
  .listen(process.env.BUN_PORT || 3000)

console.log(`🚀 Marketbel API running at http://localhost:${app.server?.port}`)
console.log(`📚 API Documentation: http://localhost:${app.server?.port}/docs`)
```

---

## 8. Run the API

```bash
# Development mode (with hot reload)
bun --watch src/index.ts

# Production mode
bun run src/index.ts
```

### Verify API is Running

```bash
# Health check
curl http://localhost:3000/health
# Expected: {"status":"healthy","database":"connected","timestamp":"..."}

# Root endpoint
curl http://localhost:3000/
# Expected: {"message":"Marketbel API v1.0.0","docs":"/docs"}

# Swagger docs
open http://localhost:3000/docs
```

---

## 9. Test Authentication

### Create Test Login Script

```bash
cat > scripts/test-login.ts <<EOF
const response = await fetch('http://localhost:3000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'admin123'
  })
})

const data = await response.json()
console.log('Login Response:', data)

if (data.token) {
  console.log('\\n✅ JWT Token obtained!')
  console.log('Use in requests: Authorization: Bearer', data.token)
}
EOF

bun run scripts/test-login.ts
```

---

## 10. Docker Setup (Optional)

### Create Dockerfile

```dockerfile
FROM oven/bun:latest

WORKDIR /app

# Copy package files
COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile --production

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Run application
CMD ["bun", "run", "src/index.ts"]
```

### Add to docker-compose.yml

```yaml
services:
  bun-api:
    build:
      context: ./services/bun-api
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://marketbel_user:${DB_PASSWORD}@postgres:5432/marketbel
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
      JWT_ISSUER: marketbel-api
      JWT_EXPIRATION_HOURS: 24
      ALLOWED_ORIGINS: http://localhost:5173
      LOG_LEVEL: info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### Start with Docker

```bash
docker-compose up -d bun-api

# Check logs
docker-compose logs -f bun-api

# Verify health
curl http://localhost:3000/health
```

---

## 11. Development Workflow

### Run Tests

```bash
# Unit tests
bun test

# Watch mode
bun test --watch

# Coverage
bun test --coverage
```

### Lint and Format

```bash
# Add Biome (Bun-native linter/formatter)
bun add -d @biomejs/biome

# Create biome.json
cat > biome.json <<EOF
{
  "\$schema": "https://biomejs.dev/schemas/1.4.1/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2
  }
}
EOF

# Lint
bun run biome lint src/

# Format
bun run biome format --write src/
```

---

## 12. Troubleshooting

### Issue: Database connection fails

**Solution:**
```bash
# Check Phase 1 PostgreSQL is running
docker-compose ps postgres

# Verify credentials
psql $DATABASE_URL -c "SELECT 1"

# Check DATABASE_URL format
echo $DATABASE_URL
# Should be: postgresql://user:password@host:port/database
```

### Issue: JWT_SECRET missing

**Solution:**
```bash
# Generate new secret
openssl rand -base64 32

# Add to .env
echo "JWT_SECRET=<generated_secret>" >> .env
```

### Issue: Redis unavailable

**Solution:**
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli -u $REDIS_URL ping
# Should respond: PONG
```

### Issue: Schema introspection fails

**Solution:**
```bash
# Ensure Phase 1 migrations are applied
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "\dt"

# Check drizzle.config.ts DATABASE_URL
# Run introspection with verbose logging
bun run drizzle-kit introspect:pg --verbose
```

---

## 13. Next Steps

After completing this quickstart:

1. **Implement Controllers:**
   - `src/controllers/auth/index.ts` - Login endpoint
   - `src/controllers/catalog/index.ts` - Public catalog
   - `src/controllers/admin/index.ts` - Admin operations

2. **Add Business Logic:**
   - `src/services/catalog.service.ts` - Product filtering
   - `src/services/admin.service.ts` - Matching logic, margin calculation
   - `src/services/queue.service.ts` - Redis publishing

3. **Create Repositories:**
   - `src/db/repositories/product.repository.ts`
   - `src/db/repositories/supplier_item.repository.ts`
   - `src/db/repositories/user.repository.ts`

4. **Write Tests:**
   - Unit tests for services and business logic
   - Integration tests with test database
   - E2E tests for critical flows

5. **Add Observability:**
   - Structured logging with request IDs
   - Metrics collection (response times, error rates)
   - Health checks for database and Redis

---

## 14. Useful Commands

```bash
# Start API with hot reload
bun --watch src/index.ts

# Run specific test file
bun test tests/services/catalog.test.ts

# Check TypeScript types
bun run tsc --noEmit

# Generate new migration
bun run drizzle-kit generate:pg

# View database schema
psql $DATABASE_URL -c "\d+ products"

# Monitor Redis queue
redis-cli -u $REDIS_URL LLEN parse-tasks

# View API logs
docker-compose logs -f bun-api --tail=100
```

---

## Summary

You've successfully:

- ✅ Installed Bun runtime
- ✅ Created project structure
- ✅ Configured environment variables
- ✅ Created users table for authentication
- ✅ Introspected Phase 1 database schema
- ✅ Set up Drizzle ORM client
- ✅ Created minimal API with health check
- ✅ Configured Swagger documentation
- ✅ Verified database and Redis connectivity

**API is now running at:** http://localhost:3000

**Next:** Implement feature-specific controllers and services according to the implementation plan.

---

**Estimated Total Setup Time:** 15-20 minutes

**Questions?** Check the troubleshooting section or refer to:
- ElysiaJS Docs: https://elysiajs.com/
- Drizzle ORM Docs: https://orm.drizzle.team/
- Bun Docs: https://bun.sh/docs
