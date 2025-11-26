import { Type, Static } from '@sinclair/typebox'

/**
 * Catalog-related TypeBox schemas
 * 
 * Based on catalog-api.json contract
 */

export const CatalogQuerySchema = Type.Object({
  category_id: Type.Optional(Type.String({ format: 'uuid' })),
  min_price: Type.Optional(Type.Number({ minimum: 0 })),
  max_price: Type.Optional(Type.Number({ minimum: 0 })),
  search: Type.Optional(Type.String({ minLength: 1, maxLength: 255 })),
  page: Type.Optional(Type.Integer({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200, default: 50 })),
})

export type CatalogQuery = Static<typeof CatalogQuerySchema>

export const CatalogProductSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  internal_sku: Type.String({ maxLength: 100 }),
  name: Type.String({ maxLength: 500 }),
  category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  min_price: Type.String({ pattern: '^\\d+\\.\\d{2}$' }), // Decimal as string
  max_price: Type.String({ pattern: '^\\d+\\.\\d{2}$' }),
  supplier_count: Type.Integer({ minimum: 0 }),
})

export type CatalogProduct = Static<typeof CatalogProductSchema>

export const CatalogResponseSchema = Type.Object({
  total_count: Type.Integer({ minimum: 0 }),
  page: Type.Integer({ minimum: 1 }),
  limit: Type.Integer({ minimum: 1 }),
  data: Type.Array(CatalogProductSchema),
})

export type CatalogResponse = Static<typeof CatalogResponseSchema>

