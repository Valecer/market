import { Elysia, t } from 'elysia'
import { catalogService } from '../../services/catalog.service'
import { CatalogQuerySchema, CatalogResponseSchema } from '../../types/catalog.types'
import { createErrorResponse } from '../../types/errors'

/**
 * Catalog Controller
 * 
 * Handles HTTP requests for public catalog endpoints.
 * No business logic - delegates to CatalogService.
 */

export const catalogController = new Elysia({ prefix: '/api/v1/catalog' })
  .get(
    '/',
    async ({ query, set }) => {
      try {
        // Transform and normalize query parameters
        // Query params come as strings, so we need to coerce them
        const catalogQuery = {
          category_id: query.category_id && typeof query.category_id === 'string' 
            ? query.category_id 
            : undefined,
          min_price: query.min_price !== undefined && query.min_price !== null && query.min_price !== ''
            ? (typeof query.min_price === 'string' ? parseFloat(query.min_price) : Number(query.min_price))
            : undefined,
          max_price: query.max_price !== undefined && query.max_price !== null && query.max_price !== ''
            ? (typeof query.max_price === 'string' ? parseFloat(query.max_price) : Number(query.max_price))
            : undefined,
          search: query.search !== undefined && query.search !== null
            ? (typeof query.search === 'string' ? query.search.trim() : String(query.search).trim())
            : undefined,
          page: query.page !== undefined && query.page !== null && query.page !== ''
            ? (typeof query.page === 'string' ? parseInt(query.page, 10) : Number(query.page)) || 1
            : 1,
          limit: query.limit !== undefined && query.limit !== null && query.limit !== ''
            ? (typeof query.limit === 'string' ? parseInt(query.limit, 10) : Number(query.limit)) || 50
            : 50,
        }

        // Validate category_id format (UUID)
        if (catalogQuery.category_id !== undefined) {
          const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
          if (!uuidRegex.test(catalogQuery.category_id)) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'category_id must be a valid UUID')
          }
        }

        // Validate search parameter (if provided, must have minLength 1)
        if (catalogQuery.search !== undefined && catalogQuery.search.length === 0) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'search must have at least 1 character')
        }

        // Validate price constraints
        if (catalogQuery.min_price !== undefined && catalogQuery.max_price !== undefined) {
          if (catalogQuery.min_price > catalogQuery.max_price) {
            set.status = 400
            return createErrorResponse(
              'VALIDATION_ERROR',
              'min_price must be less than or equal to max_price'
            )
          }
        }

        // Validate numeric constraints
        if (catalogQuery.min_price !== undefined && (isNaN(catalogQuery.min_price) || catalogQuery.min_price < 0)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'min_price must be a non-negative number')
        }

        if (catalogQuery.max_price !== undefined && (isNaN(catalogQuery.max_price) || catalogQuery.max_price < 0)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'max_price must be a non-negative number')
        }

        if (catalogQuery.page < 1) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'page must be greater than or equal to 1')
        }

        if (catalogQuery.limit < 1 || catalogQuery.limit > 200) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'limit must be between 1 and 200')
        }

        // Call catalog service to get products
        const response = await catalogService.getProducts(catalogQuery)

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
        category_id: t.Optional(t.Any()),
        min_price: t.Optional(t.Any()),
        max_price: t.Optional(t.Any()),
        search: t.Optional(t.Any()),
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
        200: CatalogResponseSchema,
        400: t.Object({
          error: t.Object({
            code: t.Literal('VALIDATION_ERROR'),
            message: t.String(),
            details: t.Optional(t.Object({})),
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
        tags: ['catalog'],
        summary: 'Get paginated catalog of active products',
        description:
          'Returns a paginated list of active products with optional filtering by category, price range, and search query. No authentication required.',
        examples: [
          {
            description: 'Get first page of products',
            value: {
              request: {
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
                    min_price: '9.99',
                    max_price: '14.99',
                    supplier_count: 3,
                  },
                ],
              },
            },
          },
          {
            description: 'Filter by category and price range',
            value: {
              request: {
                query: {
                  category_id: '660e8400-e29b-41d4-a716-446655440000',
                  min_price: 10,
                  max_price: 50,
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
          {
            description: 'Search products by name',
            value: {
              request: {
                query: {
                  search: 'cable',
                  page: 1,
                  limit: 10,
                },
              },
              response: {
                total_count: 5,
                page: 1,
                limit: 10,
                data: [],
              },
            },
          },
        ],
      },
    }
  )

