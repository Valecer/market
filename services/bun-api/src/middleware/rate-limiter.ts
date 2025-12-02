import { Elysia } from 'elysia'
import { createErrorResponse } from '../types/errors'

/**
 * Rate Limiter Middleware
 * 
 * Implements in-memory rate limiting for sync endpoint
 * Uses sliding window algorithm: counts requests within a time window
 * 
 * Note: For production with multiple API instances, migrate to Redis-backed rate limiting
 */

interface RateLimitEntry {
  count: number
  windowStart: number
}

// In-memory store for rate limit tracking
// Key: user identifier (user ID or IP), Value: rate limit entry
const rateLimitStore = new Map<string, RateLimitEntry>()

// Clean up old entries periodically to prevent memory leaks
setInterval(() => {
  const now = Date.now()
  const windowMs = (parseInt(process.env.SYNC_RATE_LIMIT_WINDOW_SECONDS || '60', 10) * 1000)
  
  for (const [key, entry] of rateLimitStore.entries()) {
    if (now - entry.windowStart > windowMs * 2) {
      rateLimitStore.delete(key)
    }
  }
}, 60000) // Clean up every minute

/**
 * Check rate limit status for a user (read-only, does not increment)
 * @param userId - User identifier (user ID preferred, IP as fallback)
 * @param limit - Maximum requests allowed in window
 * @param windowMs - Time window in milliseconds
 * @returns Object with current status and remaining requests
 */
function getRateLimitStatus(
  userId: string,
  limit: number,
  windowMs: number
): { allowed: boolean; remaining: number; resetAt: number } {
  const now = Date.now()
  const entry = rateLimitStore.get(userId)

  if (!entry || now - entry.windowStart >= windowMs) {
    // No window or window expired - would be allowed
    return { allowed: true, remaining: limit, resetAt: now + windowMs }
  }

  if (entry.count >= limit) {
    // Rate limit exceeded
    const resetAt = entry.windowStart + windowMs
    return { allowed: false, remaining: 0, resetAt }
  }

  // Still within limit
  return { allowed: true, remaining: limit - entry.count, resetAt: entry.windowStart + windowMs }
}

/**
 * Increment rate limit counter for a user
 * @param userId - User identifier
 * @param limit - Maximum requests allowed in window
 * @param windowMs - Time window in milliseconds
 * @returns Object with status after incrementing
 */
function incrementRateLimit(
  userId: string,
  limit: number,
  windowMs: number
): { allowed: boolean; remaining: number; resetAt: number } {
  const now = Date.now()
  const entry = rateLimitStore.get(userId)

  if (!entry || now - entry.windowStart >= windowMs) {
    // Start new window
    rateLimitStore.set(userId, { count: 1, windowStart: now })
    return { allowed: true, remaining: limit - 1, resetAt: now + windowMs }
  }

  if (entry.count >= limit) {
    // Rate limit already exceeded
    const resetAt = entry.windowStart + windowMs
    return { allowed: false, remaining: 0, resetAt }
  }

  // Increment count
  entry.count++
  return { allowed: true, remaining: limit - entry.count, resetAt: entry.windowStart + windowMs }
}

/**
 * Rate limiter configuration options
 */
interface RateLimiterOptions {
  /** Maximum requests allowed per window (default: 10) */
  limit?: number
  /** Time window in seconds (default: 60) */
  windowSeconds?: number
}

/**
 * Create rate limiter middleware
 * 
 * Usage:
 * ```typescript
 * app.use(rateLimiter({ limit: 10, windowSeconds: 60 }))
 * ```
 * 
 * @param options - Rate limiter configuration
 * @returns Elysia middleware that enforces rate limits
 */
export function rateLimiter(options: RateLimiterOptions = {}) {
  const limit = options.limit ?? parseInt(process.env.SYNC_RATE_LIMIT_PER_MINUTE || '10', 10)
  const windowSeconds = options.windowSeconds ?? parseInt(process.env.SYNC_RATE_LIMIT_WINDOW_SECONDS || '60', 10)
  const windowMs = windowSeconds * 1000

  return (app: Elysia) =>
    app.derive(({ user, request, set }) => {
      // Use user ID if authenticated, otherwise fall back to IP (less reliable)
      // For sync endpoint, we always have an authenticated user
      const userId = (user as any)?.sub || 
        request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 
        request.headers.get('x-real-ip') || 
        'anonymous'

      // Get current status WITHOUT incrementing (read-only check)
      const currentStatus = getRateLimitStatus(userId, limit, windowMs)
      
      return {
        rateLimitInfo: {
          allowed: currentStatus.allowed,
          remaining: currentStatus.remaining,
          resetAt: currentStatus.resetAt,
          limit,
        },
        // Helper to check, increment, and respond with 429 if rate limited
        // Only increments when actually called by a route handler
        checkRateLimit: () => {
          // Increment counter and get updated status
          const { allowed, remaining, resetAt } = incrementRateLimit(userId, limit, windowMs)
          const resetAtDate = new Date(resetAt)
          
          if (!allowed) {
            set.status = 429
            set.headers['x-ratelimit-limit'] = String(limit)
            set.headers['x-ratelimit-remaining'] = '0'
            set.headers['x-ratelimit-reset'] = resetAtDate.toISOString()
            set.headers['retry-after'] = String(Math.ceil((resetAt - Date.now()) / 1000))
            return createErrorResponse(
              'RATE_LIMIT_EXCEEDED',
              `Rate limit exceeded. Maximum ${limit} requests per ${windowSeconds} seconds.`,
              {
                limit,
                window_seconds: windowSeconds,
                retry_after: Math.ceil((resetAt - Date.now()) / 1000),
              }
            )
          }
          
          // Set rate limit headers for successful requests
          set.headers['x-ratelimit-limit'] = String(limit)
          set.headers['x-ratelimit-remaining'] = String(remaining)
          set.headers['x-ratelimit-reset'] = resetAtDate.toISOString()
          
          return null
        },
      }
    })
}

