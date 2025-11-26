import { Elysia } from 'elysia'
import { swagger } from '@elysiajs/swagger'
import { cors } from '@elysiajs/cors'
import { jwt } from '@elysiajs/jwt'
import { checkDatabaseConnection } from './db/client'
import { errorHandler } from './middleware/error-handler'
import { authController } from './controllers/auth'
import { catalogController } from './controllers/catalog'
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
      documentation: {
        info: {
          title: 'Marketbel API',
          version: '1.0.0',
          description: 'High-performance API for product catalog management',
        },
        tags: [
          { name: 'auth', description: 'Authentication endpoints' },
          { name: 'catalog', description: 'Public catalog endpoints' },
          { name: 'admin', description: 'Admin operations endpoints' },
        ],
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

