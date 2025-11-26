import Redis from 'ioredis'

/**
 * Queue Service
 * 
 * Wraps Redis client for publishing messages to the parse-tasks queue
 * Used by the sync endpoint to enqueue background data ingestion tasks
 */

export class QueueService {
  private redis: Redis
  private queueName: string

  constructor(redisUrl?: string, queueName?: string) {
    this.redis = new Redis(redisUrl || process.env.REDIS_URL || 'redis://localhost:6379')
    this.queueName = queueName || process.env.REDIS_QUEUE_NAME || 'parse-tasks'
  }

  /**
   * Check if Redis connection is healthy
   * @returns true if Redis is reachable, false otherwise
   */
  async isHealthy(): Promise<boolean> {
    try {
      const result = await this.redis.ping()
      return result === 'PONG'
    } catch (error) {
      console.error('Redis health check failed:', error)
      return false
    }
  }

  /**
   * Enqueue a parse task message to Redis
   * 
   * @param message - The task message object to serialize and enqueue
   * @returns The task ID from the message
   * @throws Error if Redis is unavailable
   */
  async enqueueParseTask(message: {
    task_id: string
    parser_type: string
    supplier_name: string
    source_config: Record<string, any>
    retry_count: number
    max_retries: number
    enqueued_at: string
  }): Promise<string> {
    try {
      const serialized = JSON.stringify(message)
      await this.redis.lpush(this.queueName, serialized)
      return message.task_id
    } catch (error) {
      console.error('Failed to enqueue task to Redis:', error)
      throw new Error('Redis unavailable')
    }
  }

  /**
   * Close Redis connection gracefully
   */
  async close(): Promise<void> {
    await this.redis.quit()
  }
}

// Export singleton instance
export const queueService = new QueueService()

