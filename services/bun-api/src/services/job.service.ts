/**
 * Job Service
 *
 * Business logic for job management including retry functionality.
 * Handles job state validation and retry task enqueueing.
 *
 * T85: Added user-facing error recommendations for common failure scenarios.
 *
 * @see /specs/008-ml-ingestion-integration/plan.md - User Story 3
 */

import Redis from 'ioredis'
import type { RetryJobResponse, IngestionJob } from '../types/ingestion.types'
import { RedisUnavailableError } from './queue.service'

// =============================================================================
// Redis Key Constants (must match Python worker job_state.py)
// =============================================================================

const JOB_KEY_PREFIX = 'job:'
const ARQ_QUEUE_NAME = process.env.ARQ_QUEUE_NAME || 'arq:queue'

// =============================================================================
// T85: User-Facing Error Recommendations
// =============================================================================

/**
 * Error recommendation interface for user-friendly error handling.
 */
interface ErrorRecommendation {
  title: string
  description: string
  recommendation: string
  canRetry: boolean
  supportLink?: string
}

/**
 * Map of error patterns to user-friendly recommendations.
 * T85: Provides actionable guidance for common error scenarios.
 */
const ERROR_RECOMMENDATIONS: Record<string, ErrorRecommendation> = {
  // File-related errors
  'file not found': {
    title: 'File Not Found',
    description: 'The uploaded file could not be located for processing.',
    recommendation: 'Please re-upload the file and try again. Ensure the file is not corrupted.',
    canRetry: false,
  },
  'no product sheets': {
    title: 'No Product Data Found',
    description: 'The file does not contain recognizable product sheets.',
    recommendation: 'Ensure your Excel file has a sheet named "Upload to site", "Products", or "Catalog" with product data.',
    canRetry: false,
  },
  'empty sheet': {
    title: 'Empty Spreadsheet',
    description: 'The selected sheet contains no data.',
    recommendation: 'Add at least one row of product data with Name and Price columns.',
    canRetry: false,
  },
  'invalid file': {
    title: 'Invalid File Format',
    description: 'The file format is not supported or the file is corrupted.',
    recommendation: 'Use Excel (.xlsx) or CSV format. Try re-exporting from your source application.',
    canRetry: false,
  },

  // Processing errors
  'timeout': {
    title: 'Processing Timeout',
    description: 'The file took too long to process.',
    recommendation: 'Try uploading a smaller file (under 500 rows). For large catalogs, split into multiple files.',
    canRetry: true,
  },
  'llm error': {
    title: 'AI Processing Issue',
    description: 'Our AI system encountered a temporary issue.',
    recommendation: 'This is usually temporary. Please wait a minute and retry.',
    canRetry: true,
  },
  'connection': {
    title: 'Connection Error',
    description: 'A network connection issue occurred.',
    recommendation: 'Check your internet connection and try again.',
    canRetry: true,
  },

  // Validation errors
  'validation': {
    title: 'Data Validation Error',
    description: 'Some products have missing or invalid fields.',
    recommendation: 'Ensure each product has at least a Name and Price. Prices should be numeric values.',
    canRetry: false,
  },
  'missing required': {
    title: 'Missing Required Data',
    description: 'Required product fields are missing.',
    recommendation: 'Check that your file includes columns for product Name and Price.',
    canRetry: false,
  },

  // System errors
  'internal error': {
    title: 'System Error',
    description: 'An unexpected error occurred in our system.',
    recommendation: 'Please try again. If the problem persists, contact support with your job ID.',
    canRetry: true,
    supportLink: '/support',
  },
  'database': {
    title: 'Database Error',
    description: 'A database operation failed.',
    recommendation: 'This is usually temporary. Please retry in a few minutes.',
    canRetry: true,
  },
  'rate limit': {
    title: 'Too Many Requests',
    description: 'Processing rate limit reached.',
    recommendation: 'Please wait a few minutes before submitting more files.',
    canRetry: true,
  },
}

/**
 * Default recommendation for unknown errors.
 */
const DEFAULT_RECOMMENDATION: ErrorRecommendation = {
  title: 'Processing Error',
  description: 'An error occurred while processing your file.',
  recommendation: 'Please try again. If the issue persists, contact support with your job ID.',
  canRetry: true,
}

/**
 * Get user-friendly error recommendation based on error message.
 *
 * T85: Matches error message patterns to provide actionable guidance.
 *
 * @param errorMessage - Technical error message
 * @returns User-friendly error recommendation
 */
export function getErrorRecommendation(errorMessage: string | null): ErrorRecommendation {
  if (!errorMessage) {
    return DEFAULT_RECOMMENDATION
  }

  const lowerError = errorMessage.toLowerCase()

  // Find matching recommendation based on error message patterns
  for (const [pattern, recommendation] of Object.entries(ERROR_RECOMMENDATIONS)) {
    if (lowerError.includes(pattern)) {
      return recommendation
    }
  }

  // Special handling for specific error codes
  if (lowerError.includes('etimedout') || lowerError.includes('timed out')) {
    return ERROR_RECOMMENDATIONS['timeout']
  }
  if (lowerError.includes('econnrefused') || lowerError.includes('econnreset')) {
    return ERROR_RECOMMENDATIONS['connection']
  }
  if (lowerError.includes('500') || lowerError.includes('internal server')) {
    return ERROR_RECOMMENDATIONS['internal error']
  }

  return DEFAULT_RECOMMENDATION
}

/**
 * Format error with user-friendly recommendation.
 *
 * T85: Combines technical error with user guidance.
 *
 * @param errorMessage - Technical error message
 * @returns Formatted error object with recommendation
 */
export function formatErrorWithRecommendation(
  errorMessage: string | null
): {
  error: string | null
  recommendation: ErrorRecommendation
  formatted_message: string
} {
  const recommendation = getErrorRecommendation(errorMessage)

  return {
    error: errorMessage,
    recommendation,
    formatted_message: `${recommendation.title}: ${recommendation.description} ${recommendation.recommendation}`,
  }
}

// =============================================================================
// Types
// =============================================================================

interface JobNotFoundError extends Error {
  code: 'NOT_FOUND'
}

interface JobNotFailedError extends Error {
  code: 'INVALID_STATE'
  current_phase: string
}

interface MaxRetriesExceededError extends Error {
  code: 'MAX_RETRIES_EXCEEDED'
  retry_count: number
  max_retries: number
}

// =============================================================================
// Job Service
// =============================================================================

export class JobService {
  private redis: Redis | null = null
  private redisUrl: string

  constructor(redisUrl?: string) {
    this.redisUrl = redisUrl || process.env.REDIS_URL || 'redis://localhost:6379'
  }

  /**
   * Get or create Redis connection (lazy initialization)
   */
  private async getRedis(): Promise<Redis> {
    if (this.redis && this.redis.status === 'ready') {
      return this.redis
    }

    this.redis = new Redis(this.redisUrl, {
      maxRetriesPerRequest: 1,
      retryStrategy: (times) => {
        if (times > 1) return null
        return 100
      },
      lazyConnect: true,
      connectTimeout: 5000,
    })

    try {
      await this.redis.connect()
      return this.redis
    } catch (error) {
      this.redis = null
      throw new RedisUnavailableError()
    }
  }

  /**
   * Get job data from Redis
   */
  private async getJob(jobId: string): Promise<IngestionJob | null> {
    const redis = await this.getRedis()
    const key = `${JOB_KEY_PREFIX}${jobId}`
    const data = await redis.hgetall(key)

    if (!data || Object.keys(data).length === 0) {
      return null
    }

    return this.parseJobData(data)
  }

  /**
   * Parse raw Redis hash data into IngestionJob
   *
   * T85: Now includes user-friendly error recommendations.
   */
  private parseJobData(data: Record<string, string>): IngestionJob {
    // Parse error details
    let errorDetails: string[] = []
    if (data.error_details) {
      try {
        const parsed = JSON.parse(data.error_details)
        errorDetails = Array.isArray(parsed) ? parsed : []
      } catch {
        errorDetails = data.error_details ? [data.error_details] : []
      }
    }

    // Build download progress
    const downloadBytes = parseInt(data.download_bytes || '0', 10)
    const downloadTotal = parseInt(data.download_total || '0', 10)
    const downloadProgress =
      downloadTotal > 0 || downloadBytes > 0
        ? {
            bytes_downloaded: downloadBytes,
            bytes_total: downloadTotal > 0 ? downloadTotal : null,
            percentage: downloadTotal > 0 ? Math.round((downloadBytes / downloadTotal) * 100) : 0,
          }
        : null

    // Build analysis progress
    const itemsProcessed = parseInt(data.items_processed || '0', 10)
    const itemsTotal = parseInt(data.items_total || '0', 10)
    const matchesFound = parseInt(data.matches_found || '0', 10)
    const reviewQueue = parseInt(data.review_queue_count || '0', 10)
    const errorCount = parseInt(data.error_count || '0', 10)
    const analysisProgress =
      itemsTotal > 0 || itemsProcessed > 0
        ? {
            items_processed: itemsProcessed,
            items_total: itemsTotal,
            matches_found: matchesFound,
            review_queue: reviewQueue,
            errors: errorCount,
            percentage: itemsTotal > 0 ? Math.round((itemsProcessed / itemsTotal) * 100) : 0,
          }
        : null

    // T85: Get user-friendly error recommendation
    const errorMessage = data.error || null
    const errorInfo = formatErrorWithRecommendation(errorMessage)

    // T85: Build retry summary
    const retryCount = parseInt(data.retry_count || '0', 10)
    const maxRetries = parseInt(data.max_retries || '3', 10)
    let retrySummary: string | null = null
    if (retryCount > 0) {
      if (data.phase === 'failed' && retryCount >= maxRetries) {
        retrySummary = `Failed after ${retryCount}/${maxRetries} retry attempts`
      } else if (data.phase === 'failed') {
        retrySummary = `Failed (retried ${retryCount}/${maxRetries} times, can retry again)`
      } else if (['processing', 'pending', 'downloading', 'analyzing', 'extracting', 'normalizing'].includes(data.phase)) {
        retrySummary = `Retry attempt ${retryCount}/${maxRetries} in progress`
      } else {
        retrySummary = `Completed after ${retryCount} retry attempt(s)`
      }
    }

    return {
      job_id: data.job_id || '',
      supplier_id: data.supplier_id || '',
      supplier_name: data.supplier_name || 'Unknown',
      phase: (data.phase || 'downloading') as any,
      status: (data.status || 'pending') as any,
      download_progress: downloadProgress,
      analysis_progress: analysisProgress,
      file_type: (data.file_type || 'excel') as any,
      error: errorMessage,
      error_details: errorDetails,
      // T85: Include error recommendation
      error_recommendation: errorInfo.recommendation,
      error_formatted: errorMessage ? errorInfo.formatted_message : null,
      can_retry: data.can_retry === 'true' || errorInfo.recommendation.canRetry,
      retry_count: retryCount,
      max_retries: maxRetries,
      retry_summary: retrySummary,
      created_at: data.created_at || new Date().toISOString(),
      started_at: data.started_at || null,
      completed_at: data.completed_at || null,
    }
  }

  /**
   * Retry a failed job
   *
   * Validates job state and enqueues retry task to Redis for Python worker.
   *
   * @param jobId - Job UUID to retry
   * @returns RetryJobResponse with new retry count
   * @throws JobNotFoundError if job doesn't exist
   * @throws JobNotFailedError if job is not in failed state
   * @throws MaxRetriesExceededError if max retries exceeded
   * @throws RedisUnavailableError if Redis is unavailable
   */
  async retryJob(jobId: string): Promise<RetryJobResponse> {
    const redis = await this.getRedis()

    // Get job data
    const job = await this.getJob(jobId)

    if (!job) {
      const error = new Error(`Job not found: ${jobId}`) as JobNotFoundError
      error.code = 'NOT_FOUND'
      throw error
    }

    // Validate job is in failed state
    if (job.phase !== 'failed') {
      const error = new Error(
        `Job is not in failed state (current: ${job.phase})`
      ) as JobNotFailedError
      error.code = 'INVALID_STATE'
      ;(error as any).current_phase = job.phase
      throw error
    }

    // Check if job can be retried
    if (!job.can_retry) {
      const error = new Error(
        `Maximum retries (${job.max_retries}) exceeded for job ${jobId}`
      ) as MaxRetriesExceededError
      error.code = 'MAX_RETRIES_EXCEEDED'
      ;(error as any).retry_count = job.retry_count
      ;(error as any).max_retries = job.max_retries
      throw error
    }

    // Validate retry count
    if (job.retry_count >= job.max_retries) {
      const error = new Error(
        `Maximum retries (${job.max_retries}) exceeded for job ${jobId}`
      ) as MaxRetriesExceededError
      error.code = 'MAX_RETRIES_EXCEEDED'
      ;(error as any).retry_count = job.retry_count
      ;(error as any).max_retries = job.max_retries
      throw error
    }

    // Enqueue retry task to Redis
    // arq expects jobs to be added to a sorted set with format: arq:queue:{queue_name}
    const taskId = `retry-${jobId}-${Date.now()}`
    
    // Create arq-compatible job message
    const jobData = {
      function: 'retry_job_task',
      args: [],
      kwargs: {
        job_id: jobId,
      },
      job_try: 1,
      enqueue_time: Date.now() / 1000, // Unix timestamp
      queue_name: process.env.ARQ_QUEUE_NAME || 'marketbel:queue',
    }

    // Encode job for arq (uses msgpack but we'll use JSON and let arq handle it)
    // arq uses a specific format, but we can trigger via the parse:triggers pattern
    // that's already established in the codebase
    
    // Use the established retry trigger pattern
    const retryTriggerKey = 'retry:triggers'
    const triggerData = JSON.stringify({
      job_id: jobId,
      task_id: taskId,
      triggered_at: new Date().toISOString(),
    })

    // Push to retry triggers list for Python worker to pick up
    await redis.lpush(retryTriggerKey, triggerData)
    // Set TTL on the list to clean up old entries
    await redis.expire(retryTriggerKey, 3600) // 1 hour

    console.log(`Retry job ${jobId} enqueued with task ${taskId}`)

    return {
      job_id: jobId,
      status: 'retrying',
      message: `Job retry initiated (attempt ${job.retry_count + 1} of ${job.max_retries})`,
      retry_count: job.retry_count + 1,
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
export const jobService = new JobService()

