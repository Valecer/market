/**
 * Product Types
 * 
 * Phase 9: Advanced Pricing & Categorization
 * 
 * Types for product pricing display in frontend.
 */

/**
 * Product with pricing fields (Phase 9)
 * 
 * Includes both aggregate pricing (min_price, max_price) from supplier items
 * and canonical pricing (retail_price, wholesale_price) at product level.
 */
export interface ProductPricing {
  /** Product UUID */
  id: string
  /** Internal SKU code */
  internal_sku: string
  /** Product name */
  name: string
  /** Category UUID or null */
  category_id: string | null
  /** Product status */
  status: 'draft' | 'active' | 'archived'
  
  // Aggregate pricing (from supplier items)
  /** Lowest supplier price as decimal string (e.g., "9.99") */
  min_price: string
  /** Highest supplier price as decimal string */
  max_price: string
  /** Number of suppliers for this product */
  supplier_count: number
  
  // Phase 9: Canonical pricing fields
  /** End-customer price (canonical product-level) - null if not set */
  retail_price: string | null
  /** Bulk/dealer price (canonical product-level) - null if not set */
  wholesale_price: string | null
  /** ISO 4217 currency code (e.g., "USD", "EUR", "RUB") - null if not set */
  currency_code: string | null
}

/**
 * Price display props for formatting
 */
export interface PriceDisplayProps {
  /** Price value as string or number */
  price: string | number | null | undefined
  /** ISO 4217 currency code */
  currencyCode?: string | null
  /** Whether to show currency code after price */
  showCurrency?: boolean
  /** Custom class name */
  className?: string
  /** Size variant */
  size?: 'sm' | 'md' | 'lg'
  /** Placeholder text for null/undefined prices */
  placeholder?: string
}

/**
 * Dual pricing display props
 */
export interface DualPricingProps {
  /** Retail/end-customer price */
  retailPrice: string | null
  /** Wholesale/dealer price */
  wholesalePrice: string | null
  /** ISO 4217 currency code */
  currencyCode?: string | null
  /** Whether to show both prices or just primary */
  showBoth?: boolean
  /** Custom class name */
  className?: string
}

/**
 * Common currency codes used in the system
 */
export type CurrencyCode = 'USD' | 'EUR' | 'RUB' | 'CNY' | 'BYN' | 'GBP' | 'JPY'

/**
 * Currency display configuration
 */
export const CURRENCY_CONFIG: Record<string, { symbol: string; position: 'before' | 'after' }> = {
  USD: { symbol: '$', position: 'before' },
  EUR: { symbol: '€', position: 'before' },
  RUB: { symbol: '₽', position: 'after' },
  CNY: { symbol: '¥', position: 'before' },
  BYN: { symbol: 'Br', position: 'after' },
  GBP: { symbol: '£', position: 'before' },
  JPY: { symbol: '¥', position: 'before' },
}

