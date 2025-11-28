/**
 * SKU Generator Utility
 * 
 * Generates unique internal SKUs for products
 * Format: PROD-{timestamp}-{random}
 */

/**
 * Generate a unique internal SKU
 * 
 * Format: PROD-{timestamp}-{random}
 * Example: PROD-1732623600000-a3f5
 * 
 * @returns A unique SKU string
 */
export function generateInternalSku(): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(2, 6).toUpperCase()
  return `PROD-${timestamp}-${random}`
}

/**
 * Validate SKU format
 * 
 * @param sku - The SKU to validate
 * @returns true if the SKU matches the expected format
 */
export function isValidSkuFormat(sku: string): boolean {
  const pattern = /^PROD-\d+-[A-Z0-9]{4}$/
  return pattern.test(sku)
}

