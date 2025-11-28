import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as schema from './schema'

// Pool configuration with sensible defaults
const poolConfig = {
  connectionString: process.env.DATABASE_URL,
  min: Number(process.env.DB_POOL_MIN) || 5,
  max: Number(process.env.DB_POOL_MAX) || 20,
  idleTimeoutMillis: Number(process.env.DB_IDLE_TIMEOUT) || 30000,
  connectionTimeoutMillis: Number(process.env.DB_CONNECTION_TIMEOUT) || 2000,
  // Allow exit even if there are connections in the pool
  allowExitOnIdle: true,
}

const pool = new Pool(poolConfig)

// Pool event listeners for monitoring
pool.on('connect', () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'debug',
    message: 'New database connection established',
    service: 'bun-api',
  }))
})

pool.on('acquire', () => {
  // Connection acquired from pool - can be noisy, use debug level
  if (process.env.LOG_LEVEL === 'debug') {
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'debug',
      message: 'Database connection acquired from pool',
      service: 'bun-api',
    }))
  }
})

pool.on('error', (error) => {
  console.error(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'error',
    message: 'Database pool error',
    error: error.message,
    stack: error.stack,
    service: 'bun-api',
  }))
})

pool.on('remove', () => {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'debug',
    message: 'Database connection removed from pool',
    service: 'bun-api',
  }))
})

export const db = drizzle(pool, { schema })

/**
 * Health check function - verifies database connectivity
 */
export async function checkDatabaseConnection(): Promise<boolean> {
  try {
    await pool.query('SELECT 1')
    return true
  } catch (error) {
    console.error('Database connection failed:', error)
    return false
  }
}

/**
 * Get current database connection pool statistics
 * Useful for monitoring and alerting
 */
export interface PoolStats {
  /** Total number of connections in the pool */
  totalCount: number
  /** Number of idle connections */
  idleCount: number
  /** Number of connections in use */
  activeCount: number
  /** Number of clients waiting for a connection */
  waitingCount: number
  /** Pool utilization percentage */
  utilizationPercent: number
  /** Pool configuration */
  config: {
    min: number
    max: number
    idleTimeoutMillis: number
    connectionTimeoutMillis: number
  }
}

export function getDatabasePoolStats(): PoolStats {
  const totalCount = pool.totalCount
  const idleCount = pool.idleCount
  const activeCount = totalCount - idleCount
  const waitingCount = pool.waitingCount
  const utilizationPercent = poolConfig.max > 0 
    ? Math.round((activeCount / poolConfig.max) * 100) 
    : 0
  
  // Log warning if pool utilization is high
  if (utilizationPercent >= 80) {
    console.warn(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Database pool utilization high',
      utilizationPercent,
      activeCount,
      maxConnections: poolConfig.max,
      waitingCount,
      service: 'bun-api',
    }))
  }
  
  return {
    totalCount,
    idleCount,
    activeCount,
    waitingCount,
    utilizationPercent,
    config: {
      min: poolConfig.min,
      max: poolConfig.max,
      idleTimeoutMillis: poolConfig.idleTimeoutMillis,
      connectionTimeoutMillis: poolConfig.connectionTimeoutMillis,
    },
  }
}

/**
 * Close all pool connections gracefully
 */
export async function closePool(): Promise<void> {
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'info',
    message: 'Closing database connection pool',
    stats: getDatabasePoolStats(),
    service: 'bun-api',
  }))
  
  await pool.end()
  
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    level: 'info',
    message: 'Database connection pool closed',
    service: 'bun-api',
  }))
}

// Graceful shutdown for database pool
process.on('SIGTERM', async () => {
  await closePool()
})

process.on('SIGINT', async () => {
  await closePool()
})
