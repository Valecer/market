/**
 * Duplicate Management API Tests
 *
 * Phase 11: Pipeline Stabilization
 * Tests: T092 (filter by status), T093 (merge updates supplier_items)
 */

import { describe, expect, it, beforeAll, afterAll } from 'bun:test'
import { db } from '../../src/db/client'
import {
  products,
  categories,
  supplierItems,
  suppliers,
  potentialDuplicates,
} from '../../src/db/schema/schema'
import { eq, and } from 'drizzle-orm'
import {
  createAdminTestApp,
  generateTestToken,
} from '../helpers'
import { createTestUser, deleteTestUser } from '../fixtures'

describe('Duplicate Management API', () => {
  let app: ReturnType<typeof createAdminTestApp>
  let adminToken: string | null = null
  let adminUserId: string | null = null

  // Test data IDs
  let categoryId: string
  let supplierId: string
  let product1Id: string
  let product2Id: string
  let product3Id: string
  let supplierItem1Id: string
  let supplierItem2Id: string
  let pendingDuplicateId: string
  let mergedDuplicateId: string

  beforeAll(async () => {
    app = createAdminTestApp()

    // Create admin user
    adminUserId = await createTestUser('duplicate-test-admin', 'test-admin-123', 'admin')
    adminToken = await generateTestToken(app, 'duplicate-test-admin', 'test-admin-123')

    // Create test category
    const [category] = await db
      .insert(categories)
      .values({ name: 'Test Duplicate Category' })
      .returning()
    categoryId = category.id

    // Create test supplier
    const [supplier] = await db
      .insert(suppliers)
      .values({
        name: 'Test Duplicate Supplier',
        sourceType: 'csv',
        metadata: {},
      })
      .returning()
    supplierId = supplier.id

    // Create test products
    const [p1] = await db
      .insert(products)
      .values({
        internalSku: `DUP-TEST-P1-${Date.now()}`,
        name: 'LED Light 50W',
        categoryId,
        status: 'active',
      })
      .returning()
    product1Id = p1.id

    const [p2] = await db
      .insert(products)
      .values({
        internalSku: `DUP-TEST-P2-${Date.now()}`,
        name: 'LED Lamp 50W',
        categoryId,
        status: 'active',
      })
      .returning()
    product2Id = p2.id

    const [p3] = await db
      .insert(products)
      .values({
        internalSku: `DUP-TEST-P3-${Date.now()}`,
        name: 'Another Product',
        categoryId,
        status: 'active',
      })
      .returning()
    product3Id = p3.id

    // Create supplier items linked to products
    const [si1] = await db
      .insert(supplierItems)
      .values({
        supplierId,
        supplierSku: `DUP-SI-1-${Date.now()}`,
        name: 'LED Light 50W Supplier Item',
        currentPrice: '25.00',
        productId: product1Id,
        characteristics: {},
      })
      .returning()
    supplierItem1Id = si1.id

    const [si2] = await db
      .insert(supplierItems)
      .values({
        supplierId,
        supplierSku: `DUP-SI-2-${Date.now()}`,
        name: 'LED Lamp 50W Supplier Item',
        currentPrice: '26.00',
        productId: product2Id,
        characteristics: {},
      })
      .returning()
    supplierItem2Id = si2.id

    // Create potential duplicates (pending and already merged)
    const orderedIds =
      product1Id < product2Id
        ? { id1: product1Id, id2: product2Id }
        : { id1: product2Id, id2: product1Id }

    const [pending] = await db
      .insert(potentialDuplicates)
      .values({
        productId1: orderedIds.id1,
        productId2: orderedIds.id2,
        similarityScore: '87.5',
        detectionReason: 'auto_creation_similarity',
        status: 'pending',
      })
      .returning()
    pendingDuplicateId = pending.id

    // Create another duplicate that's already merged (for filtering test)
    const orderedIds2 =
      product2Id < product3Id
        ? { id1: product2Id, id2: product3Id }
        : { id1: product3Id, id2: product2Id }

    const [merged] = await db
      .insert(potentialDuplicates)
      .values({
        productId1: orderedIds2.id1,
        productId2: orderedIds2.id2,
        similarityScore: '88.0',
        detectionReason: 'auto_creation_similarity',
        status: 'merged',
      })
      .returning()
    mergedDuplicateId = merged.id

    console.log('✅ Duplicate test data created')
  })

  afterAll(async () => {
    // Cleanup in reverse order
    await db.delete(potentialDuplicates).where(eq(potentialDuplicates.id, pendingDuplicateId))
    await db.delete(potentialDuplicates).where(eq(potentialDuplicates.id, mergedDuplicateId))
    await db.delete(supplierItems).where(eq(supplierItems.id, supplierItem1Id))
    await db.delete(supplierItems).where(eq(supplierItems.id, supplierItem2Id))
    await db.delete(products).where(eq(products.id, product1Id))
    await db.delete(products).where(eq(products.id, product2Id))
    await db.delete(products).where(eq(products.id, product3Id))
    await db.delete(suppliers).where(eq(suppliers.id, supplierId))
    await db.delete(categories).where(eq(categories.id, categoryId))
    if (adminUserId) await deleteTestUser(adminUserId)
    console.log('✅ Duplicate test data cleaned up')
  })

  describe('GET /api/v1/admin/duplicates', () => {
    it('should require authentication', async () => {
      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/duplicates')
      )
      expect(response.status).toBe(401)
    })

    it('should return pending duplicates by default', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/duplicates', {
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as { duplicates: unknown[]; total: number }
      expect(data.duplicates).toBeDefined()
      expect(Array.isArray(data.duplicates)).toBe(true)
    })

    /**
     * T092: Test filtering by status
     */
    it('T092: should filter by status=pending', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/duplicates?status=pending', {
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as {
        duplicates: Array<{ id: string; status: string }>
        total: number
      }

      // All returned items should have status 'pending'
      for (const dup of data.duplicates) {
        expect(dup.status).toBe('pending')
      }
    })

    it('T092: should filter by status=merged', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/duplicates?status=merged', {
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as {
        duplicates: Array<{ id: string; status: string }>
        total: number
      }

      // All returned items should have status 'merged'
      for (const dup of data.duplicates) {
        expect(dup.status).toBe('merged')
      }
    })

    it('should support pagination', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      const response = await app.handle(
        new Request('http://localhost/api/v1/admin/duplicates?limit=1&offset=0', {
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as { duplicates: unknown[]; total: number }
      expect(data.duplicates.length).toBeLessThanOrEqual(1)
    })
  })

  describe('PATCH /api/v1/admin/duplicates/:id/merge', () => {
    it('should require authentication', async () => {
      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${pendingDuplicateId}/merge`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            keepProductId: product1Id,
            archiveProductId: product2Id,
          }),
        })
      )
      expect(response.status).toBe(401)
    })

    /**
     * T093: Test that merge updates supplier_items
     */
    it('T093: should reassign supplier_items on merge', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      // First verify supplier items are linked to different products
      const beforeItems = await db
        .select()
        .from(supplierItems)
        .where(eq(supplierItems.id, supplierItem2Id))
        .limit(1)
      expect(beforeItems[0]?.productId).toBe(product2Id)

      // Perform merge
      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${pendingDuplicateId}/merge`, {
          method: 'PATCH',
          headers: {
            Authorization: `Bearer ${adminToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            keepProductId: product1Id,
            archiveProductId: product2Id,
          }),
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as {
        success: boolean
        mergedProduct: { id: string; name: string; supplierItemCount: number }
      }

      expect(data.success).toBe(true)
      expect(data.mergedProduct.id).toBe(product1Id)
      // Should now have 2 supplier items (si1 + si2 after merge)
      expect(data.mergedProduct.supplierItemCount).toBe(2)

      // Verify supplier_item2 is now linked to product1
      const afterItems = await db
        .select()
        .from(supplierItems)
        .where(eq(supplierItems.id, supplierItem2Id))
        .limit(1)
      expect(afterItems[0]?.productId).toBe(product1Id)

      // Verify product2 is archived
      const archivedProduct = await db
        .select()
        .from(products)
        .where(eq(products.id, product2Id))
        .limit(1)
      expect(archivedProduct[0]?.status).toBe('archived')

      // Verify duplicate record is marked as merged
      const dupRecord = await db
        .select()
        .from(potentialDuplicates)
        .where(eq(potentialDuplicates.id, pendingDuplicateId))
        .limit(1)
      expect(dupRecord[0]?.status).toBe('merged')
    })

    it('should reject invalid product IDs', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      // Create a fresh duplicate for this test
      const orderedIds =
        product1Id < product3Id
          ? { id1: product1Id, id2: product3Id }
          : { id1: product3Id, id2: product1Id }

      const [testDup] = await db
        .insert(potentialDuplicates)
        .values({
          productId1: orderedIds.id1,
          productId2: orderedIds.id2,
          similarityScore: '86.0',
          detectionReason: 'auto_creation_similarity',
          status: 'pending',
        })
        .returning()

      // Try to merge with IDs that don't match the duplicate record
      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${testDup.id}/merge`, {
          method: 'PATCH',
          headers: {
            Authorization: `Bearer ${adminToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            keepProductId: product1Id,
            archiveProductId: '00000000-0000-0000-0000-000000000000', // Invalid ID
          }),
        })
      )

      expect(response.status).toBe(400)

      // Cleanup
      await db.delete(potentialDuplicates).where(eq(potentialDuplicates.id, testDup.id))
    })
  })

  describe('PATCH /api/v1/admin/duplicates/:id/dismiss', () => {
    it('should require authentication', async () => {
      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${mergedDuplicateId}/dismiss`, {
          method: 'PATCH',
        })
      )
      expect(response.status).toBe(401)
    })

    it('should dismiss a pending duplicate', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      // Create a fresh duplicate for dismissal test
      const orderedIds =
        product1Id < product3Id
          ? { id1: product1Id, id2: product3Id }
          : { id1: product3Id, id2: product1Id }

      const [testDup] = await db
        .insert(potentialDuplicates)
        .values({
          productId1: orderedIds.id1,
          productId2: orderedIds.id2,
          similarityScore: '85.5',
          detectionReason: 'auto_creation_similarity',
          status: 'pending',
        })
        .returning()

      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${testDup.id}/dismiss`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(200)
      const data = (await response.json()) as { success: boolean }
      expect(data.success).toBe(true)

      // Verify status changed to dismissed
      const dismissed = await db
        .select()
        .from(potentialDuplicates)
        .where(eq(potentialDuplicates.id, testDup.id))
        .limit(1)
      expect(dismissed[0]?.status).toBe('dismissed')

      // Cleanup
      await db.delete(potentialDuplicates).where(eq(potentialDuplicates.id, testDup.id))
    })

    it('should reject dismissing already-processed duplicates', async () => {
      if (!adminToken) {
        console.warn('⚠️  No admin token, skipping test')
        return
      }

      // mergedDuplicateId is already merged, should fail
      const response = await app.handle(
        new Request(`http://localhost/api/v1/admin/duplicates/${mergedDuplicateId}/dismiss`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${adminToken}` },
        })
      )

      expect(response.status).toBe(400)
    })
  })
})
