# Marketbel Bun API Service - Production Dockerfile
# 
# Multi-stage build for minimal production image
# Based on official Bun Docker images

# ========================================
# Stage 1: Dependencies
# ========================================
FROM oven/bun:1.2.16-alpine AS deps

WORKDIR /app

# Copy package files
COPY package.json bun.lock ./

# Install dependencies (production only)
RUN bun install --frozen-lockfile --production

# ========================================
# Stage 2: Builder
# ========================================
FROM oven/bun:1.2.16-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY package.json bun.lock ./

# Copy source code
COPY src ./src
COPY tsconfig.json ./

# Type check (optional, can be removed for faster builds)
RUN bun run tsc --noEmit || true

# ========================================
# Stage 3: Production
# ========================================
FROM oven/bun:1.2.16-alpine AS production

# Security: Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S bun-api -u 1001 -G nodejs

WORKDIR /app

# Copy production dependencies
COPY --from=deps --chown=bun-api:nodejs /app/node_modules ./node_modules

# Copy application files
COPY --chown=bun-api:nodejs package.json ./
COPY --chown=bun-api:nodejs src ./src
COPY --chown=bun-api:nodejs migrations ./migrations

# Set environment variables
ENV NODE_ENV=production
ENV BUN_PORT=3000

# Expose port
EXPOSE 3000

# Switch to non-root user
USER bun-api

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Start the application
CMD ["bun", "run", "src/index.ts"]

