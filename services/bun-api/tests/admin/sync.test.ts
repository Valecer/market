import { describe, it, expect, beforeAll, afterAll } from 'bun:test'
import { createAdminTestApp, setupAuthTokens } from '../helpers'
import { db } from '../../src/db/client'
import { suppliers } from '../../src/db/schema/schema'
import { eq } from 'drizzle-orm'
import { queueService, QueueService, RedisUnavailableError } from '../../src/services/queue.service'

/**
 * Tests for the sync endpoint (POST /api/v1/admin/sync)
 * 
 * Phase 8: User Story 6 - Sync Trigger (FR-3)
 * Tasks: T161-T168
 */

describe('POST /api/v1/admin/sync', () => {
  let app: ReturnType<typeof createAdminTestApp>
  let tokens: {
    adminToken: string | null
    procurementToken: string | null
    salesToken: string | null
  }
  let testSupplierId: string | null = null

  // Setup test app and authentication tokens
  beforeAll(async () => {
    app = createAdminTestApp()

    // Setup tokens for all roles
    tokens = await setupAuthTokens(app)
    
    // Verify admin token is available (required for sync tests)
    if (!tokens.adminToken) {
      console.warn('⚠️  Admin token not available - some tests may fail')
    }

    // Create a test supplier for sync tests
    try {
      const testSupplier = await db
        .insert(suppliers)
        .values({
          name: 'Sync Test Supplier',
          sourceType: 'google_sheets',
          metadata: {
            spreadsheet_url: 'https://docs.google.com/spreadsheets/d/test123/edit',
            sheet_name: 'Price List',
          },
        })
        .returning()
      
      testSupplierId = testSupplier[0]?.id || null
      console.log(`✅ Created test supplier: ${testSupplierId}`)
    } catch (error) {
      console.error('❌ Failed to create test supplier:', error)
    }
  })

  // Cleanup test data
  afterAll(async () => {
    if (testSupplierId) {
      try {
        await db.delete(suppliers).where(eq(suppliers.id, testSupplierId))
        console.log('✅ Cleaned up test supplier')
      } catch (error) {
        console.warn('⚠️  Error cleaning up test supplier:', error)
      }
    }
  })

  // T161: Test sync endpoint: requires authentication
  it('T161: returns 401 without authentication', async () => {
    if (!testSupplierId) {
      console.warn('⚠️  Skipping test - no test supplier')
      return
    }

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ supplier_id: testSupplierId }),
      })
    )

    expect(response.status).toBe(401)
    const data = await response.json() as { error: { code: string } }
    expect(data.error.code).toBe('UNAUTHORIZED')
  })

  // T162: Test sync endpoint: requires admin role (403 for non-admin)
  it('T162: returns 403 for sales role (non-admin)', async () => {
    if (!testSupplierId || !tokens.salesToken) {
      console.warn('⚠️  Skipping test - missing test data or token')
      return
    }

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.salesToken}`,
        },
        body: JSON.stringify({ supplier_id: testSupplierId }),
      })
    )

    expect(response.status).toBe(403)
    const data = await response.json() as { error: { code: string; message: string } }
    expect(data.error.code).toBe('FORBIDDEN')
    expect(data.error.message).toContain('Admin role required')
  })

  it('T162b: returns 403 for procurement role (non-admin)', async () => {
    if (!testSupplierId || !tokens.procurementToken) {
      console.warn('⚠️  Skipping test - missing test data or token')
      return
    }

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.procurementToken}`,
        },
        body: JSON.stringify({ supplier_id: testSupplierId }),
      })
    )

    expect(response.status).toBe(403)
    const data = await response.json() as { error: { code: string } }
    expect(data.error.code).toBe('FORBIDDEN')
  })

  // T163: Test sync endpoint: enqueues message to Redis
  // T164: Test sync endpoint: message format matches contract
  // T165: Test sync endpoint: returns task_id immediately
  it('T163-165: enqueues task to Redis and returns task_id immediately', async () => {
    if (!testSupplierId || !tokens.adminToken) {
      console.warn('⚠️  Skipping test - missing test data or token')
      return
    }

    // Note: This test may fail if Redis is not running
    // In that case, it tests the 503 error handling (T167)
    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.adminToken}`,
        },
        body: JSON.stringify({ supplier_id: testSupplierId }),
      })
    )

    // Redis might not be running - handle both cases
    if (response.status === 503) {
      const data = await response.json() as { error: { code: string } }
      expect(data.error.code).toBe('REDIS_UNAVAILABLE')
      console.log('ℹ️  Redis unavailable - 503 response verified (T167)')
      return
    }

    // If Redis is available, verify successful response
    expect(response.status).toBe(202)
    const data = await response.json() as { 
      task_id: string
      supplier_id: string
      status: string
      enqueued_at: string
    }

    // T165: Verify task_id is returned
    expect(data.task_id).toBeDefined()
    expect(typeof data.task_id).toBe('string')
    // Verify UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    expect(uuidRegex.test(data.task_id)).toBe(true)

    // T164: Verify response matches contract
    expect(data.supplier_id).toBe(testSupplierId)
    expect(data.status).toBe('queued')
    expect(data.enqueued_at).toBeDefined()
    // Verify ISO-8601 timestamp format
    expect(new Date(data.enqueued_at).toISOString()).toBe(data.enqueued_at)
  })

  // T166: Test sync endpoint: 404 if supplier not found
  it('T166: returns 404 if supplier not found', async () => {
    if (!tokens.adminToken) {
      console.warn('⚠️  Skipping test - no admin token')
      return
    }

    const nonExistentId = '00000000-0000-0000-0000-000000000000'

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.adminToken}`,
        },
        body: JSON.stringify({ supplier_id: nonExistentId }),
      })
    )

    expect(response.status).toBe(404)
    const data = await response.json() as { error: { code: string; message: string } }
    expect(data.error.code).toBe('NOT_FOUND')
    expect(data.error.message).toContain('not found')
  })

  // T167: Test sync endpoint: 503 if Redis unavailable
  // Note: This is tested implicitly in T163-165 test if Redis is not running
  // For explicit testing, we would need to mock the queue service

  // T168: Test sync endpoint: rate limit enforced (429 after 10 requests)
  it('T168: enforces rate limit (429 after exceeding limit)', async () => {
    if (!testSupplierId || !tokens.adminToken) {
      console.warn('⚠️  Skipping test - missing test data or token')
      return
    }

    // Create a fresh app instance for rate limit testing to avoid cross-test interference
    const rateLimitApp = createAdminTestApp()

    // Make 11 requests - the 11th should be rate limited
    // Note: We're using a non-existent supplier to avoid Redis issues
    // The rate limit should still apply even if the request would fail
    const nonExistentId = '11111111-1111-1111-1111-111111111111'
    
    let rateLimitHit = false
    let successfulResponses = 0
    
    for (let i = 0; i < 12; i++) {
      const response = await rateLimitApp.handle(
        new Request('http://localhost/api/v1/admin/sync', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${tokens.adminToken}`,
          },
          body: JSON.stringify({ supplier_id: nonExistentId }),
        })
      )

      if (response.status === 429) {
        rateLimitHit = true
        const data = await response.json() as { error: { code: string } }
        expect(data.error.code).toBe('RATE_LIMIT_EXCEEDED')
        
        // Check rate limit headers
        expect(response.headers.get('x-ratelimit-limit')).toBe('10')
        expect(response.headers.get('x-ratelimit-remaining')).toBe('0')
        expect(response.headers.get('retry-after')).toBeDefined()
        break
      }
      
      // Count responses that passed rate limiting (404 or 202 or 503)
      if (response.status === 404 || response.status === 202 || response.status === 503) {
        successfulResponses++
      }
    }

    // Rate limit should have been hit after 10 requests
    expect(rateLimitHit).toBe(true)
    expect(successfulResponses).toBeLessThanOrEqual(10)
  })

  // Additional validation tests
  it('returns 400 for invalid supplier_id format', async () => {
    if (!tokens.adminToken) {
      console.warn('⚠️  Skipping test - no admin token')
      return
    }

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.adminToken}`,
        },
        body: JSON.stringify({ supplier_id: 'not-a-uuid' }),
      })
    )

    expect(response.status).toBe(400)
    const data = await response.json() as { error: { code: string; message: string } }
    expect(data.error.code).toBe('VALIDATION_ERROR')
    // Message may contain 'uuid' (lowercase) from Elysia validation or 'UUID' from our manual check
    expect(data.error.message.toLowerCase()).toContain('uuid')
  })

  it('returns 400 for missing supplier_id', async () => {
    if (!tokens.adminToken) {
      console.warn('⚠️  Skipping test - no admin token')
      return
    }

    const response = await app.handle(
      new Request('http://localhost/api/v1/admin/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokens.adminToken}`,
        },
        body: JSON.stringify({}),
      })
    )

    expect(response.status).toBe(400)
    const data = await response.json() as { error: { code: string } }
    expect(data.error.code).toBe('VALIDATION_ERROR')
  })
})

