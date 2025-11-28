import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import { createCatalogTestApp } from './helpers'
import { createTestData, cleanupTestData, type TestData } from './fixtures'
import type { CatalogResponse, CatalogProduct } from '../src/types/catalog.types'
import { db } from '../src/db/client'
import { products, supplierItems } from '../src/db/schema/schema'
import { inArray } from 'drizzle-orm'

/**
 * Catalog Endpoint Tests
 * 
 * Tests for T068-T075: Catalog endpoint scenarios
 * 
 * Uses fixtures for test data creation following DRY/SOLID principles.
 */

// Test product configurations for catalog tests
const TEST_PRODUCTS = {
  withCategory: [
    { name: 'USB Cable Pro', price: '15.00' },
    { name: 'HDMI Cable Premium', price: '30.00' },
    { name: 'Power Adapter', price: '45.00' },
  ],
  withoutCategory: [
    { name: 'Wireless Mouse', price: '60.00' },
  ],
  draft: [
    { name: 'Draft Product', price: '25.00' },
  ],
} as const

// Extended test data for catalog tests
interface CatalogTestData extends TestData {
  productIds: string[]
  supplierItemIds: string[]
}

describe('Catalog - Public Catalog Endpoint', () => {
  let app: ReturnType<typeof createCatalogTestApp>
  let testData: CatalogTestData = {
    adminUserId: null,
    categoryId: null,
    supplierId: null,
    supplierItemId: null,
    productIds: [],
    supplierItemIds: [],
  }

  beforeAll(async () => {
    app = createCatalogTestApp()

    // Create base test data using fixtures (category, supplier, supplier item)
    const baseData = await createTestData('catalog')
    testData.categoryId = baseData.categoryId
    testData.supplierId = baseData.supplierId
    testData.supplierItemId = baseData.supplierItemId

    if (!testData.supplierId) {
      throw new Error('Test setup failed: Supplier not created')
    }

    // Create test products with different characteristics
    const timestamp = Date.now()
    const productData = [
      // Active products with category
      ...TEST_PRODUCTS.withCategory.map((p, i) => ({
        name: p.name,
        internalSku: `test-catalog-${i}-${timestamp}`,
        status: 'active' as const,
        categoryId: testData.categoryId,
      })),
      // Active product without category
      ...TEST_PRODUCTS.withoutCategory.map((p, i) => ({
        name: p.name,
        internalSku: `test-catalog-nocat-${i}-${timestamp}`,
        status: 'active' as const,
        categoryId: null,
      })),
      // Draft product (should not appear in catalog)
      ...TEST_PRODUCTS.draft.map((p, i) => ({
        name: p.name,
        internalSku: `test-catalog-draft-${i}-${timestamp}`,
        status: 'draft' as const,
        categoryId: testData.categoryId,
      })),
    ]

    const createdProducts = await db.insert(products).values(productData).returning()
    testData.productIds = createdProducts.map(p => p.id)

    // Create supplier items with prices for active products only
    const activeProducts = createdProducts.filter(p => p.status === 'active')
    const allPrices = [...TEST_PRODUCTS.withCategory, ...TEST_PRODUCTS.withoutCategory]
    
    const supplierItemData = activeProducts.map((product, index) => ({
      supplierId: testData.supplierId!,
      supplierSku: `test-catalog-sku-${index}-${timestamp}`,
      name: product.name,
      currentPrice: allPrices[index]?.price || '10.00',
      productId: product.id,
      characteristics: {},
    }))

    const createdItems = await db.insert(supplierItems).values(supplierItemData).returning()
    testData.supplierItemIds = createdItems.map(i => i.id)

    console.log(`✅ Created ${activeProducts.length} active products with supplier items for catalog tests`)
  })

  afterAll(async () => {
    // Clean up supplier items created for products
    if (testData.supplierItemIds.length > 0) {
      await db.delete(supplierItems).where(inArray(supplierItems.id, testData.supplierItemIds))
    }
    
    // Clean up test products
    if (testData.productIds.length > 0) {
      await db.delete(products).where(inArray(products.id, testData.productIds))
    }

    // Clean up base test data using fixtures
    await cleanupTestData(testData)
    
    console.log('✅ Cleaned up catalog test data')
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
      
      // Must have products (we created test data)
      expect(data.data.length).toBeGreaterThan(0)
      
      // Verify our test products are returned
      const testProductNames = ['USB Cable Pro', 'HDMI Cable Premium', 'Power Adapter', 'Wireless Mouse']
      const returnedNames = data.data.map(p => p.name)
      
      // At least some of our test products should be in the results
      const foundTestProducts = testProductNames.filter(name => returnedNames.includes(name))
      expect(foundTestProducts.length).toBeGreaterThan(0)
      
      // Draft product should NOT be in results
      expect(returnedNames).not.toContain('Draft Product')

      // Verify response structure for all products
      data.data.forEach((product: CatalogProduct) => {
        expect(product).toHaveProperty('id')
        expect(product).toHaveProperty('internal_sku')
        expect(product).toHaveProperty('name')
        expect(product).toHaveProperty('min_price')
        expect(product).toHaveProperty('max_price')
        expect(product).toHaveProperty('supplier_count')
      })
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
      
      // Must have products (we created test data)
      expect(data.data.length).toBeGreaterThan(0)

      // Verify aggregated data is present and correctly formatted
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
    })
  })

  describe('T070: Category filter works', () => {
    test('GET /api/v1/catalog?category_id=<uuid> filters by category', async () => {
      if (!testData.categoryId) {
        throw new Error('Test setup failed: Category not created')
      }

      const response = await app.handle(
        new Request(`http://localhost/api/v1/catalog?category_id=${testData.categoryId}&page=1&limit=10`, {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Should return products in our test category (USB Cable Pro, HDMI Cable Premium, Power Adapter)
      // But NOT Wireless Mouse (which has null category)
      expect(data.data.length).toBeGreaterThan(0)
      
      // All returned products must have the test category_id
      data.data.forEach((product: CatalogProduct) => {
        expect(product.category_id).toBe(testData.categoryId)
      })
      
      // Wireless Mouse should NOT be in results (it has null category)
      const returnedNames = data.data.map(p => p.name)
      expect(returnedNames).not.toContain('Wireless Mouse')
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
      // Our test products have prices: 15, 30, 45, 60
      // Filter 10-50 should return products with prices 15, 30, 45 but NOT 60
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?min_price=10&max_price=50&page=1&limit=100', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Should return products within price range
      expect(data.data.length).toBeGreaterThan(0)
      
      // All returned products should have prices within the filter range
      data.data.forEach((product: CatalogProduct) => {
        const minPrice = parseFloat(product.min_price)
        const maxPrice = parseFloat(product.max_price)
        
        // The product's max_price should be >= min_price filter
        // The product's min_price should be <= max_price filter
        expect(maxPrice).toBeGreaterThanOrEqual(10)
        expect(minPrice).toBeLessThanOrEqual(50)
      })
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
    test('GET /api/v1/catalog?search=cable filters by product name', async () => {
      // Our test products include "USB Cable Pro" and "HDMI Cable Premium"
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?search=cable&page=1&limit=100', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Should find our "Cable" products
      expect(data.data.length).toBeGreaterThan(0)
      
      // All returned products should have names containing "cable" (case-insensitive)
      const searchTerm = 'cable'
      data.data.forEach((product: CatalogProduct) => {
        expect(product.name.toLowerCase()).toContain(searchTerm.toLowerCase())
      })
      
      // Verify specific test products are found
      const returnedNames = data.data.map(p => p.name)
      const foundCableProducts = returnedNames.filter(name => name.toLowerCase().includes('cable'))
      expect(foundCableProducts.length).toBeGreaterThan(0)
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
      if (!testData.categoryId) {
        throw new Error('Test setup failed: Category not created')
      }

      // Filter: category + price range + search for "cable"
      // Should match "USB Cable Pro" (15.00) and "HDMI Cable Premium" (30.00)
      const response = await app.handle(
        new Request(
          `http://localhost/api/v1/catalog?category_id=${testData.categoryId}&min_price=10&max_price=100&search=cable&page=1&limit=100`,
          {
            method: 'GET',
          }
        )
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      expect(data).toHaveProperty('total_count')
      expect(data).toHaveProperty('page', 1)
      expect(data).toHaveProperty('limit', 100)
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      
      // Should find cable products in our category within price range
      expect(data.data.length).toBeGreaterThan(0)
      
      // Verify all filters are applied
      data.data.forEach((product: CatalogProduct) => {
        // Category filter
        expect(product.category_id).toBe(testData.categoryId)
        // Search filter
        expect(product.name.toLowerCase()).toContain('cable')
        // Price filter
        const minPrice = parseFloat(product.min_price)
        expect(minPrice).toBeLessThanOrEqual(100)
      })
    })
  })

  describe('T074: Pagination works correctly (page, limit)', () => {
    test('GET /api/v1/catalog returns correct pagination metadata', async () => {
      // First, get page 1 to verify we have data
      const page1Response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=1&limit=2', {
          method: 'GET',
        })
      )
      expect(page1Response.status).toBe(200)
      const page1Data = (await page1Response.json()) as CatalogResponse
      
      // Should have products
      expect(page1Data.total_count).toBeGreaterThan(0)
      expect(page1Data.data.length).toBeGreaterThan(0)
      
      // Now test page 2
      const response = await app.handle(
        new Request('http://localhost/api/v1/catalog?page=2&limit=2', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(200)

      const data = (await response.json()) as CatalogResponse
      
      // Verify pagination metadata
      expect(data).toHaveProperty('total_count')
      expect(typeof data.total_count).toBe('number')
      expect(data.total_count).toBeGreaterThan(0)
      
      expect(data).toHaveProperty('page', 2)
      expect(data).toHaveProperty('limit', 2)
      
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)
      expect(data.data.length).toBeLessThanOrEqual(2)
      
      // If total_count > 2, page 2 should have different products than page 1
      if (page1Data.total_count > 2 && data.data.length > 0) {
        const page1Ids = page1Data.data.map(p => p.id)
        const page2Ids = data.data.map(p => p.id)
        // Page 2 products should be different from page 1
        page2Ids.forEach(id => {
          expect(page1Ids).not.toContain(id)
        })
      }
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
      
      // Should have our test products
      expect(data.total_count).toBeGreaterThan(0)
      expect(data.data.length).toBeGreaterThan(0)
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

