import { Type, Static } from '@sinclair/typebox'

/**
 * Product Pricing TypeBox schemas
 * 
 * Phase 9: Advanced Pricing & Categorization
 * 
 * These schemas define validation for product pricing API endpoints.
 */

// Currency code validation (ISO 4217 format: 3 uppercase letters)
export const CurrencyCodeSchema = Type.String({
  pattern: '^[A-Z]{3}$',
  minLength: 3,
  maxLength: 3,
  description: 'ISO 4217 currency code (e.g., USD, EUR, RUB)',
})

// Non-negative decimal price
export const PriceSchema = Type.Number({
  minimum: 0,
  description: 'Price value (must be non-negative)',
})

/**
 * Request schema for updating product pricing
 * All fields are optional for partial updates
 */
export const UpdateProductPricingRequestSchema = Type.Object(
  {
    retail_price: Type.Optional(
      Type.Union([PriceSchema, Type.Null()], {
        description: 'End-customer price (null to clear)',
      })
    ),
    wholesale_price: Type.Optional(
      Type.Union([PriceSchema, Type.Null()], {
        description: 'Bulk/dealer price (null to clear)',
      })
    ),
    currency_code: Type.Optional(
      Type.Union([CurrencyCodeSchema, Type.Null()], {
        description: 'ISO 4217 currency code (null to clear)',
      })
    ),
  },
  {
    description: 'Partial update for product pricing fields',
    examples: [
      {
        retail_price: 99.99,
        wholesale_price: 79.99,
        currency_code: 'USD',
      },
      {
        retail_price: 149.99,
      },
      {
        currency_code: 'EUR',
      },
    ],
  }
)

export type UpdateProductPricingRequest = Static<typeof UpdateProductPricingRequestSchema>

/**
 * Response schema for product pricing update
 */
export const UpdateProductPricingResponseSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Product UUID' }),
    internal_sku: Type.String({ description: 'Internal SKU code' }),
    name: Type.String({ description: 'Product name' }),
    retail_price: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()], {
      description: 'Updated retail price',
    }),
    wholesale_price: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()], {
      description: 'Updated wholesale price',
    }),
    currency_code: Type.Union([Type.String({ pattern: '^[A-Z]{3}$' }), Type.Null()], {
      description: 'Updated currency code',
    }),
    updated_at: Type.String({ description: 'Timestamp of update' }),
  },
  {
    description: 'Updated product pricing',
    examples: [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        internal_sku: 'PROD-001',
        name: 'USB-C Cable 2m',
        retail_price: '99.99',
        wholesale_price: '79.99',
        currency_code: 'USD',
        updated_at: '2025-12-03T12:00:00Z',
      },
    ],
  }
)

export type UpdateProductPricingResponse = Static<typeof UpdateProductPricingResponseSchema>

/**
 * Product with pricing for detail view
 */
export const ProductDetailSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    internal_sku: Type.String(),
    name: Type.String(),
    category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
    status: Type.Union([
      Type.Literal('draft'),
      Type.Literal('active'),
      Type.Literal('archived'),
    ]),
    // Aggregate fields
    min_price: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()]),
    availability: Type.Boolean(),
    mrp: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()]),
    // Phase 9: Canonical pricing
    retail_price: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()]),
    wholesale_price: Type.Union([Type.String({ pattern: '^\\d+\\.\\d{2}$' }), Type.Null()]),
    currency_code: Type.Union([Type.String({ pattern: '^[A-Z]{3}$' }), Type.Null()]),
    created_at: Type.String(),
    updated_at: Type.String(),
  },
  {
    description: 'Full product details including pricing',
  }
)

export type ProductDetail = Static<typeof ProductDetailSchema>

