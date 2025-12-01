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
} from '../types/ingestion.types'
import { supplierRepository } from '../db/repositories/supplier.repository'
import { RedisUnavailableError } from './queue.service'

// =============================================================================
// Redis Key Constants (must match Python worker sync_state.py)
// =============================================================================

const SYNC_STATUS_KEY = 'sync:status'
const SYNC_LOCK_KEY = 'sync:lock'
const SYNC_LAST_RUN_KEY = 'sync:last_run'

// Queue name for arq worker
const QUEUE_NAME = process.env.REDIS_QUEUE_NAME || 'arq:queue:price-ingestion-queue'

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

    // Check if sync is already running
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

    // Generate task ID
    const taskId = `sync-manual-${Date.now()}`
    const triggeredAt = new Date().toISOString()

    // Create queue message for Python worker
    // arq expects messages in format: {"function": "task_name", "args": [...], "kwargs": {...}}
    const message = {
      function: 'trigger_master_sync_task',
      args: [],
      kwargs: {
        task_id: taskId,
        triggered_by: 'manual',
        triggered_at: triggeredAt,
      },
      job_id: taskId,
      enqueue_time_ms: Date.now(),
    }

    // Enqueue to arq queue
    await redis.rpush(QUEUE_NAME, JSON.stringify(message))

    return {
      task_id: taskId,
      status: 'queued',
      message: 'Master sync pipeline started',
    }
  }

  /**
   * Get current ingestion pipeline status
   *
   * Retrieves sync state from Redis, supplier list from database,
   * and recent parsing logs for the admin dashboard.
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

    return {
      sync_state: syncStatus.state,
      progress:
        syncStatus.state === 'processing_suppliers'
          ? { current: syncStatus.progress_current, total: syncStatus.progress_total }
          : null,
      last_sync_at: lastSyncAt,
      next_scheduled_at: nextScheduledAt,
      suppliers,
      recent_logs: recentLogs,
    }
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
   */
  private async getSuppliersWithStatus(): Promise<SupplierStatus[]> {
    // Use repository to get suppliers with item counts
    const suppliers = await supplierRepository.findAllWithItemCounts()

    return suppliers.map((supplier) => ({
      id: supplier.id,
      name: supplier.name,
      source_type: supplier.sourceType || 'unknown',
      last_sync_at: supplier.updatedAt?.toISOString() || null,
      status: this.deriveSupplierStatus(supplier),
      items_count: supplier.itemsCount || 0,
    }))
  }

  /**
   * Derive supplier sync status from metadata
   *
   * For now, use simple logic based on existence of items.
   * In Phase 5, this will be based on parsing_logs.
   */
  private deriveSupplierStatus(supplier: {
    metadata?: Record<string, unknown> | null
    itemsCount?: number
  }): 'success' | 'error' | 'pending' | 'inactive' {
    // Check if supplier is inactive
    const isActive = supplier.metadata?.is_active !== false
    if (!isActive) {
      return 'inactive'
    }

    // If has items, assume success (simplified for Phase 3)
    // Phase 5 will implement proper status based on parsing_logs
    if (supplier.itemsCount && supplier.itemsCount > 0) {
      return 'success'
    }

    return 'pending'
  }

  /**
   * Get recent parsing logs with supplier names
   */
  private async getRecentParsingLogs(limit: number): Promise<ParsingLogEntry[]> {
    // For Phase 3, return empty array
    // Phase 5 will implement proper log retrieval via ingestion.repository.ts
    // This is intentional to keep Phase 3 scope focused on manual sync trigger
    return []
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

