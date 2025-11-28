import { db } from '../src/db/client'
import { users, categories, suppliers, supplierItems, products } from '../src/db/schema/schema'
import { eq, inArray } from 'drizzle-orm'

/**
 * Test Fixtures
 * 
 * Utilities for creating and cleaning up test data
 */

export interface TestData {
  adminUserId: string | null
  categoryId: string | null
  supplierId: string | null
  supplierItemId: string | null
  productIds: string[]
}

/**
 * Create test data (category, supplier, supplier item)
 * @param prefix - Prefix for test data names (to avoid conflicts)
 * @returns Test data IDs
 */
export async function createTestData(prefix: string = 'test'): Promise<{
  categoryId: string | null
  supplierId: string | null
  supplierItemId: string | null
}> {
  try {
    // Create test category
    const testCategory = await db
      .insert(categories)
      .values({
        name: `${prefix} Category`,
      })
      .returning()
    const categoryId = testCategory[0]?.id || null

    // Create test supplier
    const testSupplier = await db
      .insert(suppliers)
      .values({
        name: `${prefix} Supplier`,
        sourceType: 'csv',
        metadata: {},
      })
      .returning()
    const supplierId = testSupplier[0]?.id || null

    // Create test supplier item (unlinked)
    let supplierItemId: string | null = null
    if (supplierId) {
      const testSupplierItem = await db
        .insert(supplierItems)
        .values({
          supplierId,
          supplierSku: `${prefix}-SKU-001`,
          name: `${prefix} Supplier Item`,
          currentPrice: '19.99',
          characteristics: {},
        })
        .returning()
      supplierItemId = testSupplierItem[0]?.id || null
    }

    console.log('✅ Test data created successfully')
    return {
      categoryId,
      supplierId,
      supplierItemId,
    }
  } catch (error) {
    console.error('❌ Failed to create test data:', error)
    throw error
  }
}

/**
 * Clean up test data
 * @param testData - Test data to clean up
 */
export async function cleanupTestData(testData: TestData): Promise<void> {
  try {
    // Delete test products
    if (testData.productIds.length > 0) {
      await db.delete(products).where(inArray(products.id, testData.productIds))
      console.log(`✅ Cleaned up ${testData.productIds.length} test products`)
    }

    // Delete test supplier item
    if (testData.supplierItemId) {
      await db.delete(supplierItems).where(eq(supplierItems.id, testData.supplierItemId))
      console.log('✅ Cleaned up test supplier item')
    }

    // Delete test supplier
    if (testData.supplierId) {
      await db.delete(suppliers).where(eq(suppliers.id, testData.supplierId))
      console.log('✅ Cleaned up test supplier')
    }

    // Delete test category
    if (testData.categoryId) {
      await db.delete(categories).where(eq(categories.id, testData.categoryId))
      console.log('✅ Cleaned up test category')
    }

    // Delete test admin user
    if (testData.adminUserId) {
      await db.delete(users).where(eq(users.id, testData.adminUserId))
      console.log('✅ Cleaned up test admin user')
    }
  } catch (error) {
    console.error('⚠️  Error cleaning up test data:', error)
    // Don't throw - cleanup errors shouldn't fail tests
  }
}

/**
 * Create a test user with a specific role
 * @param username - Username for test user
 * @param password - Password for test user
 * @param role - User role (admin, procurement, sales)
 * @returns User ID or null if creation fails
 */
export async function createTestUser(
  username: string,
  password: string,
  role: 'admin' | 'procurement' | 'sales' = 'admin'
): Promise<string | null> {
  try {
    // Check if test user exists
    const existingUser = await db
      .select()
      .from(users)
      .where(eq(users.username, username))
      .limit(1)

    if (existingUser.length > 0) {
      console.log(`ℹ️  Test user already exists: ${username}`)
      return existingUser[0]?.id || null
    }

    // Create test user
    const passwordHash = await Bun.password.hash(password, {
      algorithm: 'bcrypt',
      cost: 10,
    })

    const newUser = await db
      .insert(users)
      .values({
        username,
        passwordHash,
        role,
      })
      .returning()

    const userId = newUser[0]?.id || null
    if (userId) {
      console.log(`✅ Created test ${role} user: ${username}`)
      // Verify user is visible in database before returning
      let verified = false
      for (let i = 0; i < 5; i++) {
        const verifyUser = await db
          .select()
          .from(users)
          .where(eq(users.id, userId))
          .limit(1)
        if (verifyUser.length > 0) {
          verified = true
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 50))
      }
      if (!verified) {
        console.warn(`⚠️  Warning: User ${username} created but not immediately visible in database`)
      }
    }
    return userId
  } catch (error) {
    console.error(`❌ Failed to create test ${role} user:`, error)
    throw error
  }
}

/**
 * Setup complete test environment with admin user and test data
 * @param prefix - Prefix for test data names
 * @returns Complete test data including admin user
 */
export async function setupTestEnvironment(prefix: string = 'test'): Promise<TestData> {
  const adminUserId = await createTestUser(`test-admin-${prefix}`, 'test-admin-123', 'admin')

  const { categoryId, supplierId, supplierItemId } = await createTestData(prefix)

  return {
    adminUserId,
    categoryId,
    supplierId,
    supplierItemId,
    productIds: [],
  }
}

/**
 * Create a single test product
 * @param categoryId - Optional category ID to link product to
 * @param prefix - Prefix for product name and SKU
 * @param status - Product status (default: 'active')
 * @returns Created product ID
 */
export async function createTestProduct(
  categoryId: string | null = null,
  prefix: string = 'test-product',
  status: 'draft' | 'active' | 'archived' = 'active'
): Promise<string> {
  try {
    const testProduct = await db
      .insert(products)
      .values({
        internalSku: `${prefix}-${Date.now()}`,
        name: `${prefix} Product`,
        categoryId: categoryId || null,
        status,
      })
      .returning()

    const productId = testProduct[0]?.id
    if (!productId) {
      throw new Error('Failed to create test product - no ID returned')
    }
    console.log(`✅ Created test product: ${productId}`)
    return productId
  } catch (error) {
    console.error('❌ Failed to create test product:', error)
    throw error
  }
}

/**
 * Create a new test supplier item
 * @param supplierId - Supplier ID to link item to
 * @param prefix - Prefix for item name and SKU
 * @returns Created supplier item ID
 */
export async function createTestSupplierItem(
  supplierId: string,
  prefix: string = 'test-item'
): Promise<string> {
  try {
    const testSupplierItem = await db
      .insert(supplierItems)
      .values({
        supplierId,
        supplierSku: `${prefix}-${Date.now()}`,
        name: `${prefix} Supplier Item`,
        currentPrice: '29.99',
        characteristics: {},
      })
      .returning()
    
    const itemId = testSupplierItem[0]?.id
    if (!itemId) {
      throw new Error('Failed to create test supplier item - no ID returned')
    }
    console.log(`✅ Created test supplier item: ${itemId}`)
    return itemId
  } catch (error) {
    console.error('❌ Failed to create test supplier item:', error)
    throw error
  }
}

/**
 * Delete a test supplier item
 * @param itemId - Supplier item ID to delete
 */
export async function deleteTestSupplierItem(itemId: string): Promise<void> {
  try {
    await db.delete(supplierItems).where(eq(supplierItems.id, itemId))
    console.log(`✅ Deleted test supplier item: ${itemId}`)
  } catch (error) {
    console.error('⚠️  Error deleting test supplier item:', error)
  }
}

/**
 * Delete a test user
 * @param userId - User ID to delete
 */
export async function deleteTestUser(userId: string): Promise<void> {
  try {
    await db.delete(users).where(eq(users.id, userId))
    console.log(`✅ Deleted test user: ${userId}`)
  } catch (error) {
    console.error('⚠️  Error deleting test user:', error)
  }
}

/**
 * Create test products with different statuses
 * @param categoryId - Optional category ID to link products to
 * @param prefix - Prefix for product names and SKUs
 * @returns Array of created product IDs
 */
export async function createTestProductsWithStatuses(
  categoryId: string | null = null,
  prefix: string = 'test-status'
): Promise<string[]> {
  try {
    const testProducts = await db
      .insert(products)
      .values([
        {
          internalSku: `${prefix}-active-${Date.now()}`,
          name: `${prefix} Active Product`,
          categoryId: categoryId || null,
          status: 'active',
        },
        {
          internalSku: `${prefix}-draft-${Date.now()}`,
          name: `${prefix} Draft Product`,
          categoryId: categoryId || null,
          status: 'draft',
        },
        {
          internalSku: `${prefix}-archived-${Date.now()}`,
          name: `${prefix} Archived Product`,
          categoryId: categoryId || null,
          status: 'archived',
        },
      ])
      .returning()

    const productIds = testProducts.map((p) => p.id)
    console.log(`✅ Created ${productIds.length} test products with different statuses`)
    return productIds
  } catch (error) {
    console.error('❌ Failed to create test products:', error)
    throw error
  }
}

