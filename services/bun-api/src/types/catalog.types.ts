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

