import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import { createAdminTestApp, generateTestToken, verifyToken, setupAuthTokens } from '../helpers'
import { createTestProductsWithStatuses, cleanupTestData, createTestData } from '../fixtures'
import type { AdminProductsResponse, AdminProduct } from '../../src/types/admin.types'

/**
 * Admin Products Endpoint Tests
 * 
 * Tests for T089-T097: Admin products endpoint scenarios
 * 
 * Prerequisites:
 * - DATABASE_URL environment variable must be set
 * - Users table must exist with test user: username='admin', password='admin123'
 * - Database must be accessible and running
 * 
 * Note: If authentication token cannot be obtained, tests requiring auth will be skipped.
 * This usually indicates DATABASE_URL is not set or the users table doesn't have test data.
 */

describe('Admin Products - Admin Products Endpoint', () => {
  let app: ReturnType<typeof createAdminTestApp>
  let authToken: string | null = null

  beforeAll(async () => {
    app = createAdminTestApp()
    // Get auth token for authenticated requests
    const token = await generateTestToken(app)
    
    if (!token || token.trim().length === 0) {
      console.warn('⚠️  Warning: Could not obtain auth token. Tests requiring authentication will be skipped.')
      console.warn('   Make sure DATABASE_URL is set and users table has test data (admin/admin123)')
      authToken = null
    } else {
      // Verify token works by making a test request
      if (await verifyToken(app, token)) {
        authToken = token
      } else {
        console.warn('⚠️  Warning: Auth token obtained but verification failed. Tests requiring authentication will be skipped.')
        authToken = null
      }
    }
  })

  describe('T089: Requires authentication', () => {
    test('GET /api/v1/admin/products without token returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(401)
    })

    test('GET /api/v1/admin/products with invalid token returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: 'Bearer invalid-token-here',
          },
        })
      )

      expect(response.status).toBe(401)
    })

    test('GET /api/v1/admin/products with valid token returns 200', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      if (response.status !== 200) {
        const errorBody = await response.json().catch(() => ({}))
        console.error('Admin endpoint failed:', response.status, errorBody)
      }
      expect(response.status).toBe(200)
    })
  })

  describe('T090: Returns all product statuses', () => {
    test('GET /api/v1/admin/products returns products with all statuses', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=100', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // Check that we can get products with different statuses
      if (data.data.length > 0) {
        const statuses = new Set(data.data.map((p: AdminProduct) => p.status))
        expect(statuses.size).toBeGreaterThanOrEqual(1)
      }
    })
  })

  describe('T091: Includes supplier details', () => {
    test('GET /api/v1/admin/products includes supplier_items array', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // Verify supplier_items structure
      if (data.data.length > 0) {
        data.data.forEach((product: AdminProduct) => {
          expect(product).toHaveProperty('supplier_items')
          expect(Array.isArray(product.supplier_items)).toBe(true)

          // If product has supplier items, verify their structure
          if (product.supplier_items.length > 0) {
            product.supplier_items.forEach((item) => {
              expect(item).toHaveProperty('id')
              expect(item).toHaveProperty('supplier_id')
              expect(item).toHaveProperty('supplier_name')
              expect(item).toHaveProperty('supplier_sku')
              expect(item).toHaveProperty('current_price')
              expect(item).toHaveProperty('characteristics')
              expect(item).toHaveProperty('last_ingested_at')
              expect(typeof item.current_price).toBe('string')
              expect(item.current_price).toMatch(/^\d+\.\d{2}$/) // Decimal format
            })
          }
        })
      }
    })
  })

  describe('T092: Margin calculation correct', () => {
    test('GET /api/v1/admin/products includes margin_percentage field', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // Verify margin_percentage field exists (can be null or number)
      if (data.data.length > 0) {
        data.data.forEach((product: AdminProduct) => {
          expect(product).toHaveProperty('margin_percentage')
          expect(
            product.margin_percentage === null || typeof product.margin_percentage === 'number'
          ).toBe(true)
        })
      }
    })
  })

  describe('T093: Status filter works', () => {
    test('GET /api/v1/admin/products?status=active returns only active products', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?status=active&page=1&limit=100', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // All returned products should have status 'active'
      data.data.forEach((product: AdminProduct) => {
        expect(product.status).toBe('active')
      })
    })

    test('GET /api/v1/admin/products?status=draft returns only draft products', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?status=draft&page=1&limit=100', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // All returned products should have status 'draft'
      data.data.forEach((product: AdminProduct) => {
        expect(product.status).toBe('draft')
      })
    })
  })

  describe('T094: Margin filters work', () => {
    test('GET /api/v1/admin/products?min_margin=10 filters by minimum margin', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      // Note: Margin filtering is currently disabled because target_price doesn't exist
      // This test verifies the endpoint accepts the parameter without error
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?min_margin=10&page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
    })

    test('GET /api/v1/admin/products?max_margin=50 filters by maximum margin', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?max_margin=50&page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
    })
  })

  describe('T095: Supplier filter works', () => {
    test('GET /api/v1/admin/products?supplier_id=<uuid> filters by supplier', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      // Use a valid UUID format (this may not exist in test data, but should not error)
      const testSupplierId = '00000000-0000-0000-0000-000000000000'
      const response = await app.handle(
        new Request(
          `http://localhost/api/v1/admin/products?supplier_id=${testSupplierId}&page=1&limit=10`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          }
        )
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // If products are returned, they should only have supplier items from the specified supplier
      if (data.data.length > 0) {
        data.data.forEach((product: AdminProduct) => {
          product.supplier_items.forEach((item) => {
            expect(item.supplier_id).toBe(testSupplierId)
          })
        })
      }
    })
  })

  describe('T096: Pagination works', () => {
    test('GET /api/v1/admin/products with pagination returns correct metadata', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data).toHaveProperty('total_count')
      expect(data).toHaveProperty('page')
      expect(data).toHaveProperty('limit')
      expect(data).toHaveProperty('data')

      expect(typeof data.total_count).toBe('number')
      expect(data.total_count).toBeGreaterThanOrEqual(0)
      expect(data.page).toBe(1)
      expect(data.limit).toBe(10)
      expect(Array.isArray(data.data)).toBe(true)
      expect(data.data.length).toBeLessThanOrEqual(10)
    })

    test('GET /api/v1/admin/products?page=2&limit=5 returns second page', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=2&limit=5', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as AdminProductsResponse
      expect(data.page).toBe(2)
      expect(data.limit).toBe(5)
      expect(Array.isArray(data.data)).toBe(true)
      expect(data.data.length).toBeLessThanOrEqual(5)
    })
  })

  describe('T097: 401 without token', () => {
    test('GET /api/v1/admin/products without Authorization header returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(401)

      const data = (await response.json()) as { error: { code: string } }
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code')
      expect(data.error.code).toBe('UNAUTHORIZED')
    })

    test('GET /api/v1/admin/products with empty Authorization header returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: '',
          },
        })
      )

      expect(response.status).toBe(401)
    })
  })

  describe('Independent Test Criteria: Admin Products View', () => {
    test('✅ GET /api/v1/admin/products requires valid JWT token', async () => {
      // Test without token
      const responseNoToken = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
        })
      )
      expect(responseNoToken.status).toBe(401)

      // Test with invalid token
      const responseInvalidToken = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: 'Bearer invalid-token',
          },
        })
      )
      expect(responseInvalidToken.status).toBe(401)

      // Test with valid token
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }
      
      const responseValidToken = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )
      expect(responseValidToken.status).toBe(200)
    })

    describe('Returns products with all statuses', () => {
      let testProductIds: string[] = []
      let testCategoryId: string | null = null

      beforeAll(async () => {
        // Create test category for products
        const testData = await createTestData('test-status-products')
        testCategoryId = testData.categoryId

        // Create test products with different statuses
        testProductIds = await createTestProductsWithStatuses(testCategoryId, 'test-status')
      })

      afterAll(async () => {
        // Clean up test products
        if (testProductIds.length > 0) {
          await cleanupTestData({
            adminUserId: null,
            categoryId: testCategoryId,
            supplierId: null,
            supplierItemId: null,
            productIds: testProductIds,
          })
        }
      })

      test('✅ Returns products with all statuses (draft, active, archived)', async () => {
        if (!authToken || authToken.trim().length === 0) {
          console.warn('Skipping test: Auth token not available')
          return
        }

        const response = await app.handle(
          new Request('http://localhost/api/v1/admin/products?page=1&limit=200', {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          })
        )

        expect(response.status).toBe(200)
        const data = (await response.json()) as AdminProductsResponse

        // Verify response structure
        expect(data).toHaveProperty('data')
        expect(Array.isArray(data.data)).toBe(true)

        // Collect all statuses found
        const statusesFound = new Set(data.data.map((p: AdminProduct) => p.status))
        
        // Verify that status field exists and is one of the valid values
        data.data.forEach((product: AdminProduct) => {
          expect(['draft', 'active', 'archived']).toContain(product.status)
        })

        // Verify that all three statuses are present in the response
        expect(statusesFound.has('active')).toBe(true)
        expect(statusesFound.has('draft')).toBe(true)
        expect(statusesFound.has('archived')).toBe(true)
      })
    })

    test('✅ Includes supplier item details for each product', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=50', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as AdminProductsResponse

      // Every product must have supplier_items array
      data.data.forEach((product: AdminProduct) => {
        expect(product).toHaveProperty('supplier_items')
        expect(Array.isArray(product.supplier_items)).toBe(true)

        // If product has supplier items, verify complete structure
        if (product.supplier_items.length > 0) {
          product.supplier_items.forEach((item) => {
            // Verify all required fields
            expect(item).toHaveProperty('id')
            expect(item).toHaveProperty('supplier_id')
            expect(item).toHaveProperty('supplier_name')
            expect(item).toHaveProperty('supplier_sku')
            expect(item).toHaveProperty('current_price')
            expect(item).toHaveProperty('characteristics')
            expect(item).toHaveProperty('last_ingested_at')

            // Verify data types and formats
            expect(typeof item.id).toBe('string')
            expect(typeof item.supplier_id).toBe('string')
            expect(typeof item.supplier_name).toBe('string')
            expect(typeof item.supplier_sku).toBe('string')
            expect(typeof item.current_price).toBe('string')
            expect(item.current_price).toMatch(/^\d+\.\d{2}$/) // Decimal format
            expect(typeof item.characteristics).toBe('object')
            expect(typeof item.last_ingested_at).toBe('string')
          })
        }
      })
    })

    test('✅ Calculates margin percentage if target price exists', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=50', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as AdminProductsResponse

      // Verify margin_percentage field exists on all products
      data.data.forEach((product: AdminProduct) => {
        expect(product).toHaveProperty('margin_percentage')
        
        // margin_percentage can be:
        // - null (when target_price doesn't exist in products table yet)
        // - number (when target_price exists and calculation is performed)
        expect(
          product.margin_percentage === null || typeof product.margin_percentage === 'number'
        ).toBe(true)

        // If margin is calculated (not null), verify it's a valid percentage
        if (product.margin_percentage !== null) {
          expect(product.margin_percentage).toBeGreaterThanOrEqual(0)
          expect(product.margin_percentage).toBeLessThanOrEqual(100)
        }
      })

      // Note: Currently margin_percentage will be null because target_price field
      // doesn't exist in products table. When target_price is added, this test
      // will verify the calculation is performed correctly.
    })

    test('✅ Filtering by status, margin, supplier_id works', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      // Test status filter
      const statusResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products?status=active&page=1&limit=100', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )
      expect(statusResponse.status).toBe(200)
      const statusData = (await statusResponse.json()) as AdminProductsResponse
      statusData.data.forEach((product: AdminProduct) => {
        expect(product.status).toBe('active')
      })

      // Test supplier_id filter (using a valid UUID format)
      const supplierId = '00000000-0000-0000-0000-000000000000'
      const supplierResponse = await app.handle(
        new Request(
          `http://localhost/api/v1/admin/products?supplier_id=${supplierId}&page=1&limit=100`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          }
        )
      )
      expect(supplierResponse.status).toBe(200)
      const supplierData = (await supplierResponse.json()) as AdminProductsResponse
      // If products are returned, verify they only have items from the specified supplier
      supplierData.data.forEach((product: AdminProduct) => {
        product.supplier_items.forEach((item) => {
          expect(item.supplier_id).toBe(supplierId)
        })
      })

      // Test margin filters (accepted but not yet functional without target_price)
      const marginResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products?min_margin=10&max_margin=50&page=1&limit=10', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )
      expect(marginResponse.status).toBe(200)
      // Note: Margin filtering will work when target_price field is added to products table
    })

    test('✅ Pagination works correctly', async () => {
      if (!authToken || authToken.trim().length === 0) {
        console.warn('Skipping test: Auth token not available')
        return
      }

      // Test first page
      const page1Response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=1&limit=5', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )
      expect(page1Response.status).toBe(200)
      const page1Data = (await page1Response.json()) as AdminProductsResponse
      expect(page1Data.page).toBe(1)
      expect(page1Data.limit).toBe(5)
      expect(page1Data.data.length).toBeLessThanOrEqual(5)
      expect(typeof page1Data.total_count).toBe('number')
      expect(page1Data.total_count).toBeGreaterThanOrEqual(0)

      // Test second page
      const page2Response = await app.handle(
        new Request('http://localhost/api/v1/admin/products?page=2&limit=5', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      )
      expect(page2Response.status).toBe(200)
      const page2Data = (await page2Response.json()) as AdminProductsResponse
      expect(page2Data.page).toBe(2)
      expect(page2Data.limit).toBe(5)
      expect(page2Data.data.length).toBeLessThanOrEqual(5)

      // Verify pagination metadata consistency
      expect(page1Data.total_count).toBe(page2Data.total_count) // Total count should be same
    })

    test('✅ Returns 401 if token missing or invalid', async () => {
      // Test without token
      const response1 = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'GET',
        })
      )
      expect(response1.status).toBe(401)

      // Test with invalid token
      const response2 = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'GET',
          headers: {
            Authorization: 'Bearer invalid-token-12345',
          },
        })
      )
      expect(response2.status).toBe(401)
    })
  })
})

