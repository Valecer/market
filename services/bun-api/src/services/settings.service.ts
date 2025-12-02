/**
 * Settings Service
 *
 * Business logic for admin settings management.
 * Stores configuration in Redis for persistence across services.
 */

import Redis from 'ioredis'
import type { MasterSheetUrlResponse, UpdateMasterSheetUrlResponse } from '../types/settings.types'

// =============================================================================
// Redis Key Constants
// =============================================================================

const MASTER_SHEET_URL_KEY = 'settings:master_sheet_url'
const MASTER_SHEET_URL_UPDATED_KEY = 'settings:master_sheet_url_updated_at'
const MASTER_SHEET_NAME_KEY = 'settings:master_sheet_name'

// =============================================================================
// Settings Service
// =============================================================================

class SettingsService {
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
      const err = new Error('Redis service is temporarily unavailable') as Error & { code: string }
      err.code = 'REDIS_UNAVAILABLE'
      throw err
    }
  }

  /**
   * Get current master sheet URL configuration
   */
  async getMasterSheetUrl(): Promise<MasterSheetUrlResponse> {
    const redis = await this.getRedis()

    const [url, sheetName, lastUpdatedAt] = await Promise.all([
      redis.get(MASTER_SHEET_URL_KEY),
      redis.get(MASTER_SHEET_NAME_KEY),
      redis.get(MASTER_SHEET_URL_UPDATED_KEY),
    ])

    // Also check environment variable as fallback
    const envUrl = process.env.MASTER_SHEET_URL
    const effectiveUrl = url || envUrl || null
    const effectiveSheetName = sheetName || 'Suppliers'

    return {
      url: effectiveUrl,
      sheet_name: effectiveSheetName,
      configured: !!effectiveUrl,
      last_updated_at: lastUpdatedAt,
    }
  }

  /**
   * Update master sheet URL and sheet name
   */
  async updateMasterSheetUrl(
    url: string,
    sheetName?: string
  ): Promise<UpdateMasterSheetUrlResponse> {
    const redis = await this.getRedis()

    const now = new Date().toISOString()
    const effectiveSheetName = sheetName || 'Suppliers'

    await Promise.all([
      redis.set(MASTER_SHEET_URL_KEY, url),
      redis.set(MASTER_SHEET_NAME_KEY, effectiveSheetName),
      redis.set(MASTER_SHEET_URL_UPDATED_KEY, now),
    ])

    return {
      url,
      sheet_name: effectiveSheetName,
      message: 'Master sheet configuration updated successfully',
    }
  }

  /**
   * Clear master sheet URL (revert to environment variable)
   */
  async clearMasterSheetUrl(): Promise<void> {
    const redis = await this.getRedis()

    await Promise.all([
      redis.del(MASTER_SHEET_URL_KEY),
      redis.del(MASTER_SHEET_NAME_KEY),
      redis.del(MASTER_SHEET_URL_UPDATED_KEY),
    ])
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
export const settingsService = new SettingsService()

