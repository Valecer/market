import { Elysia } from 'elysia'
import { swagger } from '@elysiajs/swagger'
import { cors } from '@elysiajs/cors'
import { jwt } from '@elysiajs/jwt'
import { checkDatabaseConnection } from './db/client'
import { errorHandler } from './middleware/error-handler'
import { authController } from './controllers/auth'
import { catalogController } from './controllers/catalog'
import { adminController } from './controllers/admin'
import Redis from 'ioredis'

// Initialize Redis client
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379')

// Health check for Redis
async function checkRedisConnection(): Promise<boolean> {
  try {
    await redis.ping()
    return true
  } catch (error) {
    console.error('Redis connection failed:', error)
    return false
  }
}

const app = new Elysia()
  .use(errorHandler)
  .use(
    cors({
      origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
      credentials: true,
    })
  )
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
  .use(
    jwt({
      name: 'jwt',
      secret: process.env.JWT_SECRET || 'change-me-in-production',
      exp: `${process.env.JWT_EXPIRATION_HOURS || 24}h`,
    })
  )
  .use(authController)
  .use(catalogController)
  .use(adminController)
  .get('/health', async () => {
    const dbHealthy = await checkDatabaseConnection()
    const redisHealthy = await checkRedisConnection()

    return {
      status: dbHealthy && redisHealthy ? 'healthy' : 'unhealthy',
      database: dbHealthy ? 'connected' : 'disconnected',
      redis: redisHealthy ? 'connected' : 'disconnected',
      timestamp: new Date().toISOString(),
    }
  })
  .get('/', () => ({
    message: 'Marketbel API v1.0.0',
    docs: '/docs',
    health: '/health',
  }))
  .listen(Number(process.env.BUN_PORT) || 3000)

console.log(`🚀 Marketbel API running at http://localhost:${app.server?.port}`)
console.log(`📚 API Documentation: http://localhost:${app.server?.port}/docs`)

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, closing connections...')
  await redis.quit()
  process.exit(0)
})

