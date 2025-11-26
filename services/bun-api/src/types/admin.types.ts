import { Type, Static } from '@sinclair/typebox'

/**
 * Admin-related TypeBox schemas
 * 
 * Based on admin-api.json contract
 */

export const ProductStatusSchema = Type.Union([
  Type.Literal('draft'),
  Type.Literal('active'),
  Type.Literal('archived'),
])

export type ProductStatus = Static<typeof ProductStatusSchema>

export const SupplierItemDetailSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  supplier_id: Type.String({ format: 'uuid' }),
  supplier_name: Type.String(),
  supplier_sku: Type.String(),
  current_price: Type.String({ pattern: '^\\d+\\.\\d{2}$' }), // Decimal as string
  characteristics: Type.Record(Type.String(), Type.Any()), // JSONB
  last_ingested_at: Type.String({ format: 'date-time' }),
})

export type SupplierItemDetail = Static<typeof SupplierItemDetailSchema>

export const AdminProductSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  internal_sku: Type.String(),
  name: Type.String(),
  category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  status: ProductStatusSchema,
  supplier_items: Type.Array(SupplierItemDetailSchema),
  margin_percentage: Type.Union([Type.Number(), Type.Null()]),
})

export type AdminProduct = Static<typeof AdminProductSchema>

export const AdminProductsResponseSchema = Type.Object({
  total_count: Type.Integer({ minimum: 0 }),
  page: Type.Integer({ minimum: 1 }),
  limit: Type.Integer({ minimum: 1 }),
  data: Type.Array(AdminProductSchema),
})

export type AdminProductsResponse = Static<typeof AdminProductsResponseSchema>

export const AdminQuerySchema = Type.Object({
  status: Type.Optional(ProductStatusSchema),
  min_margin: Type.Optional(Type.Number({ minimum: 0, maximum: 100 })),
  max_margin: Type.Optional(Type.Number({ minimum: 0, maximum: 100 })),
  supplier_id: Type.Optional(Type.String({ format: 'uuid' })),
  page: Type.Optional(Type.Integer({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200, default: 50 })),
})

export type AdminQuery = Static<typeof AdminQuerySchema>

export const MatchRequestSchema = Type.Object({
  action: Type.Union([Type.Literal('link'), Type.Literal('unlink')]),
  supplier_item_id: Type.String({ format: 'uuid' }),
})

export type MatchRequest = Static<typeof MatchRequestSchema>

export const MatchResponseSchema = Type.Object({
  product: AdminProductSchema,
})

export type MatchResponse = Static<typeof MatchResponseSchema>

export const CreateProductRequestSchema = Type.Object({
  internal_sku: Type.Optional(Type.String({ maxLength: 100 })),
  name: Type.String({ minLength: 1, maxLength: 500 }),
  category_id: Type.Optional(Type.String({ format: 'uuid' })),
  status: Type.Optional(Type.Union([Type.Literal('draft'), Type.Literal('active')])),
  supplier_item_id: Type.Optional(Type.String({ format: 'uuid' })),
})

export type CreateProductRequest = Static<typeof CreateProductRequestSchema>

export const CreateProductResponseSchema = Type.Object({
  id: Type.String({ format: 'uuid' }),
  internal_sku: Type.String(),
  name: Type.String(),
  category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()]),
  status: Type.Union([Type.Literal('draft'), Type.Literal('active')]),
  supplier_items: Type.Array(SupplierItemDetailSchema),
  created_at: Type.String({ format: 'date-time' }),
})

export type CreateProductResponse = Static<typeof CreateProductResponseSchema>

export const SyncRequestSchema = Type.Object({
  supplier_id: Type.String({ format: 'uuid' }),
})

export type SyncRequest = Static<typeof SyncRequestSchema>

export const SyncResponseSchema = Type.Object({
  task_id: Type.String({ format: 'uuid' }),
  supplier_id: Type.String({ format: 'uuid' }),
  status: Type.Literal('queued'),
  enqueued_at: Type.String({ format: 'date-time' }),
})

export type SyncResponse = Static<typeof SyncResponseSchema>

