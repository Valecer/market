/**
 * API Integration Tests for Product Pricing Endpoints
 * 
 * Phase 9: Advanced Pricing & Categorization
 * 
 * Tests the admin PATCH /products/:id/pricing endpoint
 */
import { describe, test, expect, beforeAll } from 'bun:test'
import { Elysia } from 'elysia'
import jwt from '@elysiajs/jwt'
import { adminController } from '../../src/controllers/admin'
import { errorHandler } from '../../src/middleware/error-handler'

// Test fixtures
const TEST_PRODUCT_ID = '550e8400-e29b-41d4-a716-446655440000'
const INVALID_UUID = 'not-a-uuid'
const JWT_SECRET = 'test-secret-key'

// Create test app with JWT
const createTestApp = () => {
  return new Elysia()
    .use(errorHandler)
    .use(jwt({ name: 'jwt', secret: JWT_SECRET }))
    .use(adminController)
}

// Generate test JWT token
async function getAdminToken(app: Elysia): Promise<string> {
  // @ts-ignore - access jwt from context
  const token = await app.decorator.jwt.sign({
    id: 'test-admin-id',
    username: 'admin',
    role: 'admin',
  })
  return token
}

async function getSalesToken(app: Elysia): Promise<string> {
  // @ts-ignore
  const token = await app.decorator.jwt.sign({
    id: 'test-sales-id',
    username: 'sales',
    role: 'sales',
  })
  return token
}

describe('Product Pricing API (Phase 9)', () => {
  describe('PATCH /api/v1/admin/products/:id/pricing', () => {
    test('should require authentication', async () => {
      const app = createTestApp()
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ retail_price: 99.99 }),
        })
      )
      expect(res.status).toBe(401)
    })

    test('should require admin role', async () => {
      const app = createTestApp()
      const token = await getSalesToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ retail_price: 99.99 }),
        })
      )
      expect(res.status).toBe(403)
    })

    test('should validate product ID format', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${INVALID_UUID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ retail_price: 99.99 }),
        })
      )
      expect(res.status).toBe(400)
      const body = await res.json()
      expect(body.error.code).toBe('VALIDATION_ERROR')
    })

    test('should validate currency code format (lowercase rejected)', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ currency_code: 'usd' }),
        })
      )
      expect(res.status).toBe(400)
      const body = await res.json()
      expect(body.error.code).toBe('VALIDATION_ERROR')
      expect(body.error.message).toContain('uppercase')
    })

    test('should validate currency code format (wrong length rejected)', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ currency_code: 'US' }),
        })
      )
      expect(res.status).toBe(400)
    })

    test('should reject negative prices', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ retail_price: -5.00 }),
        })
      )
      expect(res.status).toBe(400)
    })

    test('should accept valid complete pricing update', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            retail_price: 99.99,
            wholesale_price: 79.99,
            currency_code: 'USD',
          }),
        })
      )
      // Will be 404 if product doesn't exist in test DB, 200 if it does
      expect([200, 404]).toContain(res.status)
    })

    test('should accept valid partial update (retail_price only)', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ retail_price: 149.99 }),
        })
      )
      expect([200, 404]).toContain(res.status)
    })

    test('should accept valid partial update (currency_code only)', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ currency_code: 'EUR' }),
        })
      )
      expect([200, 404]).toContain(res.status)
    })

    test('should accept null to clear pricing fields', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            retail_price: null,
            wholesale_price: null,
            currency_code: null,
          }),
        })
      )
      expect([200, 404]).toContain(res.status)
    })

    test('should accept zero price (free products)', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const res = await app.handle(
        new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ retail_price: 0 }),
        })
      )
      expect([200, 404]).toContain(res.status)
    })

    test('should accept common currency codes', async () => {
      const app = createTestApp()
      const token = await getAdminToken(app)
      
      const validCodes = ['USD', 'EUR', 'RUB', 'CNY', 'BYN', 'GBP', 'JPY']
      
      for (const code of validCodes) {
        const res = await app.handle(
          new Request(`http://localhost/api/v1/admin/products/${TEST_PRODUCT_ID}/pricing`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ currency_code: code }),
          })
        )
        // Should not fail validation (400), may be 404 if product doesn't exist
        expect([200, 404]).toContain(res.status)
      }
    })
  })
})
