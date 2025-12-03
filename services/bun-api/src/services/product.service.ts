import { eq } from 'drizzle-orm'
import { db } from '../db/client'
import { products } from '../db/schema/schema'
import type { UpdateProductPricingRequest, UpdateProductPricingResponse } from '../types/product.types'

/**
 * Product Service
 * 
 * Phase 9: Handles product pricing operations
 */

interface NotFoundError extends Error {
  code: 'NOT_FOUND'
}

interface ValidationError extends Error {
  code: 'VALIDATION_ERROR'
}

/**
 * Update product pricing fields
 * @param productId - Product UUID
 * @param data - Pricing update data
 * @returns Updated product pricing info
 */
export async function updateProductPricing(
  productId: string,
  data: UpdateProductPricingRequest
): Promise<UpdateProductPricingResponse> {
  // Build update object with only provided fields
  const updateData: {
    retailPrice?: string | null
    wholesalePrice?: string | null
    currencyCode?: string | null
    updatedAt: Date
  } = {
    updatedAt: new Date(),
  }

  // Handle retail_price (convert number to string for decimal storage)
  if (data.retail_price !== undefined) {
    updateData.retailPrice = data.retail_price !== null
      ? data.retail_price.toFixed(2)
      : null
  }

  // Handle wholesale_price
  if (data.wholesale_price !== undefined) {
    updateData.wholesalePrice = data.wholesale_price !== null
      ? data.wholesale_price.toFixed(2)
      : null
  }

  // Handle currency_code
  if (data.currency_code !== undefined) {
    updateData.currencyCode = data.currency_code
  }

  // Update product
  const result = await db
    .update(products)
    .set(updateData)
    .where(eq(products.id, productId))
    .returning({
      id: products.id,
      internal_sku: products.internalSku,
      name: products.name,
      retail_price: products.retailPrice,
      wholesale_price: products.wholesalePrice,
      currency_code: products.currencyCode,
      updated_at: products.updatedAt,
    })

  if (!result[0]) {
    const error = new Error(`Product not found: ${productId}`) as NotFoundError
    error.code = 'NOT_FOUND'
    throw error
  }

  const updated = result[0]
  return {
    id: updated.id,
    internal_sku: updated.internal_sku,
    name: updated.name,
    retail_price: updated.retail_price
      ? parseFloat(updated.retail_price).toFixed(2)
      : null,
    wholesale_price: updated.wholesale_price
      ? parseFloat(updated.wholesale_price).toFixed(2)
      : null,
    currency_code: updated.currency_code || null,
    updated_at: updated.updated_at,
  }
}

/**
 * Get product pricing by ID
 * @param productId - Product UUID
 * @returns Product pricing info
 */
export async function getProductPricing(productId: string): Promise<UpdateProductPricingResponse | null> {
  const result = await db
    .select({
      id: products.id,
      internal_sku: products.internalSku,
      name: products.name,
      retail_price: products.retailPrice,
      wholesale_price: products.wholesalePrice,
      currency_code: products.currencyCode,
      updated_at: products.updatedAt,
    })
    .from(products)
    .where(eq(products.id, productId))
    .limit(1)

  if (!result[0]) {
    return null
  }

  const product = result[0]
  return {
    id: product.id,
    internal_sku: product.internal_sku,
    name: product.name,
    retail_price: product.retail_price
      ? parseFloat(product.retail_price).toFixed(2)
      : null,
    wholesale_price: product.wholesale_price
      ? parseFloat(product.wholesale_price).toFixed(2)
      : null,
    currency_code: product.currency_code || null,
    updated_at: product.updated_at,
  }
}

/**
 * Validate currency code format (ISO 4217)
 * @param code - Currency code to validate
 * @returns true if valid
 */
export function isValidCurrencyCode(code: string): boolean {
  return /^[A-Z]{3}$/.test(code)
}

// Export service object for consistent usage
export const productService = {
  updateProductPricing,
  getProductPricing,
  isValidCurrencyCode,
}

