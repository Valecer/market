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

export const SupplierItemDetailSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Supplier item UUID' }),
    supplier_id: Type.String({ format: 'uuid', description: 'Supplier UUID' }),
    supplier_name: Type.String({ description: 'Supplier company name' }),
    supplier_sku: Type.String({ description: 'SKU used by the supplier' }),
    current_price: Type.String({
      pattern: '^\\d+\\.\\d{2}$',
      description: 'Current price as decimal string (e.g., "19.99")',
    }),
    characteristics: Type.Record(Type.String(), Type.Any(), {
      description: 'Flexible JSONB attributes from supplier data',
    }),
    last_ingested_at: Type.String({
      format: 'date-time',
      description: 'ISO-8601 timestamp of last data sync',
    }),
  },
  {
    examples: [
      {
        id: '770e8400-e29b-41d4-a716-446655440000',
        supplier_id: '880e8400-e29b-41d4-a716-446655440000',
        supplier_name: 'TechSupplier Inc',
        supplier_sku: 'TS-USB-C-2M',
        current_price: '9.99',
        characteristics: { color: 'black', length: '2m' },
        last_ingested_at: '2025-11-28T10:30:00Z',
      },
    ],
  }
)

export type SupplierItemDetail = Static<typeof SupplierItemDetailSchema>

export const AdminProductSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Product UUID' }),
    internal_sku: Type.String({ description: 'Internal SKU code' }),
    name: Type.String({ description: 'Product name' }),
    category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()], {
      description: 'Category UUID or null',
    }),
    status: ProductStatusSchema,
    supplier_items: Type.Array(SupplierItemDetailSchema, {
      description: 'Array of linked supplier items with pricing',
    }),
    margin_percentage: Type.Union([Type.Number(), Type.Null()], {
      description: 'Calculated margin: (target - min_price) / target * 100',
    }),
  },
  {
    examples: [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        internal_sku: 'PROD-001',
        name: 'USB-C Cable 2m',
        category_id: '660e8400-e29b-41d4-a716-446655440000',
        status: 'active',
        supplier_items: [
          {
            id: '770e8400-e29b-41d4-a716-446655440000',
            supplier_id: '880e8400-e29b-41d4-a716-446655440000',
            supplier_name: 'TechSupplier Inc',
            supplier_sku: 'TS-USB-C-2M',
            current_price: '9.99',
            characteristics: { color: 'black', length: '2m' },
            last_ingested_at: '2025-11-28T10:30:00Z',
          },
        ],
        margin_percentage: 25.5,
      },
    ],
  }
)

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

export const MatchRequestSchema = Type.Object(
  {
    action: Type.Union([Type.Literal('link'), Type.Literal('unlink')], {
      description: 'Action to perform: link to create association, unlink to remove it',
    }),
    supplier_item_id: Type.String({
      format: 'uuid',
      description: 'UUID of the supplier item to link/unlink',
    }),
  },
  {
    examples: [
      { action: 'link', supplier_item_id: '770e8400-e29b-41d4-a716-446655440000' },
      { action: 'unlink', supplier_item_id: '770e8400-e29b-41d4-a716-446655440000' },
    ],
  }
)

export type MatchRequest = Static<typeof MatchRequestSchema>

export const MatchResponseSchema = Type.Object(
  {
    product: AdminProductSchema,
  },
  {
    description: 'Returns the updated product with all linked supplier items',
  }
)

export type MatchResponse = Static<typeof MatchResponseSchema>

export const CreateProductRequestSchema = Type.Object(
  {
    internal_sku: Type.Optional(
      Type.String({
        maxLength: 100,
        description: 'Custom internal SKU. If not provided, one will be auto-generated.',
      })
    ),
    name: Type.String({
      minLength: 1,
      maxLength: 500,
      description: 'Product name (required)',
    }),
    category_id: Type.Optional(
      Type.String({
        format: 'uuid',
        description: 'Category UUID to assign the product to',
      })
    ),
    status: Type.Optional(
      Type.Union([Type.Literal('draft'), Type.Literal('active')], {
        default: 'draft',
        description: 'Initial product status (default: draft)',
      })
    ),
    supplier_item_id: Type.Optional(
      Type.String({
        format: 'uuid',
        description: 'Supplier item UUID to link on creation (split SKU workflow)',
      })
    ),
  },
  {
    examples: [
      {
        name: 'USB-C Cable 2m',
        category_id: '660e8400-e29b-41d4-a716-446655440000',
        status: 'draft',
      },
      {
        internal_sku: 'HDMI-3M-001',
        name: 'HDMI Cable 3m',
        category_id: '660e8400-e29b-41d4-a716-446655440000',
        status: 'draft',
        supplier_item_id: '770e8400-e29b-41d4-a716-446655440000',
      },
    ],
  }
)

export type CreateProductRequest = Static<typeof CreateProductRequestSchema>

export const CreateProductResponseSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Newly created product UUID' }),
    internal_sku: Type.String({ description: 'Internal SKU (auto-generated or provided)' }),
    name: Type.String({ description: 'Product name' }),
    category_id: Type.Union([Type.String({ format: 'uuid' }), Type.Null()], {
      description: 'Category UUID or null',
    }),
    status: Type.Union([Type.Literal('draft'), Type.Literal('active')], {
      description: 'Product status',
    }),
    supplier_items: Type.Array(SupplierItemDetailSchema, {
      description: 'Linked supplier items (may be empty if no supplier_item_id provided)',
    }),
    created_at: Type.String({ format: 'date-time', description: 'Creation timestamp' }),
  },
  {
    examples: [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        internal_sku: 'MKT-20251128-ABC123',
        name: 'USB-C Cable 2m',
        category_id: '660e8400-e29b-41d4-a716-446655440000',
        status: 'draft',
        supplier_items: [],
        created_at: '2025-11-28T10:30:00Z',
      },
    ],
  }
)

export type CreateProductResponse = Static<typeof CreateProductResponseSchema>

export const SyncRequestSchema = Type.Object(
  {
    supplier_id: Type.String({
      format: 'uuid',
      description: 'UUID of the supplier to synchronize data for',
    }),
  },
  {
    examples: [{ supplier_id: '880e8400-e29b-41d4-a716-446655440000' }],
  }
)

export type SyncRequest = Static<typeof SyncRequestSchema>

export const SyncResponseSchema = Type.Object(
  {
    task_id: Type.String({
      format: 'uuid',
      description: 'Unique identifier for tracking the background task',
    }),
    supplier_id: Type.String({
      format: 'uuid',
      description: 'UUID of the supplier being synchronized',
    }),
    status: Type.Literal('queued', {
      description: 'Task status - always "queued" on successful enqueue',
    }),
    enqueued_at: Type.String({
      format: 'date-time',
      description: 'ISO-8601 timestamp when the task was enqueued',
    }),
  },
  {
    examples: [
      {
        task_id: '990e8400-e29b-41d4-a716-446655440000',
        supplier_id: '880e8400-e29b-41d4-a716-446655440000',
        status: 'queued',
        enqueued_at: '2025-11-28T10:30:00Z',
      },
    ],
  }
)

export type SyncResponse = Static<typeof SyncResponseSchema>

// =============================================================================
// Unmatched Supplier Items Types
// =============================================================================

export const UnmatchedQuerySchema = Type.Object({
  supplier_id: Type.Optional(Type.String({ format: 'uuid' })),
  search: Type.Optional(Type.String()),
  page: Type.Optional(Type.Integer({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200, default: 50 })),
})

export type UnmatchedQuery = Static<typeof UnmatchedQuerySchema>

export const UnmatchedSupplierItemSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid', description: 'Supplier item UUID' }),
    supplier_id: Type.String({ format: 'uuid', description: 'Supplier UUID' }),
    supplier_name: Type.String({ description: 'Supplier company name' }),
    supplier_sku: Type.String({ description: 'SKU used by the supplier' }),
    name: Type.String({ description: 'Item name from supplier' }),
    current_price: Type.String({
      description: 'Current price as decimal string (e.g., "19.99")',
    }),
    characteristics: Type.Record(Type.String(), Type.Any(), {
      description: 'Flexible JSONB attributes from supplier data',
    }),
    last_ingested_at: Type.String({
      format: 'date-time',
      description: 'ISO-8601 timestamp of last data sync',
    }),
  },
  {
    examples: [
      {
        id: '770e8400-e29b-41d4-a716-446655440000',
        supplier_id: '880e8400-e29b-41d4-a716-446655440000',
        supplier_name: 'TechSupplier Inc',
        supplier_sku: 'TS-HDMI-3M',
        name: 'HDMI Cable 3m',
        current_price: '12.99',
        characteristics: { color: 'black', length: '3m' },
        last_ingested_at: '2025-11-28T10:30:00Z',
      },
    ],
  }
)

export type UnmatchedSupplierItem = Static<typeof UnmatchedSupplierItemSchema>

export const UnmatchedResponseSchema = Type.Object({
  total_count: Type.Integer({ minimum: 0 }),
  page: Type.Integer({ minimum: 1 }),
  limit: Type.Integer({ minimum: 1 }),
  data: Type.Array(UnmatchedSupplierItemSchema),
})

export type UnmatchedResponse = Static<typeof UnmatchedResponseSchema>

