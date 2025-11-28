import { Elysia, t } from 'elysia'
import { catalogService } from '../../services/catalog.service'
import { CatalogResponseSchema } from '../../types/catalog.types'
import { createErrorResponse } from '../../types/errors'
import { isValidUUID, parseNum } from '../../utils/error-helpers'

/**
 * Catalog Controller
 * 
 * Handles HTTP requests for public catalog endpoints.
 * No business logic - delegates to CatalogService.
 * 
 * Uses functional plugin pattern for consistency with other controllers.
 * See CLAUDE.md for explanation of Elysia plugin scoping.
 */

// Reusable response schemas
const ErrorSchemas = {
  validation: t.Object({
    error: t.Object({
      code: t.Literal('VALIDATION_ERROR'),
      message: t.String(),
      details: t.Optional(t.Object({})),
    }),
  }),
  internal: t.Object({
    error: t.Object({
      code: t.Literal('INTERNAL_ERROR'),
      message: t.String(),
    }),
  }),
}

export const catalogController = (app: Elysia) =>
  app.group('/api/v1/catalog', (app) =>
    app.get(
      '/',
      async ({ query, set }) => {
        // Transform and normalize query parameters
        const catalogQuery = {
          category_id:
            query.category_id && typeof query.category_id === 'string'
              ? query.category_id
              : undefined,
          min_price: parseNum(query.min_price),
          max_price: parseNum(query.max_price),
          search:
            query.search !== undefined && query.search !== null
              ? (typeof query.search === 'string' ? query.search.trim() : String(query.search).trim())
              : undefined,
          page: parseNum(query.page) || 1,
          limit: parseNum(query.limit) || 50,
        }

        // Validations
        if (catalogQuery.category_id && !isValidUUID(catalogQuery.category_id)) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'category_id must be a valid UUID')
        }

        if (catalogQuery.search !== undefined && catalogQuery.search.length === 0) {
          set.status = 400
          return createErrorResponse('VALIDATION_ERROR', 'search must have at least 1 character')
        }

        if (catalogQuery.min_price !== undefined && catalogQuery.max_price !== undefined) {
          if (catalogQuery.min_price > catalogQuery.max_price) {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'min_price must be less than or equal to max_price')
          }
        }

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

        return catalogService.getProducts(catalogQuery)
      },
      {
        query: t.Object({
          category_id: t.Optional(t.Any()),
          min_price: t.Optional(t.Any()),
          max_price: t.Optional(t.Any()),
          search: t.Optional(t.Any()),
          page: t.Optional(t.Any()),
          limit: t.Optional(t.Any()),
        }),
        error({ code, error, set }) {
          if (code === 'VALIDATION') {
            set.status = 400
            return createErrorResponse('VALIDATION_ERROR', 'Invalid query parameters', { issue: error.message })
          }
        },
        response: { 200: CatalogResponseSchema, 400: ErrorSchemas.validation, 500: ErrorSchemas.internal },
        detail: {
          tags: ['catalog'],
          summary: 'Get paginated catalog of active products',
          description:
            'Returns a paginated list of active products with optional filtering by category, price range, and search query. No authentication required.',
        },
      }
    )
  )
