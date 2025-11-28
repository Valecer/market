import Redis from 'ioredis'
import type { ParseTaskMessage } from '../types/queue.types'

/**
 * Custom error for Redis unavailability
 */
export class RedisUnavailableError extends Error {
  readonly code = 'REDIS_UNAVAILABLE'

  constructor(message: string = 'Queue service is temporarily unavailable') {
    super(message)
    this.name = 'RedisUnavailableError'
  }
}

/**
 * Queue Service
 * 
 * Wraps Redis client for publishing messages to the parse-tasks queue
 * Used by the sync endpoint to enqueue background data ingestion tasks
 */
export class QueueService {
  private redis: Redis | null = null
  private queueName: string
  private redisUrl: string
  private connectionAttempted: boolean = false

  constructor(redisUrl?: string, queueName?: string) {
    this.redisUrl = redisUrl || process.env.REDIS_URL || 'redis://localhost:6379'
    this.queueName = queueName || process.env.REDIS_QUEUE_NAME || 'parse-tasks'
  }

  /**
   * Get or create Redis connection
   * Uses lazy connection to avoid blocking startup if Redis is unavailable
   */
  private async getRedis(): Promise<Redis> {
    if (this.redis && this.redis.status === 'ready') {
      return this.redis
    }

    // Create new connection
    this.redis = new Redis(this.redisUrl, {
      maxRetriesPerRequest: 1,
      retryStrategy: (times) => {
        // Only retry once, then fail fast
        if (times > 1) {
          return null
        }
        return 100 // Wait 100ms before retry
      },
      lazyConnect: true,
      connectTimeout: 5000, // 5 second connection timeout
    })

    try {
      await this.redis.connect()
      this.connectionAttempted = true
      return this.redis
    } catch (error) {
      this.connectionAttempted = true
      this.redis = null
      throw new RedisUnavailableError()
    }
  }

  /**
   * Check if Redis connection is healthy
   * @returns true if Redis is reachable, false otherwise
   */
  async isHealthy(): Promise<boolean> {
    try {
      const redis = await this.getRedis()
      const result = await redis.ping()
      return result === 'PONG'
    } catch (error) {
      console.error('Redis health check failed:', error)
      return false
    }
  }

  /**
   * Enqueue a parse task message to Redis
   * 
   * @param message - The task message object matching ParseTaskMessage schema
   * @returns The task ID from the message
   * @throws RedisUnavailableError if Redis is unavailable
   */
  async enqueueParseTask(message: ParseTaskMessage): Promise<string> {
    try {
      const redis = await this.getRedis()
      const serialized = JSON.stringify(message)
      await redis.lpush(this.queueName, serialized)
      return message.task_id
    } catch (error) {
      if (error instanceof RedisUnavailableError) {
        throw error
      }
      console.error('Failed to enqueue task to Redis:', error)
      throw new RedisUnavailableError()
    }
  }

  /**
   * Close Redis connection gracefully
   */
  async close(): Promise<void> {
    if (this.redis) {
    await this.redis.quit()
      this.redis = null
    }
  }
}

// Export singleton instance
export const queueService = new QueueService()

