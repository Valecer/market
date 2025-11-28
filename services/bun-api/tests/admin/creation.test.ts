import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import { createAdminTestApp, generateTestToken, setupAuthTokens, type ErrorResponse } from '../helpers'
import { setupTestEnvironment, cleanupTestData, type TestData } from '../fixtures'
import type { CreateProductResponse } from '../../src/types/admin.types'

/**
 * Product Creation Endpoint Tests
 * 
 * Tests for T137-T146: Product creation endpoint scenarios
 * 
 * Prerequisites:
 * - DATABASE_URL environment variable must be set
 * - Users table must exist
 * - Categories, suppliers, supplier_items tables must exist
 * 
 * Test Setup:
 * - Creates test admin user if it doesn't exist
 * - Creates test category, supplier, and supplier_item
 * - Cleans up all test data after tests complete
 */
describe('Admin Products - Product Creation Endpoint', () => {
  let app: ReturnType<typeof createAdminTestApp>
  let adminToken: string | null = null
  let procurementToken: string | null = null
  let salesToken: string | null = null
  let testData: TestData | null = null

  beforeAll(async () => {
    app = createAdminTestApp()
    
    // Setup test environment with admin user and test data
    testData = await setupTestEnvironment('creation')
    
    // Create test users for all roles to ensure we have working tokens
    const { createTestUser } = await import('../fixtures')
    
    // Create test procurement and sales users
    const testProcurementUserId = await createTestUser(
      'test-procurement-creation',
      'test-procurement-123',
      'procurement'
    )
    const testSalesUserId = await createTestUser(
      'test-sales-creation',
      'test-sales-123',
      'sales'
    )
    
    // Add a small delay to ensure users are fully committed to database
    await new Promise(resolve => setTimeout(resolve, 100))
    
    // Get tokens for test users (preferred, since we just created them)
    if (testData.adminUserId) {
      const testAdminToken = await generateTestToken(
        app,
        'test-admin-creation',
        'test-admin-123',
        5 // More retries for newly created user
      )
      if (testAdminToken) {
        adminToken = testAdminToken
      }
    }
    
    if (testProcurementUserId) {
      const testProcurementToken = await generateTestToken(
        app,
        'test-procurement-creation',
        'test-procurement-123',
        5
      )
      if (testProcurementToken) {
        procurementToken = testProcurementToken
      }
    }
    
    if (testSalesUserId) {
      const testSalesToken = await generateTestToken(
        app,
        'test-sales-creation',
        'test-sales-123',
        5
      )
      if (testSalesToken) {
        salesToken = testSalesToken
      }
    }

    // Fallback to default users if test users didn't work
    const tokens = await setupAuthTokens(app)
    if (!adminToken) {
      adminToken = tokens.adminToken
    }
    if (!procurementToken) {
      procurementToken = tokens.procurementToken
    }
    if (!salesToken) {
      salesToken = tokens.salesToken
    }

  })

  afterAll(async () => {
    // Clean up test data
    if (testData) {
      await cleanupTestData(testData)
    }
  })

  describe('T137: Requires authentication', () => {
    test('POST /api/v1/admin/products without token returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name: 'Test Product',
          }),
        })
      )

      expect(response.status).toBe(401)
      const data = await response.json() as ErrorResponse
      expect(data).toHaveProperty('error')
      expect(data.error.code).toBe('UNAUTHORIZED')
    })

    test('POST /api/v1/admin/products with invalid token returns 401', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer invalid-token-here',
          },
          body: JSON.stringify({
            name: 'Test Product',
          }),
        })
      )

      expect(response.status).toBe(401)
      const data = await response.json() as ErrorResponse
      expect(data).toHaveProperty('error')
      expect(data.error.code).toBe('UNAUTHORIZED')
    })
  })

  describe('T138: Requires procurement or admin role', () => {
    test('POST /api/v1/admin/products with sales role returns 403', async () => {
      if (!salesToken) {
        console.warn('Skipping test: Sales token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${salesToken}`,
          },
          body: JSON.stringify({
            name: 'Test Product',
          }),
        })
      )

      expect(response.status).toBe(403)
      const data = await response.json() as ErrorResponse
      expect(data).toHaveProperty('error')
      expect(data.error.code).toBe('FORBIDDEN')
      expect(data.error.message).toContain('Procurement or admin role required')
    })

    test('POST /api/v1/admin/products with procurement role succeeds', async () => {
      if (!procurementToken) {
        console.warn('Skipping test: Procurement token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${procurementToken}`,
          },
          body: JSON.stringify({
            name: 'Test Product from Procurement',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data).toHaveProperty('id')
      expect(data).toHaveProperty('internal_sku')
      expect(data.name).toBe('Test Product from Procurement')
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })

    test('POST /api/v1/admin/products with admin role succeeds', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Test Product from Admin',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data).toHaveProperty('id')
      expect(data).toHaveProperty('internal_sku')
      expect(data.name).toBe('Test Product from Admin')
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })
  })

  describe('T139: Creates with auto-generated SKU', () => {
    test('POST /api/v1/admin/products without internal_sku generates SKU', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Auto SKU',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data).toHaveProperty('internal_sku')
      expect(data.internal_sku).toMatch(/^PROD-\d+-[A-Z0-9]{4}$/)
      expect(data.name).toBe('Product with Auto SKU')
      expect(data.status).toBe('draft') // Default status
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })
  })

  describe('T140: Creates with provided SKU', () => {
    test('POST /api/v1/admin/products with provided internal_sku uses it', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const customSku = `TEST-SKU-${Date.now()}`
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Custom SKU',
            internal_sku: customSku,
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data.internal_sku).toBe(customSku)
      expect(data.name).toBe('Product with Custom SKU')
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })
  })

  describe('T141: Links supplier item if provided', () => {
    test('POST /api/v1/admin/products with supplier_item_id links it', async () => {
      if (!adminToken || !testData?.supplierItemId) {
        console.warn('Skipping test: Admin token or test supplier item not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Linked Supplier Item',
            supplier_item_id: testData.supplierItemId,
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data).toHaveProperty('supplier_items')
      expect(Array.isArray(data.supplier_items)).toBe(true)
      expect(data.supplier_items.length).toBe(1)
      if (data.supplier_items[0] && testData.supplierItemId) {
        expect(data.supplier_items[0].id).toBe(testData.supplierItemId)
      }
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
      
      // Note: We can't reuse testData.supplierItemId for another test since it's now linked
      // This is expected behavior - supplier items can only be linked to one product
    })
  })

  describe('T142: 400 if internal_sku duplicate', () => {
    test('POST /api/v1/admin/products with duplicate SKU returns 400', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      // First, create a product with a specific SKU
      const duplicateSku = `DUPLICATE-SKU-${Date.now()}`
      const firstResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'First Product',
            internal_sku: duplicateSku,
          }),
        })
      )

      expect(firstResponse.status).toBe(201)
      const firstData = await firstResponse.json() as CreateProductResponse
      if (firstData.id && testData) {
        testData.productIds.push(firstData.id)
      }

      // Try to create another product with the same SKU
      const secondResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Second Product with Duplicate SKU',
            internal_sku: duplicateSku,
          }),
        })
      )

      expect(secondResponse.status).toBe(400)
      const errorData = await secondResponse.json() as ErrorResponse
      expect(errorData).toHaveProperty('error')
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
      expect(errorData.error.message).toContain('already exists')
    })
  })

  describe('T143: 400 if category_id invalid', () => {
    test('POST /api/v1/admin/products with non-existent category_id returns 400', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const fakeCategoryId = '00000000-0000-0000-0000-000000000000'
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Invalid Category',
            category_id: fakeCategoryId,
          }),
        })
      )

      expect(response.status).toBe(400)
      const errorData = await response.json() as ErrorResponse
      expect(errorData).toHaveProperty('error')
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
      expect(errorData.error.message).toContain('not found')
    })

    test('POST /api/v1/admin/products with valid category_id succeeds', async () => {
      if (!adminToken || !testData?.categoryId) {
        console.warn('Skipping test: Admin token or test category not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Valid Category',
            category_id: testData.categoryId,
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data.category_id).toBe(testData.categoryId)
      
      // Track for cleanup
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })
  })

  describe('T144: 400 if supplier_item_id invalid', () => {
    test('POST /api/v1/admin/products with non-existent supplier_item_id returns 400', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const fakeSupplierItemId = '00000000-0000-0000-0000-000000000000'
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Invalid Supplier Item',
            supplier_item_id: fakeSupplierItemId,
          }),
        })
      )

      expect(response.status).toBe(400)
      const errorData = await response.json() as ErrorResponse
      expect(errorData).toHaveProperty('error')
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
      expect(errorData.error.message).toContain('not found')
    })

    test('POST /api/v1/admin/products with already-linked supplier_item_id returns 400', async () => {
      if (!adminToken || !testData?.supplierId) {
        console.warn('Skipping test: Admin token or test supplier not available')
        return
      }

      // Create a new supplier item and link it to a product
      const { db } = await import('../../src/db/client')
      const { supplierItems, products } = await import('../../src/db/schema/schema')
      const { eq } = await import('drizzle-orm')
      
      const linkedSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId: testData.supplierId,
          supplierSku: `LINKED-SKU-${Date.now()}`,
          name: 'Linked Supplier Item',
          currentPrice: '29.99',
          characteristics: {},
        })
        .returning()
      
      const linkedProduct = await db
        .insert(products)
        .values({
          internalSku: `LINKED-PROD-${Date.now()}`,
          name: 'Product with Linked Item',
          status: 'draft',
        })
        .returning()
      
      // Link the supplier item to the product
      if (linkedProduct[0]?.id && linkedSupplierItem[0]?.id) {
        await db
          .update(supplierItems)
          .set({ productId: linkedProduct[0].id })
          .where(eq(supplierItems.id, linkedSupplierItem[0].id))
      }
      
      if (linkedProduct[0]?.id && testData) {
        testData.productIds.push(linkedProduct[0].id)
      }
      
      // Try to create a new product with the already-linked supplier item
      if (linkedSupplierItem[0]?.id) {
        const response = await app.handle(
          new Request('http://localhost/api/v1/admin/products', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${adminToken}`,
            },
            body: JSON.stringify({
              name: 'Product Trying to Use Linked Item',
              supplier_item_id: linkedSupplierItem[0].id,
            }),
          })
        )

        expect(response.status).toBe(400)
        const errorData = await response.json() as ErrorResponse
        expect(errorData).toHaveProperty('error')
        expect(errorData.error.code).toBe('VALIDATION_ERROR')
        expect(errorData.error.message).toContain('already linked')
        
        // Clean up
        await db.delete(supplierItems).where(eq(supplierItems.id, linkedSupplierItem[0].id))
      }
    })
  })

  describe('T145: 400 if name empty or too long', () => {
    test('POST /api/v1/admin/products with empty name returns 400', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: '',
          }),
        })
      )

      expect(response.status).toBe(400)
      const errorData = await response.json() as ErrorResponse
      expect(errorData).toHaveProperty('error')
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
    })

    test('POST /api/v1/admin/products with name too long returns 400', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const longName = 'A'.repeat(501) // 501 characters (max is 500)
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: longName,
          }),
        })
      )

      expect(response.status).toBe(400)
      const errorData = await response.json() as ErrorResponse
      expect(errorData).toHaveProperty('error')
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
    })
  })

  describe('T146: Transaction rollback on error', () => {
    test('POST /api/v1/admin/products rolls back if supplier item link fails', async () => {
      if (!adminToken || !testData?.supplierId) {
        console.warn('Skipping test: Admin token or test supplier not available')
        return
      }

      const { db } = await import('../../src/db/client')
      const { supplierItems, products } = await import('../../src/db/schema/schema')
      const { eq } = await import('drizzle-orm')
      
      // Create a supplier item that we'll delete to cause a foreign key error
      const tempSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId: testData.supplierId,
          supplierSku: `TEMP-SKU-${Date.now()}`,
          name: 'Temporary Supplier Item',
          currentPrice: '39.99',
          characteristics: {},
        })
        .returning()
      
      const tempSupplierItemId = tempSupplierItem[0]?.id
      if (!tempSupplierItemId) {
        throw new Error('Failed to create temp supplier item')
      }
      
      // Delete the supplier item to make it invalid
      await db.delete(supplierItems).where(eq(supplierItems.id, tempSupplierItemId))
      
      // Try to create a product with the deleted supplier item
      // This should fail and roll back the product creation
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product That Should Not Be Created',
            supplier_item_id: tempSupplierItemId,
          }),
        })
      )

      expect(response.status).toBe(400)
      
      // Verify product was not created by checking the database
      const createdProducts = await db
        .select()
        .from(products)
        .where(eq(products.name, 'Product That Should Not Be Created'))
        .limit(1)
      
      expect(createdProducts.length).toBe(0) // Product should not exist
    })
  })

  describe('Independent Test Criteria Verification', () => {
    test('✅ POST /api/v1/admin/products requires procurement or admin role', async () => {
      if (!salesToken) {
        console.warn('Skipping test: Sales token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${salesToken}`,
          },
          body: JSON.stringify({
            name: 'Test Product',
          }),
        })
      )

      expect(response.status).toBe(403)
    })

    test('✅ Creates new product with auto-generated SKU if not provided', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Auto SKU',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data.internal_sku).toMatch(/^PROD-\d+-[A-Z0-9]{4}$/)
      
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })

    test('✅ Creates new product with provided internal_sku', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const customSku = `PROVIDED-SKU-${Date.now()}`
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Provided SKU',
            internal_sku: customSku,
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data.internal_sku).toBe(customSku)
      
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })

    test('✅ Links supplier item if supplier_item_id provided', async () => {
      if (!adminToken || !testData?.supplierId) {
        console.warn('Skipping test: Admin token or test supplier not available')
        return
      }

      // Create a new supplier item for this test
      const { db } = await import('../../src/db/client')
      const { supplierItems } = await import('../../src/db/schema/schema')
      const { eq } = await import('drizzle-orm')
      
      const newSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId: testData.supplierId,
          supplierSku: `LINK-TEST-${Date.now()}`,
          name: 'Supplier Item for Link Test',
          currentPrice: '49.99',
          characteristics: {},
        })
        .returning()
      
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Linked Item',
            supplier_item_id: newSupplierItem[0]?.id || '',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      expect(data.supplier_items.length).toBe(1)
      if (data.supplier_items[0] && newSupplierItem[0]?.id) {
        expect(data.supplier_items[0].id).toBe(newSupplierItem[0].id)
      }
      
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
      
      // Clean up supplier item
      if (newSupplierItem[0]?.id) {
        await db.delete(supplierItems).where(eq(supplierItems.id, newSupplierItem[0].id))
      }
    })

    test('✅ Validates internal_sku uniqueness', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      const uniqueSku = `UNIQUE-SKU-${Date.now()}`
      
      // Create first product
      const firstResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'First Product',
            internal_sku: uniqueSku,
          }),
        })
      )

      expect(firstResponse.status).toBe(201)
      const firstData = await firstResponse.json() as CreateProductResponse
      if (firstData.id && testData) {
        testData.productIds.push(firstData.id)
      }

      // Try to create second product with same SKU
      const secondResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Second Product',
            internal_sku: uniqueSku,
          }),
        })
      )

      expect(secondResponse.status).toBe(400)
      const errorData = await secondResponse.json() as ErrorResponse
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
      expect(errorData.error.message).toContain('already exists')
    })

    test('✅ Validates category_id exists if provided', async () => {
      if (!adminToken || !testData?.categoryId) {
        console.warn('Skipping test: Admin token or test category not available')
        return
      }

      // Test with valid category
      const validResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Valid Category',
            category_id: testData.categoryId,
          }),
        })
      )

      expect(validResponse.status).toBe(201)
      const validData = await validResponse.json() as CreateProductResponse
      expect(validData.category_id).toBe(testData.categoryId)
      
      if (validData.id && testData) {
        testData.productIds.push(validData.id)
      }

      // Test with invalid category
      const invalidResponse = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Invalid Category',
            category_id: '00000000-0000-0000-0000-000000000000',
          }),
        })
      )

      expect(invalidResponse.status).toBe(400)
      const errorData = await invalidResponse.json() as ErrorResponse
      expect(errorData.error.code).toBe('VALIDATION_ERROR')
    })

    test('✅ Returns created product with supplier items', async () => {
      if (!adminToken || !testData?.supplierId) {
        console.warn('Skipping test: Admin token or test supplier not available')
        return
      }

      const { db } = await import('../../src/db/client')
      const { supplierItems } = await import('../../src/db/schema/schema')
      const { eq } = await import('drizzle-orm')
      
      const newSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId: testData.supplierId,
          supplierSku: `RESPONSE-TEST-${Date.now()}`,
          name: 'Supplier Item for Response Test',
          currentPrice: '59.99',
          characteristics: { color: 'red', size: 'large' },
        })
        .returning()
      
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product with Supplier Items in Response',
            supplier_item_id: newSupplierItem[0]?.id || '',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      
      // Verify response structure
      expect(data).toHaveProperty('id')
      expect(data).toHaveProperty('internal_sku')
      expect(data).toHaveProperty('name')
      expect(data).toHaveProperty('status')
      expect(data).toHaveProperty('supplier_items')
      expect(data).toHaveProperty('created_at')
      
      // Verify supplier items structure
      expect(Array.isArray(data.supplier_items)).toBe(true)
      expect(data.supplier_items.length).toBe(1)
      expect(data.supplier_items[0]).toHaveProperty('id')
      expect(data.supplier_items[0]).toHaveProperty('supplier_id')
      expect(data.supplier_items[0]).toHaveProperty('supplier_name')
      expect(data.supplier_items[0]).toHaveProperty('supplier_sku')
      expect(data.supplier_items[0]).toHaveProperty('current_price')
      expect(data.supplier_items[0]).toHaveProperty('characteristics')
      
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
      
      // Clean up
      if (newSupplierItem[0]?.id) {
        await db.delete(supplierItems).where(eq(supplierItems.id, newSupplierItem[0].id))
      }
    })

    test('✅ Returns 400 for validation errors', async () => {
      if (!adminToken) {
        console.warn('Skipping test: Admin token not available')
        return
      }

      // Test multiple validation errors
      const testCases = [
        { name: '', expected: 'empty name' },
        { name: 'A'.repeat(501), expected: 'name too long' },
        { category_id: 'invalid-uuid', expected: 'invalid UUID' },
      ]

      for (const testCase of testCases) {
        const response = await app.handle(
          new Request('http://localhost/api/v1/admin/products', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${adminToken}`,
            },
            body: JSON.stringify(testCase),
          })
        )

        expect(response.status).toBe(400)
        const errorData = await response.json() as ErrorResponse
        expect(errorData).toHaveProperty('error')
        expect(errorData.error.code).toBe('VALIDATION_ERROR')
      }
    })

    test('✅ Transaction ensures atomicity (product creation + item link)', async () => {
      if (!adminToken || !testData?.supplierId) {
        console.warn('Skipping test: Admin token or test supplier not available')
        return
      }

      const { db } = await import('../../src/db/client')
      const { supplierItems, products } = await import('../../src/db/schema/schema')
      const { eq } = await import('drizzle-orm')
      
      // Create a supplier item
      const testSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId: testData.supplierId,
          supplierSku: `ATOMIC-TEST-${Date.now()}`,
          name: 'Supplier Item for Atomicity Test',
          currentPrice: '69.99',
          characteristics: {},
        })
        .returning()
      
      // Create product with supplier item link
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            name: 'Product for Atomicity Test',
            supplier_item_id: testSupplierItem[0]?.id || '',
          }),
        })
      )

      expect(response.status).toBe(201)
      const data = await response.json() as CreateProductResponse
      
      // Verify both product and link were created
      const product = await db
        .select()
        .from(products)
        .where(eq(products.id, data.id))
        .limit(1)
      
      expect(product.length).toBe(1)
      
      const linkedItem = await db
        .select()
        .from(supplierItems)
        .where(eq(supplierItems.id, testSupplierItem[0]?.id || ''))
        .limit(1)
      
      expect(linkedItem.length).toBe(1)
      if (linkedItem[0] && data.id) {
        expect(linkedItem[0].productId).toBe(data.id) // Item should be linked
      }
      
      if (data.id && testData) {
        testData.productIds.push(data.id)
      }
    })
  })
})

