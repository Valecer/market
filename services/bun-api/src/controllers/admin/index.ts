import { Elysia, t } from 'elysia'
import { adminService } from '../../services/admin.service'
import { AdminQuerySchema, AdminProductsResponseSchema, MatchRequestSchema, MatchResponseSchema } from '../../types/admin.types'
import { createErrorResponse } from '../../types/errors'
import { authMiddleware, requireAuth } from '../../middleware/auth'
import { requireSales } from '../../middleware/rbac'

/**
 * Admin Controller
 * 
 * Handles HTTP requests for admin operations.
 * Requires authentication and appropriate role permissions.
 */

export const adminController = new Elysia({ prefix: '/api/v1/admin' })
  .use(authMiddleware) // Extract user from JWT token - must be before guard
  .guard({
    beforeHandle({ user, set }) {
      if (!user) {
        set.status = 401
        return {
          error: {
            code: 'UNAUTHORIZED',
            message: 'Unauthorized',
          },
        }
      }
      // Check role
      if (!['sales', 'procurement', 'admin'].includes(user.role)) {
        set.status = 403
        return {
          error: {
            code: 'FORBIDDEN',
            message: 'Forbidden: Insufficient permissions',
          },
        }
      }
    },
  })
  .get(
    '/products',
    async ({ query, set, user }) => {
      try {
        // Transform and normalize query parameters
        // Query params come as strings, so we need to coerce them
        const adminQuery = {
          status: query.status && typeof query.status === 'string'
            ? (query.status === 'draft' || query.status === 'active' || query.status === 'archived' 
                ? query.status 
                : undefined)
            : undefined,
          min_margin: query.min_margin !== undefined && query.min_margin !== null && query.min_margin !== ''
            ? (typeof query.min_margin === 'string' ? parseFloat(query.min_margin) : Number(query.min_margin))
            : undefined,
          max_margin: query.max_margin !== undefined && query.max_margin !== null && query.max_margin !== ''
            ? (typeof query.max_margin === 'string' ? parseFloat(query.max_margin) : Number(query.max_margin))
            : undefined,
          supplier_id: query.supplier_id && typeof query.supplier_id === 'string'
            ? query.supplier_id
            : undefined,
          page: query.page !== undefined && query.page !== null && query.page !== ''
            ? (typeof query.page === 'string' ? parseInt(query.page, 10) : Number(query.page)) || 1
            : 1,
          limit: query.limit !== undefined && query.limit !== null && query.limit !== ''
            ? (typeof query.limit === 'string' ? parseInt(query.limit, 10) : Number(query.limit)) || 50
            : 50,
        }

        // Validate supplier_id format (UUID)
        if (adminQuery.supplier_id !== undefined) {
          const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
          if (!uuidRegex.test(adminQuery.supplier_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'supplier_id must be a valid UUID')
          }
        }

        // Validate margin constraints
        if (adminQuery.min_margin !== undefined && (isNaN(adminQuery.min_margin) || adminQuery.min_margin < 0 || adminQuery.min_margin > 100)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'min_margin must be between 0 and 100')
        }

        if (adminQuery.max_margin !== undefined && (isNaN(adminQuery.max_margin) || adminQuery.max_margin < 0 || adminQuery.max_margin > 100)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'max_margin must be between 0 and 100')
        }

        if (adminQuery.min_margin !== undefined && adminQuery.max_margin !== undefined) {
          if (adminQuery.min_margin > adminQuery.max_margin) {
            set.status = 400
            return createErrorResponse(
              'VALIDATION_ERROR',
              'min_margin must be less than or equal to max_margin'
            )
          }
        }

        // Validate pagination constraints
        if (adminQuery.page < 1) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'page must be greater than or equal to 1')
        }

        if (adminQuery.limit < 1 || adminQuery.limit > 200) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'limit must be between 1 and 200')
        }

        // Call admin service to get products
        const response = await adminService.getAdminProducts(adminQuery)

        set.status = 200
        return response
      } catch (error) {
        // Re-throw to be caught by error handler middleware
        throw error
      }
    },
    {
      // Use a permissive query schema - all parameters are optional strings
      // We'll handle type coercion and validation in the handler
      query: t.Object({
        status: t.Optional(t.Any()),
        min_margin: t.Optional(t.Any()),
        max_margin: t.Optional(t.Any()),
        supplier_id: t.Optional(t.Any()),
        page: t.Optional(t.Any()),
        limit: t.Optional(t.Any()),
      }),
      error({ code, error, set }) {
        // Handle validation errors - convert 422 to 400 to match API contract
        if (code === 'VALIDATION') {
          set.status = 400
          return createErrorResponse(
            'VALIDATION_ERROR',
            'Invalid query parameters',
            {
              issue: error.message,
            }
          )
        }
      },
      response: {
        200: AdminProductsResponseSchema,
        400: t.Object({
          error: t.Object({
            code: t.Literal('VALIDATION_ERROR'),
            message: t.String(),
            details: t.Optional(t.Object({})),
          }),
        }),
        401: t.Object({
          error: t.Object({
            code: t.Literal('UNAUTHORIZED'),
            message: t.String(),
          }),
        }),
        500: t.Object({
          error: t.Object({
            code: t.Literal('INTERNAL_ERROR'),
            message: t.String(),
          }),
        }),
      },
      detail: {
        tags: ['admin'],
        summary: 'Get paginated admin products with supplier details',
        description:
          'Returns a paginated list of all products (draft, active, archived) with supplier item details and calculated margins. Requires authentication with sales, procurement, or admin role.',
        examples: [
          {
            description: 'Get first page of all products',
            value: {
              request: {
                headers: {
                  Authorization: 'Bearer <jwt-token>',
                },
                query: {
                  page: 1,
                  limit: 50,
                },
              },
              response: {
                total_count: 150,
                page: 1,
                limit: 50,
                data: [
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
                        characteristics: {
                          color: 'black',
                          length: '2m',
                        },
                        last_ingested_at: '2025-11-26T10:30:00Z',
                      },
                    ],
                    margin_percentage: null,
                  },
                ],
              },
            },
          },
          {
            description: 'Filter by status and supplier',
            value: {
              request: {
                headers: {
                  Authorization: 'Bearer <jwt-token>',
                },
                query: {
                  status: 'active',
                  supplier_id: '880e8400-e29b-41d4-a716-446655440000',
                  page: 1,
                  limit: 20,
                },
              },
              response: {
                total_count: 25,
                page: 1,
                limit: 20,
                data: [],
              },
            },
          },
        ],
      },
    }
  )
  .patch(
    '/products/:id/match',
    async ({ params, body, set, user }) => {
      try {
        // Validate product ID format (UUID)
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
        if (!uuidRegex.test(params.id)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'Product ID must be a valid UUID')
        }

        // Validate supplier_item_id format (UUID)
        if (!uuidRegex.test(body.supplier_item_id)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'supplier_item_id must be a valid UUID')
        }

        // Call admin service to match product
        const response = await adminService.matchProduct(params.id, body)

        set.status = 200
        return response
      } catch (error: any) {
        // Re-throw to be caught by error handler middleware
        throw error
      }
    },
    {
      body: MatchRequestSchema,
      beforeHandle({ user, set }) {
        // Check role: procurement or admin only
        if (!user) {
          set.status = 401
          return {
            error: {
              code: 'UNAUTHORIZED',
              message: 'Unauthorized',
            },
          }
        }
        if (!['procurement', 'admin'].includes(user.role)) {
          set.status = 403
          return {
            error: {
              code: 'FORBIDDEN',
              message: 'Forbidden: Insufficient permissions. Procurement or admin role required.',
            },
          }
        }
      },
      error({ code, error, set }) {
        // Handle validation errors - convert 422 to 400 to match API contract
        if (code === 'VALIDATION') {
          set.status = 400
          return createErrorResponse(
            'VALIDATION_ERROR',
            'Invalid request body',
            {
              issue: error.message,
            }
          )
        }
      },
      response: {
        200: MatchResponseSchema,
        400: t.Object({
          error: t.Object({
            code: t.Union([
              t.Literal('VALIDATION_ERROR'),
              t.Literal('NOT_FOUND'),
            ]),
            message: t.String(),
            details: t.Optional(t.Object({})),
          }),
        }),
        401: t.Object({
          error: t.Object({
            code: t.Literal('UNAUTHORIZED'),
            message: t.String(),
          }),
        }),
        403: t.Object({
          error: t.Object({
            code: t.Literal('FORBIDDEN'),
            message: t.String(),
          }),
        }),
        404: t.Object({
          error: t.Object({
            code: t.Union([
              t.Literal('NOT_FOUND'),
            ]),
            message: t.String(),
          }),
        }),
        409: t.Object({
          error: t.Object({
            code: t.Literal('CONFLICT'),
            message: t.String(),
          }),
        }),
        500: t.Object({
          error: t.Object({
            code: t.Literal('INTERNAL_ERROR'),
            message: t.String(),
          }),
        }),
      },
      detail: {
        tags: ['admin'],
        summary: 'Link or unlink supplier item to product',
        description:
          'Manually link or unlink a supplier item to/from a product. Requires procurement or admin role. Cannot link to archived products. Returns updated product with all supplier items.',
        examples: [
          {
            description: 'Link supplier item to product',
            value: {
              request: {
                headers: {
                  Authorization: 'Bearer <jwt-token>',
                },
                params: {
                  id: '550e8400-e29b-41d4-a716-446655440000',
                },
                body: {
                  action: 'link',
                  supplier_item_id: '770e8400-e29b-41d4-a716-446655440000',
                },
              },
              response: {
                product: {
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
                      characteristics: {
                        color: 'black',
                        length: '2m',
                      },
                      last_ingested_at: '2025-11-26T10:30:00Z',
                    },
                  ],
                  margin_percentage: null,
                },
              },
            },
          },
          {
            description: 'Unlink supplier item from product',
            value: {
              request: {
                headers: {
                  Authorization: 'Bearer <jwt-token>',
                },
                params: {
                  id: '550e8400-e29b-41d4-a716-446655440000',
                },
                body: {
                  action: 'unlink',
                  supplier_item_id: '770e8400-e29b-41d4-a716-446655440000',
                },
              },
              response: {
                product: {
                  id: '550e8400-e29b-41d4-a716-446655440000',
                  internal_sku: 'PROD-001',
                  name: 'USB-C Cable 2m',
                  category_id: '660e8400-e29b-41d4-a716-446655440000',
                  status: 'active',
                  supplier_items: [],
                  margin_percentage: null,
                },
              },
            },
          },
        ],
      },
    }
  )

