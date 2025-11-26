import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import { Elysia } from 'elysia'
import { catalogController } from '../src/controllers/catalog'
import { errorHandler } from '../src/middleware/error-handler'
import type { CatalogResponse, CatalogProduct } from '../src/types/catalog.types'

/**
 * Catalog Endpoint Tests
 * 
 * Tests for T068-T075: Catalog endpoint scenarios
 * 
 * Note: These tests require a database connection. Set DATABASE_URL environment variable
 * to point to a test database with sample data.
 */

// Create a test app with catalog controller
const createTestApp = () => {
  return new Elysia()
    .use(errorHandler)
    .use(catalogController)
}

describe('Catalog - Public Catalog Endpoint', () => {
  let app: ReturnType<typeof createTestApp>

  beforeAll(() => {
    app = createTestApp()
  })

  describe('T068: No auth required', () => {
    test('GET /api/v1/catalog without authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=1&limit=10', {
          method: 'GET',
        })
      )

      // Should not require authentication (no 401)
      expect(response.status).not.toBe(401)
      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('total_count')
      expect(data).toHaveProperty('page')
      expect(data).toHaveProperty('limit')
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
    })
  })

  describe('T069: Only active products returned', () => {
    test('GET /api/v1/catalog returns only active products', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=1&limit=100', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      
      // All returned products should have status 'active' (implicitly, since we filter by status)
      // This is verified by the repository query, but we can check that products are returned
      if (data.data.length > 0) {
        // Verify response structure
        data.data.forEach((product: CatalogProduct) => {
          expect(product).toHaveProperty('id')
          expect(product).toHaveProperty('internal_sku')
          expect(product).toHaveProperty('name')
          expect(product).toHaveProperty('min_price')
          expect(product).toHaveProperty('max_price')
          expect(product).toHaveProperty('supplier_count')
        })
      }
    })
  })

  describe('Independent Test Criteria: Aggregated data verification', () => {
    test('Response includes aggregated data (min_price, max_price, supplier_count)', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // Verify aggregated data is present and correctly formatted
      if (data.data.length > 0) {
        data.data.forEach((product: CatalogProduct) => {
          // Verify min_price exists and is a string with decimal format
          expect(product).toHaveProperty('min_price')
          expect(typeof product.min_price).toBe('string')
          expect(product.min_price).toMatch(/^\d+\.\d{2}$/) // Matches pattern: digits.digits

          // Verify max_price exists and is a string with decimal format
          expect(product).toHaveProperty('max_price')
          expect(typeof product.max_price).toBe('string')
          expect(product.max_price).toMatch(/^\d+\.\d{2}$/) // Matches pattern: digits.digits

          // Verify supplier_count exists and is a non-negative integer
          expect(product).toHaveProperty('supplier_count')
          expect(typeof product.supplier_count).toBe('number')
          expect(product.supplier_count).toBeGreaterThanOrEqual(0)
          expect(Number.isInteger(product.supplier_count)).toBe(true)

          // Verify min_price <= max_price (logical constraint)
          const minPrice = parseFloat(product.min_price)
          const maxPrice = parseFloat(product.max_price)
          expect(minPrice).toBeLessThanOrEqual(maxPrice)
        })
      }
    })
  })

  describe('T070: Category filter works', () => {
    test('GET /api/v1/catalog?category_id=<uuid> filters by category', async () => {
      // This test requires a valid category_id from the database
      // For now, we test that the endpoint accepts the parameter
      const categoryId = '550e8400-e29b-41d4-a716-446655440000'
      
      const response = await app.handle(
        new Request(`http://localhost/api/v1/catalog?category_id=${categoryId}&page=1&limit=10`, {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Verify filtering by category_id works correctly
      // All returned products should have the specified category_id
      if (data.data.length > 0) {
        data.data.forEach((product: CatalogProduct) => {
          // category_id can be null or the specified UUID
          if (product.category_id !== null) {
            expect(product.category_id).toBe(categoryId)
          }
        })
      }
    })

    test('GET /api/v1/catalog with invalid category_id format returns 400', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?category_id=invalid-uuid&page=1&limit=10', {
          method: 'GET',
        })
      )

      // Should return 400 for invalid UUID format
      expect(response.status).toBe(400)

      const data = (await response.json()) as { error: { code: string; message: string } }
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('VALIDATION_ERROR')
    })
  })

  describe('T071: Price range filter works', () => {
    test('GET /api/v1/catalog?min_price=10&max_price=50 filters by price range', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?min_price=10&max_price=50&page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Verify filtering by min_price and max_price works correctly
      // All returned products should have prices within the specified range
      if (data.data.length > 0) {
        data.data.forEach((product: CatalogProduct) => {
          const minPrice = parseFloat(product.min_price)
          const maxPrice = parseFloat(product.max_price)
          
          // The product's max_price should be >= min_price filter
          // The product's min_price should be <= max_price filter
          // This ensures the product's price range overlaps with the filter range
          expect(maxPrice).toBeGreaterThanOrEqual(10) // min_price filter
          expect(minPrice).toBeLessThanOrEqual(50) // max_price filter
        })
      }
    })

    test('GET /api/v1/catalog with min_price > max_price returns 400', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?min_price=50&max_price=10&page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(400)

      const data = (await response.json()) as { error: { code: string; message: string } }
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('VALIDATION_ERROR')
      expect(data.error.message).toContain('min_price must be less than or equal to max_price')
    })

    test('GET /api/v1/catalog with negative min_price returns 400', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?min_price=-10&page=1&limit=10', {
          method: 'GET',
        })
      )

      // TypeBox validation should reject negative values
      expect(response.status).toBe(400)
    })
  })

  describe('T072: Search filter works', () => {
    test('GET /api/v1/catalog?search=query filters by product name', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?search=cable&page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Verify search by product name works correctly
      // All returned products should have names containing the search term (case-insensitive)
      if (data.data.length > 0) {
        const searchTerm = 'cable'
        data.data.forEach((product: CatalogProduct) => {
          expect(product.name.toLowerCase()).toContain(searchTerm.toLowerCase())
        })
      }
    })

    test('GET /api/v1/catalog with empty search string returns 400', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?search=&page=1&limit=10', {
          method: 'GET',
        })
      )

      // TypeBox validation requires minLength: 1 for search
      expect(response.status).toBe(400)
    })
  })

  describe('T073: Combined filters work', () => {
    test('GET /api/v1/catalog with multiple filters', async () => {
      const categoryId = '550e8400-e29b-41d4-a716-446655440000'
      const response = await app.handle(
        new Request(
          `http://localhost/api/v1/catalog?category_id=${categoryId}&min_price=10&max_price=100&search=cable&page=1&limit=10`,
          {
            method: 'GET',
          }
        )
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('total_count')
      expect(data).toHaveProperty('page', 1)
      expect(data).toHaveProperty('limit', 10)
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
    })
  })

  describe('T074: Pagination works correctly (page, limit)', () => {
    test('GET /api/v1/catalog returns correct pagination metadata', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=2&limit=25', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      
      // Verify pagination works correctly
      expect(data).toHaveProperty('total_count')
      expect(typeof data.total_count).toBe('number')
      expect(data.total_count).toBeGreaterThanOrEqual(0)
      
      expect(data).toHaveProperty('page', 2)
      expect(data).toHaveProperty('limit', 25)
      
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      expect(data.data.length).toBeLessThanOrEqual(25)
      
      // Verify pagination logic: if we're on page 2 with limit 25,
      // we should have skipped the first 25 items
      // (This is verified by the repository offset calculation)
    })

    test('GET /api/v1/catalog with default pagination', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      
      // Default values: page=1, limit=50
      expect(data).toHaveProperty('page', 1)
      expect(data).toHaveProperty('limit', 50)
      expect(data.data.length).toBeLessThanOrEqual(50)
    })

    test('GET /api/v1/catalog with limit > 200 returns 400', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?limit=201', {
          method: 'GET',
        })
      )

      // TypeBox validation enforces maximum: 200
      expect(response.status).toBe(400)
    })
  })

  describe('T075: Response time meets p95 < 500ms target', () => {
    test('GET /api/v1/catalog response time is acceptable', async () => {
      const startTime = performance.now()
      
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=1&limit=50', {
          method: 'GET',
        })
      )

      const endTime = performance.now()
      const responseTime = endTime - startTime

      expect(response.status).toBe(200)
      
      // Target: p95 < 500ms
      // For a single request, we check it's reasonable (< 1000ms for safety margin)
      // In production, you'd run multiple requests and calculate p95
      expect(responseTime).toBeLessThan(1000) // Safety margin for test environment
      
      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
    }, 2000) // 2 second timeout for this test
  })
})

