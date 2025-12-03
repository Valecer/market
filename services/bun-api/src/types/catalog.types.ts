import { Type, Static } from '@sinclair/typebox'

/**
 * Catalog-related TypeBox schemas
 *
 * Based on catalog-api.json contract
 */

export const CatalogQuerySchema = Type.Object({
  category_id: Type.Optional(
    Type.String({ format: 'uuid', description: 'Filter by category UUID' })
  ),
  min_price: Type.Optional(
    Type.Union([Type.Number({ minimum: 0 }), Type.String()], {
      description: 'Minimum price threshold',
    })
  ),
  max_price: Type.Optional(
    Type.Union([Type.Number({ minimum: 0 }), Type.String()], {
      description: 'Maximum price threshold',
    })
  ),
  search: Type.Optional(
    Type.String({ minLength: 1, maxLength: 255, description: 'Full-text search on product name' })
  ),
  page: Type.Optional(
    Type.Union([Type.Integer({ minimum: 1 }), Type.String()], {
      description: 'Page number (default: 1)',
    })
  ),
  limit: Type.Optional(
    Type.Union([Type.Integer({ minimum: 1, maximum: 200 }), Type.String()], {
      description: 'Items per page (default: 50, max: 200)',
    })
  ),
})

export type CatalogQuery = Static<typeof CatalogQuerySchema>

// Phase 9: Currency code validation schema (ISO 4217 format)
export const CurrencyCodeSchema = Type.Union(
  [
    Type.String({
      pattern: '^[A-Z]{3}$',
      description: 'ISO 4217 currency code (3 uppercase letters, e.g., USD, EUR, RUB)',
    }),
    Type.Null(),
  ],
  { description: 'Currency code or null' }
)

// Phase 9: Decimal price schema (non-negative, 2 decimal places)
export const PriceDecimalSchema = Type.Union(
  [
    Type.String({
      pattern: '^\\d+\\.\\d{2}$',
      description: 'Price as decimal string (e.g., "99.99")',
    }),
    Type.Null(),
  ],
  { description: 'Price or null' }
)

export const CatalogProductSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Product UUID' }),
    internal_sku: Type.String({ maxLength: 100, description: 'Internal SKU code' }),
    name: Type.String({ maxLength: 500, description: 'Product name' }),
    category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()], {
      description: 'Category UUID or null',
    }),
    min_price: Type.String({
      pattern: '^\\d+\\.\\d{2}$',
      description: 'Lowest supplier price as decimal string (e.g., "9.99")',
    }),
    max_price: Type.String({
      pattern: '^\\d+\\.\\d{2}$',
      description: 'Highest supplier price as decimal string',
    }),
    supplier_count: Type.Integer({ minimum: 0, description: 'Number of suppliers for this product' }),
    // Phase 9: Canonical pricing fields
    retail_price: PriceDecimalSchema,
    wholesale_price: PriceDecimalSchema,
    currency_code: CurrencyCodeSchema,
  },
  {
    examples: [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        internal_sku: 'PROD-001',
        name: 'USB-C Cable 2m',
        category_id: '660e8400-e29b-41d4-a716-446655440000',
        min_price: '9.99',
        max_price: '14.99',
        supplier_count: 3,
        retail_price: '14.99',
        wholesale_price: '11.99',
        currency_code: 'USD',
      },
    ],
  }
)

export type CatalogProduct = Static<typeof CatalogProductSchema>

export const CatalogResponseSchema = Type.Object(
  {
    total_count: Type.Integer({ minimum: 0, description: 'Total number of matching products' }),
    page: Type.Integer({ minimum: 1, description: 'Current page number' }),
    limit: Type.Integer({ minimum: 1, description: 'Items per page' }),
    data: Type.Array(CatalogProductSchema, { description: 'Array of catalog products' }),
  },
  {
    examples: [
      {
        total_count: 42,
        page: 1,
        limit: 50,
        data: [
          {
            id: '550e8400-e29b-41d4-a716-446655440000',
            internal_sku: 'PROD-001',
            name: 'USB-C Cable 2m',
            category_id: '660e8400-e29b-41d4-a716-446655440000',
            min_price: '9.99',
            max_price: '14.99',
            supplier_count: 3,
          },
        ],
      },
    ],
  }
)

export type CatalogResponse = Static<typeof CatalogResponseSchema>

