/**
 * Product Variant Repository
 * 
 * Phase 10: Product Variants
 * 
 * Handles CRUD operations for product_variants table and
 * variant-related queries for products and supplier_items.
 */

import { eq, and, inArray, sql } from 'drizzle-orm'
import type { PostgresJsDatabase } from 'drizzle-orm/postgres-js'
import {
  products,
  productVariants,
  supplierItems,
  suppliers,
} from '../schema/schema'
import type { ProductVariant, NewProductVariant, VariantAttributes } from '../schema/types'

/**
 * Product with variants for API response
 */
export interface ProductWithVariants {
  id: string
  name: string
  internalSku: string
  categoryId: string | null
  status: string
  hasVariants: boolean
  variantSchema: string[] | null
  variants: Array<{
    id: string
    variantKey: string
    variantAttributes: VariantAttributes
    displayOrder: number
    minPrice: string
    maxPrice: string
    supplierCount: number
  }>
}

/**
 * Variant with supplier items
 */
export interface VariantWithItems {
  id: string
  variantKey: string
  variantAttributes: VariantAttributes
  displayOrder: number
  supplierItems: Array<{
    id: string
    supplierId: string
    supplierName: string
    name: string
    price: string
    lastIngestedAt: string
  }>
}

export class VariantRepository {
  constructor(private db: PostgresJsDatabase) {}

  /**
   * Get all variants for a product
   */
  async getVariantsByProductId(productId: string): Promise<ProductVariant[]> {
    return this.db
      .select()
      .from(productVariants)
      .where(eq(productVariants.productId, productId))
      .orderBy(productVariants.displayOrder)
  }

  /**
   * Get a product with all its variants and pricing info
   */
  async getProductWithVariants(productId: string): Promise<ProductWithVariants | null> {
    // Get product
    const [product] = await this.db
      .select()
      .from(products)
      .where(eq(products.id, productId))
      .limit(1)

    if (!product) return null

    // Get variants with aggregated pricing
    const variants = await this.db
      .select({
        id: productVariants.id,
        variantKey: productVariants.variantKey,
        variantAttributes: productVariants.variantAttributes,
        displayOrder: productVariants.displayOrder,
        minPrice: sql<string>`MIN(${supplierItems.currentPrice})`,
        maxPrice: sql<string>`MAX(${supplierItems.currentPrice})`,
        supplierCount: sql<number>`COUNT(DISTINCT ${supplierItems.supplierId})`,
      })
      .from(productVariants)
      .leftJoin(supplierItems, eq(supplierItems.variantId, productVariants.id))
      .where(eq(productVariants.productId, productId))
      .groupBy(
        productVariants.id,
        productVariants.variantKey,
        productVariants.variantAttributes,
        productVariants.displayOrder
      )
      .orderBy(productVariants.displayOrder)

    return {
      id: product.id,
      name: product.name,
      internalSku: product.internalSku,
      categoryId: product.categoryId,
      status: product.status,
      hasVariants: product.hasVariants,
      variantSchema: product.variantSchema as string[] | null,
      variants: variants.map(v => ({
        id: v.id,
        variantKey: v.variantKey,
        variantAttributes: v.variantAttributes as VariantAttributes,
        displayOrder: v.displayOrder,
        minPrice: v.minPrice || '0',
        maxPrice: v.maxPrice || '0',
        supplierCount: Number(v.supplierCount) || 0,
      })),
    }
  }

  /**
   * Get variant details with supplier items
   */
  async getVariantWithItems(variantId: string): Promise<VariantWithItems | null> {
    // Get variant
    const [variant] = await this.db
      .select()
      .from(productVariants)
      .where(eq(productVariants.id, variantId))
      .limit(1)

    if (!variant) return null

    // Get supplier items for this variant
    const items = await this.db
      .select({
        id: supplierItems.id,
        supplierId: supplierItems.supplierId,
        supplierName: suppliers.name,
        name: supplierItems.name,
        price: supplierItems.currentPrice,
        lastIngestedAt: supplierItems.lastIngestedAt,
      })
      .from(supplierItems)
      .innerJoin(suppliers, eq(suppliers.id, supplierItems.supplierId))
      .where(eq(supplierItems.variantId, variantId))
      .orderBy(supplierItems.currentPrice)

    return {
      id: variant.id,
      variantKey: variant.variantKey,
      variantAttributes: variant.variantAttributes as VariantAttributes,
      displayOrder: variant.displayOrder,
      supplierItems: items.map(item => ({
        id: item.id,
        supplierId: item.supplierId,
        supplierName: item.supplierName,
        name: item.name,
        price: item.price,
        lastIngestedAt: item.lastIngestedAt,
      })),
    }
  }

  /**
   * Create a new variant
   */
  async createVariant(data: NewProductVariant): Promise<ProductVariant> {
    const result = await this.db
      .insert(productVariants)
      .values(data)
      .returning()

    const variant = result[0]
    if (!variant) {
      throw new Error('Failed to create variant')
    }

    // Update product.hasVariants flag
    await this.db
      .update(products)
      .set({ hasVariants: true, updatedAt: new Date().toISOString() })
      .where(eq(products.id, data.productId))

    return variant
  }

  /**
   * Create multiple variants for a product
   */
  async createVariants(
    productId: string,
    variants: Array<{ variantKey: string; variantAttributes: VariantAttributes; displayOrder?: number }>
  ): Promise<ProductVariant[]> {
    if (variants.length === 0) return []

    const created = await this.db
      .insert(productVariants)
      .values(
        variants.map((v, idx) => ({
          productId,
          variantKey: v.variantKey,
          variantAttributes: v.variantAttributes,
          displayOrder: v.displayOrder ?? idx,
        }))
      )
      .returning()

    // Update product flags
    const variantSchema = this.extractVariantSchema(variants.map(v => v.variantAttributes))
    await this.db
      .update(products)
      .set({
        hasVariants: true,
        variantSchema: variantSchema,
        updatedAt: new Date().toISOString(),
      })
      .where(eq(products.id, productId))

    return created
  }

  /**
   * Link supplier item to a variant
   */
  async linkSupplierItemToVariant(
    supplierItemId: string,
    variantId: string
  ): Promise<void> {
    await this.db
      .update(supplierItems)
      .set({ variantId, updatedAt: new Date().toISOString() })
      .where(eq(supplierItems.id, supplierItemId))
  }

  /**
   * Unlink supplier item from variant
   */
  async unlinkSupplierItemFromVariant(supplierItemId: string): Promise<void> {
    await this.db
      .update(supplierItems)
      .set({ variantId: null, updatedAt: new Date().toISOString() })
      .where(eq(supplierItems.id, supplierItemId))
  }

  /**
   * Update variant
   */
  async updateVariant(
    variantId: string,
    data: Partial<Pick<ProductVariant, 'variantKey' | 'variantAttributes' | 'displayOrder'>>
  ): Promise<ProductVariant | null> {
    const result = await this.db
      .update(productVariants)
      .set({ ...data, updatedAt: new Date().toISOString() })
      .where(eq(productVariants.id, variantId))
      .returning()

    return result[0] ?? null
  }

  /**
   * Delete variant
   */
  async deleteVariant(variantId: string): Promise<boolean> {
    // Get product_id before deleting
    const [variant] = await this.db
      .select({ productId: productVariants.productId })
      .from(productVariants)
      .where(eq(productVariants.id, variantId))
      .limit(1)

    if (!variant) return false

    // Delete variant (supplier_items.variant_id will be SET NULL via FK)
    await this.db
      .delete(productVariants)
      .where(eq(productVariants.id, variantId))

    // Check if product still has variants
    const remainingVariants = await this.db
      .select({ id: productVariants.id })
      .from(productVariants)
      .where(eq(productVariants.productId, variant.productId))
      .limit(1)

    if (remainingVariants.length === 0) {
      // No more variants - update product flag
      await this.db
        .update(products)
        .set({ hasVariants: false, variantSchema: null, updatedAt: new Date().toISOString() })
        .where(eq(products.id, variant.productId))
    }

    return true
  }

  /**
   * Get products that have variants
   */
  async getProductsWithVariants(limit = 50, offset = 0): Promise<ProductWithVariants[]> {
    const productList = await this.db
      .select()
      .from(products)
      .where(eq(products.hasVariants, true))
      .limit(limit)
      .offset(offset)
      .orderBy(products.name)

    const result: ProductWithVariants[] = []
    for (const product of productList) {
      const withVariants = await this.getProductWithVariants(product.id)
      if (withVariants) result.push(withVariants)
    }

    return result
  }

  /**
   * Extract variant schema from attributes
   */
  private extractVariantSchema(attributesList: VariantAttributes[]): string[] {
    const allKeys = new Set<string>()
    for (const attrs of attributesList) {
      for (const key of Object.keys(attrs)) {
        allKeys.add(key)
      }
    }
    return Array.from(allKeys).sort()
  }
}

