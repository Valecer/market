# =============================================================================
# Marketbel Frontend Dockerfile
# =============================================================================
# Multi-stage build for production-ready React application
# 
# Stage 1: Build the application with Bun
# Stage 2: Serve static files with Nginx
#
# Build: docker build -t marketbel-frontend .
# Run:   docker run -p 80:80 marketbel-frontend
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM oven/bun:1-alpine AS builder

WORKDIR /app

# Copy package files first for better layer caching
COPY package.json bun.lock ./

# Install dependencies (production + dev for build)
RUN bun install --frozen-lockfile

# Copy source files
COPY . .

# Set build-time environment variables
# These get baked into the bundle at build time
ARG VITE_API_URL=http://localhost:3000
ARG VITE_ENV=production

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_ENV=${VITE_ENV}

# Build the application
RUN bun run build

# -----------------------------------------------------------------------------
# Stage 2: Production Server (Nginx)
# -----------------------------------------------------------------------------
FROM nginx:1.25-alpine AS production

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy custom nginx configuration
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    listen [::]:80;
    server_name _;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json image/svg+xml;
    gzip_disable "MSIE [1-6]\.";
    
    # Cache static assets aggressively
    location ~* \.(?:css|js|woff2?|eot|ttf|otf|ico|jpg|jpeg|png|gif|svg|webp)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
    
    # SPA routing - serve index.html for all non-file requests
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Don't cache index.html
    location = /index.html {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]

