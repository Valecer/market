/**
 * Product Variant Types
 * 
 * Phase 10: Product Variants
 * 
 * TypeScript types for product variants feature.
 */

/**
 * Variant attributes (key-value pairs)
 */
export type VariantAttributes = Record<string, string | number>

/**
 * Product variant from API
 */
export interface ProductVariant {
  id: string
  variantKey: string
  variantAttributes: VariantAttributes
  displayOrder: number
  minPrice: string
  maxPrice: string
  supplierCount: number
}

/**
 * Product with variants from API
 */
export interface ProductWithVariants {
  id: string
  name: string
  internalSku: string
  categoryId: string | null
  status: string
  hasVariants: boolean
  variantSchema: string[] | null
  variants: ProductVariant[]
}

/**
 * Supplier item linked to a variant
 */
export interface VariantSupplierItem {
  id: string
  supplierId: string
  supplierName: string
  name: string
  price: string
  lastIngestedAt: string
}

/**
 * Variant with full supplier items
 */
export interface VariantWithItems {
  id: string
  variantKey: string
  variantAttributes: VariantAttributes
  displayOrder: number
  supplierItems: VariantSupplierItem[]
}

/**
 * Create variant request
 */
export interface CreateVariantRequest {
  productId: string
  variantKey: string
  variantAttributes: VariantAttributes
  displayOrder?: number
}

/**
 * Link supplier item to variant request
 */
export interface LinkVariantRequest {
  supplierItemId: string
  variantId: string
}

/**
 * Common variant attribute keys
 */
export const VARIANT_ATTRIBUTE_KEYS = [
  'voltage',
  'capacity',
  'power',
  'storage',
  'ram',
  'color',
  'size',
  'model',
  'year',
] as const

export type VariantAttributeKey = typeof VARIANT_ATTRIBUTE_KEYS[number]

