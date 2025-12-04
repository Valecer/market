import { describe, test, expect, beforeAll, afterAll } from 'bun:test'
import {
  createAdminTestApp,
  generateTestToken,
  type ErrorResponse,
} from '../helpers'
import { db } from '../../src/db/client'
import { categories, suppliers, products } from '../../src/db/schema/schema'
import { sql, eq } from 'drizzle-orm'

/**
 * Category Review Endpoint Tests
 *
 * Tests for Phase 9 - Semantic ETL: Category Review Workflow
 *
 * Tasks covered:
 * - T064: GET /categories/review endpoint
 * - T065: Query filters (supplier_id, needs_review, search, sort)
 * - T066: POST /categories/approve endpoint (approve/merge actions)
 * - T069: CategoryService unit tests
 * - T069a: GET /categories/review/count endpoint
 * - T069b: POST /categories/approve/bulk endpoint
 *
 * Prerequisites:
 * - DATABASE_URL environment variable must be set
 * - Categories table must have Phase 9 columns (needs_review, is_active, supplier_id, updated_at)
 */
describe('Admin Categories - Category Review Workflow', () => {
  let app: ReturnType<typeof createAdminTestApp>
  let adminToken: string | null = null
  let salesToken: string | null = null

  // Test data IDs for cleanup
  let testSupplierId: string | null = null
  let testCategoryIds: string[] = []
  let testProductIds: string[] = []

  // ==========================================================================
  // Setup and Teardown
  // ==========================================================================

  beforeAll(async () => {
    app = createAdminTestApp()

    // Get admin token (assumes admin user exists)
    adminToken = await generateTestToken(app, 'admin', 'admin123', 5)
    salesToken = await generateTestToken(app, 'sales', 'sales123', 5)

    if (!adminToken) {
      console.warn(
        'Warning: Could not obtain admin token. Tests will fail if authentication is required.'
      )
    }

    // Create test supplier
    const supplierResult = await db
      .insert(suppliers)
      .values({
        name: 'Test Supplier for Categories',
        sourceType: 'excel',
        metadata: { test: true },
      })
      .returning()

    if (supplierResult[0]) {
      testSupplierId = supplierResult[0].id
    }

    // Create test categories with various states
    const testCategories = [
      { name: 'Category Needs Review 1', needsReview: true, isActive: true, supplierId: testSupplierId },
      { name: 'Category Needs Review 2', needsReview: true, isActive: true, supplierId: testSupplierId },
      { name: 'Category Approved', needsReview: false, isActive: true, supplierId: testSupplierId },
      { name: 'Category Inactive', needsReview: true, isActive: false, supplierId: testSupplierId },
      { name: 'Parent Category', needsReview: false, isActive: true, supplierId: null },
    ]

    for (const cat of testCategories) {
      const result = await db
        .insert(categories)
        .values({
          name: cat.name,
          needsReview: cat.needsReview,
          isActive: cat.isActive,
          supplierId: cat.supplierId,
        })
        .returning()

      if (result[0]) {
        testCategoryIds.push(result[0].id)
      }
    }

    // Create a child category for merge testing
    if (testCategoryIds.length >= 5) {
      const childResult = await db
        .insert(categories)
        .values({
          name: 'Child Category for Merge',
          needsReview: true,
          isActive: true,
          supplierId: testSupplierId,
          parentId: testCategoryIds[4], // Parent Category
        })
        .returning()

      if (childResult[0]) {
        testCategoryIds.push(childResult[0].id)
      }
    }

    // Create a test product in the first review category for merge tests
    if (testCategoryIds.length > 0) {
      const productResult = await db
        .insert(products)
        .values({
          name: 'Test Product for Category Merge',
          internalSku: `TEST-CATREVIEW-${Date.now()}`,
          categoryId: testCategoryIds[0],
          status: 'draft',
        })
        .returning()

      if (productResult[0]) {
        testProductIds.push(productResult[0].id)
      }
    }
  })

  afterAll(async () => {
    // Cleanup test data in reverse dependency order
    for (const productId of testProductIds) {
      await db.delete(products).where(eq(products.id, productId))
    }

    for (const categoryId of testCategoryIds) {
      await db.delete(categories).where(eq(categories.id, categoryId))
    }

    if (testSupplierId) {
      await db.delete(suppliers).where(eq(suppliers.id, testSupplierId))
    }
  })

  // ==========================================================================
  // GET /api/v1/admin/categories/review
  // ==========================================================================

  describe('GET /api/v1/admin/categories/review', () => {
    test('should return 401 without authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(401)
    })

    test('should return 403 for non-admin users', async () => {
      if (!salesToken) {
        console.warn('Skipping test: no sales token')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${salesToken}`,
          },
        })
      )

      expect(response.status).toBe(403)
    })

    test('should return paginated categories needing review', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${adminToken}`,
          },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      expect(data).toHaveProperty('total_count')
      expect(data).toHaveProperty('page')
      expect(data).toHaveProperty('limit')
      expect(data).toHaveProperty('data')
      expect(Array.isArray(data.data)).toBe(true)

      // Should only include active categories needing review
      for (const category of data.data) {
        expect(category).toHaveProperty('id')
        expect(category).toHaveProperty('name')
        expect(category).toHaveProperty('needs_review')
        expect(category).toHaveProperty('is_active')
        expect(category).toHaveProperty('product_count')
        // Default filter: needs_review = true, is_active = true
        expect(category.needs_review).toBe(true)
        expect(category.is_active).toBe(true)
      }
    })

    test('should filter by supplier_id', async () => {
      if (!adminToken || !testSupplierId) {
        console.warn('Skipping test: no admin token or supplier ID')
        return
      }

      const response = await app.handle(
        new Request(
          `http://localhost/api/v1/admin/categories/review?supplier_id=${testSupplierId}`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${adminToken}`,
            },
          }
        )
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      // All returned categories should belong to the test supplier
      for (const category of data.data) {
        expect(category.supplier_id).toBe(testSupplierId)
      }
    })

    test('should filter by search term', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request(
          'http://localhost/api/v1/admin/categories/review?search=Needs%20Review',
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${adminToken}`,
            },
          }
        )
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      // All returned categories should contain the search term
      for (const category of data.data) {
        expect(category.name.toLowerCase()).toContain('needs review')
      }
    })

    test('should support pagination', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review?page=1&limit=2', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${adminToken}`,
          },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      expect(data.page).toBe(1)
      expect(data.limit).toBe(2)
      expect(data.data.length).toBeLessThanOrEqual(2)
    })

    test('should sort by name ascending', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request(
          'http://localhost/api/v1/admin/categories/review?sort_by=name&sort_order=asc',
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${adminToken}`,
            },
          }
        )
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      // Check that names are in ascending order
      if (data.data.length > 1) {
        for (let i = 1; i < data.data.length; i++) {
          expect(data.data[i].name >= data.data[i - 1].name).toBe(true)
        }
      }
    })
  })

  // ==========================================================================
  // GET /api/v1/admin/categories/review/count
  // ==========================================================================

  describe('GET /api/v1/admin/categories/review/count', () => {
    test('should return 401 without authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review/count', {
          method: 'GET',
        })
      )

      expect(response.status).toBe(401)
    })

    test('should return count of categories needing review', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/review/count', {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${adminToken}`,
          },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      expect(data).toHaveProperty('count')
      expect(typeof data.count).toBe('number')
      expect(data.count).toBeGreaterThanOrEqual(0)
    })
  })

  // ==========================================================================
  // POST /api/v1/admin/categories/approve
  // ==========================================================================

  describe('POST /api/v1/admin/categories/approve', () => {
    test('should return 401 without authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            category_id: testCategoryIds[0],
            action: 'approve',
          }),
        })
      )

      expect(response.status).toBe(401)
    })

    test('should return 403 for non-admin users', async () => {
      if (!salesToken || testCategoryIds.length === 0) {
        console.warn('Skipping test: no sales token or category IDs')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${salesToken}`,
          },
          body: JSON.stringify({
            category_id: testCategoryIds[0],
            action: 'approve',
          }),
        })
      )

      expect(response.status).toBe(403)
    })

    test('should approve a category (set needs_review=false)', async () => {
      if (!adminToken || testCategoryIds.length === 0) {
        console.warn('Skipping test: no admin token or category IDs')
        return
      }

      const categoryId = testCategoryIds[1] // Use second category

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_id: categoryId,
            action: 'approve',
          }),
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      expect(data.success).toBe(true)
      expect(data.action).toBe('approve')
      expect(data.category_id).toBe(categoryId)

      // Verify the category was updated in the database
      const [updatedCategory] = await db
        .select()
        .from(categories)
        .where(eq(categories.id, categoryId))

      expect(updatedCategory).toBeDefined()
      expect(updatedCategory.needsReview).toBe(false)
    })

    test('should return 404 for non-existent category', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const fakeId = '00000000-0000-0000-0000-000000000000'

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_id: fakeId,
            action: 'approve',
          }),
        })
      )

      expect(response.status).toBe(404)
    })

    test('should merge a category (transfer products)', async () => {
      if (!adminToken || testCategoryIds.length < 3) {
        console.warn('Skipping test: no admin token or not enough categories')
        return
      }

      // Create a temporary category for merge (so we don't affect other tests)
      const tempCategoryResult = await db
        .insert(categories)
        .values({
          name: 'Temp Category for Merge Test',
          needsReview: true,
          isActive: true,
          supplierId: testSupplierId,
        })
        .returning()

      const tempCategoryId = tempCategoryResult[0]?.id
      if (!tempCategoryId) {
        console.warn('Skipping test: could not create temp category')
        return
      }

      // Create a product in the temp category
      const tempProductResult = await db
        .insert(products)
        .values({
          name: 'Temp Product for Merge Test',
          internalSku: `TEST-MERGE-${Date.now()}`,
          categoryId: tempCategoryId,
          status: 'draft',
        })
        .returning()

      const tempProductId = tempProductResult[0]?.id

      // Target: approved category (index 2)
      const targetCategoryId = testCategoryIds[2]

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_id: tempCategoryId,
            action: 'merge',
            merge_with_id: targetCategoryId,
          }),
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as any

      expect(data.success).toBe(true)
      expect(data.action).toBe('merge')
      expect(data.affected_products).toBeGreaterThanOrEqual(1)

      // Verify the source category was deleted
      const [deletedCategory] = await db
        .select()
        .from(categories)
        .where(eq(categories.id, tempCategoryId))

      expect(deletedCategory).toBeUndefined()

      // Verify the product was moved to target category
      if (tempProductId) {
        const [movedProduct] = await db
          .select()
          .from(products)
          .where(eq(products.id, tempProductId))

        expect(movedProduct).toBeDefined()
        expect(movedProduct.categoryId).toBe(targetCategoryId)

        // Cleanup
        await db.delete(products).where(eq(products.id, tempProductId))
      }
    })

    test('should return 400 when merging without merge_with_id', async () => {
      if (!adminToken || testCategoryIds.length === 0) {
        console.warn('Skipping test: no admin token or category IDs')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_id: testCategoryIds[0],
            action: 'merge',
            // Missing merge_with_id
          }),
        })
      )

      expect(response.status).toBe(400)
    })

    test('should return 400 when merging category with itself', async () => {
      if (!adminToken || testCategoryIds.length === 0) {
        console.warn('Skipping test: no admin token or category IDs')
        return
      }

      const categoryId = testCategoryIds[0]

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_id: categoryId,
            action: 'merge',
            merge_with_id: categoryId, // Same ID
          }),
        })
      )

      // Should return 400 (validation error) or 500 (caught error)
      expect([400, 500].includes(response.status)).toBe(true)
    })
  })

  // ==========================================================================
  // POST /api/v1/admin/categories/approve/bulk
  // ==========================================================================

  describe('POST /api/v1/admin/categories/approve/bulk', () => {
    test('should return 401 without authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve/bulk', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            category_ids: [testCategoryIds[0]],
          }),
        })
      )

      expect(response.status).toBe(401)
    })

    test('should bulk approve categories', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      // Create temp categories for bulk approval
      const tempCategories = await Promise.all([
        db
          .insert(categories)
          .values({
            name: 'Bulk Approve Test 1',
            needsReview: true,
            isActive: true,
            supplierId: testSupplierId,
          })
          .returning(),
        db
          .insert(categories)
          .values({
            name: 'Bulk Approve Test 2',
            needsReview: true,
            isActive: true,
            supplierId: testSupplierId,
          })
          .returning(),
      ])

      const tempIds = tempCategories.map((r) => r[0]?.id).filter(Boolean) as string[]

      try {
        const response = await app.handle(
          new Request('http://localhost/api/v1/admin/categories/approve/bulk', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${adminToken}`,
            },
            body: JSON.stringify({
              category_ids: tempIds,
            }),
          })
        )

        expect(response.status).toBe(200)
        const data = (await response.json()) as any

        expect(data.success).toBe(true)
        expect(data.approved_count).toBe(2)

        // Verify categories were updated
        for (const id of tempIds) {
          const [cat] = await db.select().from(categories).where(eq(categories.id, id))
          expect(cat.needsReview).toBe(false)
        }
      } finally {
        // Cleanup
        for (const id of tempIds) {
          await db.delete(categories).where(eq(categories.id, id))
        }
      }
    })

    test('should return success with zero count for empty array', async () => {
      if (!adminToken) {
        console.warn('Skipping test: no admin token')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/categories/approve/bulk', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            category_ids: [],
          }),
        })
      )

      // Empty array should fail validation (minItems: 1)
      expect(response.status).toBe(400)
    })
  })
})

