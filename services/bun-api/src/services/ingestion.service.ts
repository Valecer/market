/**
 * Ingestion Service
 *
 * Business logic for the Admin Control Panel & Master Sync Scheduler feature.
 * Handles sync trigger, status retrieval, and coordination with Redis state.
 *
 * @see /specs/006-admin-sync-scheduler/plan.md
 */

import Redis from 'ioredis'
import type {
  TriggerSyncResponse,
  IngestionStatusResponse,
  SyncState,
  SupplierStatus,
  ParsingLogEntry,
  TriggerMasterSyncMessage,
  IngestionJob,
  JobPhase,
  JobStatus,
} from '../types/ingestion.types'
import { ingestionRepository } from '../db/repositories/ingestion.repository'
import { RedisUnavailableError } from './queue.service'

// =============================================================================
// Redis Key Constants (must match Python worker sync_state.py)
// =============================================================================

const SYNC_STATUS_KEY = 'sync:status'
const SYNC_LOCK_KEY = 'sync:lock'
const SYNC_LAST_RUN_KEY = 'sync:last_run'
const SYNC_TRIGGER_KEY = 'sync:trigger'

// Job state keys (must match Python worker job_state.py)
const JOB_KEY_PREFIX = 'job:'
const JOB_LIST_KEY = 'jobs:active'

// Default sync interval (from env or 8 hours)
const SYNC_INTERVAL_HOURS = parseInt(process.env.SYNC_INTERVAL_HOURS || '8', 10)

// =============================================================================
// Types for Redis sync status (from Python worker)
// =============================================================================

interface RedisSyncStatus {
  state: SyncState
  task_id: string | null
  started_at: string | null
  progress_current: number
  progress_total: number
}

// =============================================================================
// Ingestion Service
// =============================================================================

export class IngestionService {
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
   * Trigger the master sync pipeline
   *
   * Enqueues a trigger_master_sync_task to Redis for the Python worker.
   * Returns 409 SYNC_IN_PROGRESS if a sync is already running.
   *
   * @returns TriggerSyncResponse with task_id
   * @throws RedisUnavailableError if Redis is unavailable
   * @throws Error with code SYNC_IN_PROGRESS if sync is already running
   */
  async triggerSync(): Promise<TriggerSyncResponse> {
    const redis = await this.getRedis()

    // Check if sync is already running (check both lock and pending trigger)
    const currentLock = await redis.get(SYNC_LOCK_KEY)
    if (currentLock) {
      const error = new Error('A sync operation is already in progress') as Error & {
        code: string
        current_task_id: string
      }
      error.code = 'SYNC_IN_PROGRESS'
      error.current_task_id = currentLock
      throw error
    }

    // Check if there's already a pending trigger
    const pendingTrigger = await redis.get(SYNC_TRIGGER_KEY)
    if (pendingTrigger) {
      const trigger = JSON.parse(pendingTrigger)
      const error = new Error('A sync request is already pending') as Error & {
        code: string
        current_task_id: string
      }
      error.code = 'SYNC_IN_PROGRESS'
      error.current_task_id = trigger.task_id || 'pending'
      throw error
    }

    // Generate task ID
    const taskId = `sync-manual-${Date.now()}`
    const triggeredAt = new Date().toISOString()

    // Set trigger key for Python worker to pick up
    // Uses SET NX to prevent overwriting (5 minute TTL for auto-cleanup)
    const triggerData = {
      task_id: taskId,
      triggered_by: 'manual',
      triggered_at: triggeredAt,
    }

    const result = await redis.set(SYNC_TRIGGER_KEY, JSON.stringify(triggerData), 'EX', 300, 'NX')

    if (!result) {
      // Another trigger was set between our check and this set
      const error = new Error('A sync request is already pending') as Error & {
        code: string
        current_task_id: string
      }
      error.code = 'SYNC_IN_PROGRESS'
      error.current_task_id = taskId
      throw error
    }

    return {
      task_id: taskId,
      status: 'queued',
      message: 'Master sync pipeline started (will begin within 1 minute)',
    }
  }

  /**
   * Get current ingestion pipeline status
   *
   * Retrieves sync state from Redis, supplier list from database,
   * recent parsing logs, and active jobs for the admin dashboard.
   *
   * @param logLimit Maximum number of recent logs to return (default 50)
   * @returns IngestionStatusResponse with full pipeline status
   */
  async getStatus(logLimit: number = 50): Promise<IngestionStatusResponse> {
    const redis = await this.getRedis()

    // Get sync status from Redis
    const syncStatusJson = await redis.get(SYNC_STATUS_KEY)
    let syncStatus: RedisSyncStatus = {
      state: 'idle',
      task_id: null,
      started_at: null,
      progress_current: 0,
      progress_total: 0,
    }

    if (syncStatusJson) {
      try {
        syncStatus = JSON.parse(syncStatusJson)
      } catch (e) {
        // Invalid JSON, use default idle state
      }
    }

    // Get last sync timestamp from Redis
    const lastSyncAt = await redis.get(SYNC_LAST_RUN_KEY)

    // Calculate next scheduled sync
    const nextScheduledAt = this.calculateNextScheduledSync(lastSyncAt)

    // Get suppliers with status from database
    const suppliers = await this.getSuppliersWithStatus()

    // Get recent parsing logs
    const recentLogs = await this.getRecentParsingLogs(logLimit)

    // Get active and recent jobs from Redis (Phase 8)
    const jobs = await this.getJobsFromRedis(redis, 20)

    // Determine current phase from active jobs
    const currentPhase = this.determineCurrentPhase(jobs)

    return {
      sync_state: syncStatus.state,
      current_phase: currentPhase,
      progress:
        syncStatus.state === 'processing_suppliers'
          ? { current: syncStatus.progress_current, total: syncStatus.progress_total }
          : null,
      last_sync_at: lastSyncAt,
      next_scheduled_at: nextScheduledAt,
      jobs,
      suppliers,
      recent_logs: recentLogs,
    }
  }

  /**
   * Get jobs from Redis
   *
   * Retrieves active and recent jobs from Redis for status display.
   */
  private async getJobsFromRedis(redis: Redis, limit: number = 20): Promise<IngestionJob[]> {
    const jobs: IngestionJob[] = []

    try {
      // Get active job IDs
      const activeJobIds = await redis.smembers(JOB_LIST_KEY)

      // Get job data for each active job
      for (const jobId of activeJobIds) {
        const jobIdStr = typeof jobId === 'string' ? jobId : jobId.toString()
        const jobData = await redis.hgetall(`${JOB_KEY_PREFIX}${jobIdStr}`)

        if (jobData && Object.keys(jobData).length > 0) {
          const job = this.parseJobData(jobData)
          if (job) {
            jobs.push(job)
          }
        }
      }

      // If we don't have enough jobs, scan for recent completed jobs
      if (jobs.length < limit) {
        const scanCount = Math.min(limit * 2, 100)
        let cursor = '0'
        let scanned = 0

        do {
          const [newCursor, keys] = await redis.scan(
            cursor,
            'MATCH',
            `${JOB_KEY_PREFIX}*`,
            'COUNT',
            50
          )
          cursor = newCursor

          for (const key of keys) {
            const jobId = key.replace(JOB_KEY_PREFIX, '')
            
            // Skip if already in list
            if (jobs.some((j) => j.job_id === jobId)) {
              continue
            }

            const jobData = await redis.hgetall(key)
            if (jobData && Object.keys(jobData).length > 0) {
              const job = this.parseJobData(jobData)
              if (job) {
                jobs.push(job)
              }
            }

            if (jobs.length >= limit * 2) break
          }

          scanned += keys.length
        } while (cursor !== '0' && scanned < scanCount)
      }

      // Sort by created_at descending
      jobs.sort((a, b) => {
        const aDate = new Date(a.created_at).getTime()
        const bDate = new Date(b.created_at).getTime()
        return bDate - aDate
      })

      return jobs.slice(0, limit)
    } catch (error) {
      console.error('Error fetching jobs from Redis:', error)
      return []
    }
  }

  /**
   * Parse raw Redis hash data into IngestionJob
   */
  private parseJobData(data: Record<string, string>): IngestionJob | null {
    try {
      const phase = (data.phase || 'downloading') as JobPhase
      const status = (data.status || 'pending') as JobStatus
      const fileType = (data.file_type || 'excel') as 'excel' | 'csv' | 'pdf'

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
      const downloadProgress = downloadTotal > 0 || downloadBytes > 0
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
      const analysisProgress = itemsTotal > 0 || itemsProcessed > 0
        ? {
            items_processed: itemsProcessed,
            items_total: itemsTotal,
            matches_found: matchesFound,
            review_queue: reviewQueue,
            errors: errorCount,
            percentage: itemsTotal > 0 ? Math.round((itemsProcessed / itemsTotal) * 100) : 0,
          }
        : null

      return {
        job_id: data.job_id || '',
        supplier_id: data.supplier_id || '',
        supplier_name: data.supplier_name || 'Unknown',
        phase,
        status,
        download_progress: downloadProgress,
        analysis_progress: analysisProgress,
        file_type: fileType,
        error: data.error || null,
        error_details: errorDetails,
        can_retry: data.can_retry === 'true',
        retry_count: parseInt(data.retry_count || '0', 10),
        max_retries: parseInt(data.max_retries || '3', 10),
        created_at: data.created_at || new Date().toISOString(),
        started_at: data.started_at || null,
        completed_at: data.completed_at || null,
      }
    } catch (error) {
      console.error('Error parsing job data:', error, data)
      return null
    }
  }

  /**
   * Determine current phase from active jobs
   */
  private determineCurrentPhase(jobs: IngestionJob[]): JobPhase | null {
    // Find any job that's actively processing
    const activeJob = jobs.find(
      (j) => j.status === 'processing' || j.status === 'pending'
    )

    if (activeJob) {
      return activeJob.phase
    }

    return null
  }

  /**
   * Calculate next scheduled sync timestamp
   *
   * Based on last sync time + SYNC_INTERVAL_HOURS.
   * If never synced, returns current time + interval.
   */
  private calculateNextScheduledSync(lastSyncAt: string | null): string {
    const intervalMs = SYNC_INTERVAL_HOURS * 60 * 60 * 1000
    const baseTime = lastSyncAt ? new Date(lastSyncAt).getTime() : Date.now()
    const nextTime = new Date(baseTime + intervalMs)

    // If next scheduled time is in the past, calculate from now
    if (nextTime.getTime() < Date.now()) {
      return new Date(Date.now() + intervalMs).toISOString()
    }

    return nextTime.toISOString()
  }

  /**
   * Get all suppliers with their sync status
   *
   * Uses ingestion repository to derive status from parsing_logs.
   * Includes use_ml_processing flag from supplier metadata.
   */
  private async getSuppliersWithStatus(): Promise<SupplierStatus[]> {
    const suppliers = await ingestionRepository.getSuppliersWithStatus()

    return suppliers.map((supplier) => {
      // Extract use_ml_processing from metadata (default to true)
      const metadata = (supplier as any).metadata as Record<string, unknown> | undefined
      const useMlProcessing = metadata?.use_ml_processing !== false

      return {
        id: supplier.id,
        name: supplier.name,
        source_type: supplier.sourceType || 'unknown',
        last_sync_at: supplier.lastSyncAt,
        status: supplier.status,
        items_count: supplier.itemsCount,
        use_ml_processing: useMlProcessing,
      }
    })
  }

  /**
   * Get recent parsing logs with supplier names
   *
   * Uses ingestion repository to join logs with suppliers for context.
   */
  private async getRecentParsingLogs(limit: number): Promise<ParsingLogEntry[]> {
    const logs = await ingestionRepository.getRecentParsingLogs(limit)

    return logs.map((log) => ({
      id: log.id,
      task_id: log.taskId,
      supplier_id: log.supplierId,
      supplier_name: log.supplierName,
      error_type: log.errorType,
      error_message: log.errorMessage,
      row_number: log.rowNumber,
      created_at: log.createdAt,
    }))
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
export const ingestionService = new IngestionService()

