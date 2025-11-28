import { Elysia } from 'elysia'
import { swagger } from '@elysiajs/swagger'
import { cors } from '@elysiajs/cors'
import { jwt } from '@elysiajs/jwt'
import { checkDatabaseConnection, getDatabasePoolStats } from './db/client'
import { errorHandler } from './middleware/error-handler'
import { logger } from './middleware/logger'
import { defaultSecurityHeaders } from './middleware/security-headers'
import { authController } from './controllers/auth'
import { catalogController } from './controllers/catalog'
import { adminController } from './controllers/admin'
import Redis from 'ioredis'

// Initialize Redis client with reconnection strategy
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    const delay = Math.min(times * 100, 3000)
    console.log(`Redis reconnecting, attempt ${times}, delay ${delay}ms`)
    return delay
  },
  reconnectOnError(err) {
    const targetErrors = ['READONLY', 'ECONNRESET', 'ETIMEDOUT']
    return targetErrors.some(e => err.message.includes(e))
  },
})

// Redis event listeners for monitoring
redis.on('connect', () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'info',
    message: 'Redis connected',
    service: 'bun-api',
  }))
})

redis.on('error', (error) => {
  console.error(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'error',
    message: 'Redis connection error',
    error: error.message,
    service: 'bun-api',
  }))
})

redis.on('close', () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'warn',
    message: 'Redis connection closed',
    service: 'bun-api',
  }))
})

// Health check for Redis with stats
async function checkRedisConnection(): Promise<{
  connected: boolean
  latencyMs?: number
  info?: Record<string, string>
}> {
  try {
    const start = Date.now()
    const pong = await redis.ping()
    const latencyMs = Date.now() - start
    
    // Get basic Redis info for monitoring
    const infoRaw = await redis.info('server')
    const info: Record<string, string> = {}
    infoRaw.split('\r\n').forEach(line => {
      const [key, value] = line.split(':')
      if (key && value) info[key] = value
    })
    
    return {
      connected: pong === 'PONG',
      latencyMs,
      info: {
        redis_version: info.redis_version || 'unknown',
        uptime_in_seconds: info.uptime_in_seconds || 'unknown',
      },
    }
  } catch (error) {
    console.error('Redis health check failed:', error)
    return { connected: false }
  }
}

// Graceful shutdown state
let isShuttingDown = false
const SHUTDOWN_TIMEOUT = 30000 // 30 seconds max for graceful shutdown

const app = new Elysia()
  // Security headers first (sets headers on all responses)
  .use(defaultSecurityHeaders)
  // Logging middleware
  .use(logger)
  // Error handler
  .use(errorHandler)
  // CORS configuration
  .use(
    cors({
      origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
      credentials: true,
    })
  )
  // Swagger documentation
  .use(
    swagger({
      path: '/docs',
      documentation: {
        info: {
          title: 'Marketbel API',
          version: '1.0.0',
          description:
            'High-performance API for unified product catalog management. Provides endpoints for browsing products, managing supplier relationships, and triggering data synchronization.',
          termsOfService: '/terms',
          contact: {
            name: 'Marketbel API Support',
            email: 'api-support@marketbel.com',
          },
          license: {
            name: 'Proprietary',
            url: '/license',
          },
        },
        servers: [
          {
            url: 'http://localhost:3000',
            description: 'Development server',
          },
          {
            url: 'https://api.marketbel.com',
            description: 'Production server',
          },
        ],
        tags: [
          {
            name: 'auth',
            description:
              'Authentication endpoints for obtaining JWT tokens. Use the login endpoint to authenticate and receive a bearer token for protected endpoints.',
          },
          {
            name: 'catalog',
            description:
              'Public catalog endpoints for browsing active products. No authentication required. Supports filtering by category, price range, and search.',
          },
          {
            name: 'admin',
            description:
              'Protected admin endpoints for internal staff. Requires JWT authentication. Includes product management, supplier matching, and sync operations.',
          },
        ],
        components: {
          securitySchemes: {
            bearerAuth: {
              type: 'http',
              scheme: 'bearer',
              bearerFormat: 'JWT',
              description:
                'JWT token obtained from POST /api/v1/auth/login. Include in Authorization header as: Bearer <token>',
            },
          },
        },
        externalDocs: {
          description: 'API Implementation Guide',
          url: 'https://github.com/marketbel/api-docs',
        },
      },
    })
  )
  // JWT authentication
  .use(
    jwt({
      name: 'jwt',
      secret: process.env.JWT_SECRET || 'change-me-in-production',
      exp: `${process.env.JWT_EXPIRATION_HOURS || 24}h`,
    })
  )
  // Controllers
  .use(authController)
  .use(catalogController)
  .use(adminController)
  // Health check endpoint with detailed monitoring
  .get('/health', async ({ set }) => {
    // Return 503 if shutting down
    if (isShuttingDown) {
      set.status = 503
      return {
        status: 'shutting_down',
        message: 'Server is shutting down',
        timestamp: new Date().toISOString(),
      }
    }
    
    const [dbStatus, redisStatus] = await Promise.all([
      (async () => {
        const healthy = await checkDatabaseConnection()
        const stats = getDatabasePoolStats()
        return { healthy, stats }
      })(),
      checkRedisConnection(),
    ])
    
    const dbHealthy = dbStatus.healthy
    const redisHealthy = redisStatus.connected
    const allHealthy = dbHealthy && redisHealthy
    
    // Set appropriate status code
    set.status = allHealthy ? 200 : 503
    
    return {
      status: allHealthy ? 'healthy' : 'unhealthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      version: '1.0.0',
      services: {
        database: {
          status: dbHealthy ? 'connected' : 'disconnected',
          pool: dbStatus.stats,
        },
        redis: {
          status: redisHealthy ? 'connected' : 'disconnected',
          latencyMs: redisStatus.latencyMs,
          info: redisStatus.info,
        },
      },
    }
  })
  // Readiness probe (for Kubernetes/Docker health checks)
  .get('/ready', async ({ set }) => {
    if (isShuttingDown) {
      set.status = 503
      return { ready: false, reason: 'shutting_down' }
    }
    
    const dbHealthy = await checkDatabaseConnection()
    const redisStatus = await checkRedisConnection()
    const ready = dbHealthy && redisStatus.connected
    
    set.status = ready ? 200 : 503
    return { ready }
  })
  // Liveness probe (for Kubernetes/Docker)
  .get('/live', ({ set }) => {
    if (isShuttingDown) {
      set.status = 503
      return { alive: false }
    }
    set.status = 200
    return { alive: true }
  })
  // Root endpoint
  .get('/', () => ({
    message: 'Marketbel API v1.0.0',
    docs: '/docs',
    health: '/health',
    ready: '/ready',
    live: '/live',
  }))
  .listen(Number(process.env.BUN_PORT) || 3000)

console.log(JSON.stringify({
  timestamp: new Date().toISOString(),
  level: 'info',
  message: 'Server started',
  port: app.server?.port,
  docs: `http://localhost:${app.server?.port}/docs`,
  env: process.env.NODE_ENV || 'development',
  service: 'bun-api',
}))

// Graceful shutdown handler
async function gracefulShutdown(signal: string) {
  if (isShuttingDown) {
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Shutdown already in progress',
      signal,
      service: 'bun-api',
    }))
    return
  }
  
  isShuttingDown = true
  
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'info',
    message: 'Graceful shutdown initiated',
    signal,
    service: 'bun-api',
  }))
  
  // Set a timeout to force exit if graceful shutdown takes too long
  const forceExitTimeout = setTimeout(() => {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'error',
      message: 'Graceful shutdown timeout, forcing exit',
      service: 'bun-api',
    }))
    process.exit(1)
  }, SHUTDOWN_TIMEOUT)
  
  try {
    // Stop accepting new connections
    app.server?.stop()
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'Server stopped accepting new connections',
      service: 'bun-api',
    }))
    
    // Wait a bit for in-flight requests to complete
    await new Promise(resolve => setTimeout(resolve, 5000))
    
    // Close Redis connection
    await redis.quit()
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'Redis connection closed',
      service: 'bun-api',
    }))
    
    // Database pool will be closed by its own SIGTERM handler
    
    clearTimeout(forceExitTimeout)
    
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'Graceful shutdown completed',
      service: 'bun-api',
    }))
    
    process.exit(0)
  } catch (error) {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'error',
      message: 'Error during graceful shutdown',
      error: error instanceof Error ? error.message : String(error),
      service: 'bun-api',
    }))
    clearTimeout(forceExitTimeout)
    process.exit(1)
  }
}

// Register shutdown handlers
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'))
process.on('SIGINT', () => gracefulShutdown('SIGINT'))

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  console.error(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'error',
    message: 'Uncaught exception',
    error: error.message,
    stack: error.stack,
    service: 'bun-api',
  }))
  gracefulShutdown('uncaughtException')
})

process.on('unhandledRejection', (reason) => {
  console.error(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'error',
    message: 'Unhandled rejection',
    reason: String(reason),
    service: 'bun-api',
  }))
  // Don't exit on unhandled rejections, just log them
})

export type App = typeof app
