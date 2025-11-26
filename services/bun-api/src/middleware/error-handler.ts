import { Elysia } from 'elysia'
import { createErrorResponse, ErrorCode } from '../types/errors'

/**
 * Global error handler middleware
 * 
 * Catches all errors and formats them into consistent error responses
 * following the standard error response format.
 */

export const errorHandler = new Elysia({ name: 'error-handler' })
  .onError(({ code, error, set }) => {
    // Log error for debugging
    console.error('Error caught by error handler:', {
      code,
      error: error.message,
      stack: error.stack,
    })

    // Handle validation errors (from TypeBox/Elysia)
    if (code === 'VALIDATION') {
      set.status = 400
      return createErrorResponse(
        'VALIDATION_ERROR',
        'Invalid request parameters',
        {
          issue: error.message,
        }
      )
    }

    // Handle not found errors
    if (code === 'NOT_FOUND') {
      set.status = 404
      return createErrorResponse('NOT_FOUND', error.message || 'Resource not found')
    }

    // Handle unauthorized errors
    if (code === 'UNAUTHORIZED' || error.message.includes('Unauthorized')) {
      set.status = 401
      return createErrorResponse('UNAUTHORIZED', error.message || 'Unauthorized')
    }

    // Handle forbidden errors
    if (code === 'FORBIDDEN' || error.message.includes('Forbidden')) {
      set.status = 403
      return createErrorResponse('FORBIDDEN', error.message || 'Forbidden')
    }

    // Handle conflict errors
    if (code === 'CONFLICT' || error.message.includes('Conflict')) {
      set.status = 409
      return createErrorResponse('CONFLICT', error.message || 'Conflict')
    }

    // Handle rate limit errors
    if (code === 'RATE_LIMIT' || error.message.includes('Rate limit')) {
      set.status = 429
      return createErrorResponse('RATE_LIMIT_EXCEEDED', error.message || 'Rate limit exceeded')
    }

    // Handle Redis unavailable errors
    if (error.message.includes('Redis') || error.message.includes('redis')) {
      set.status = 503
      return createErrorResponse('REDIS_UNAVAILABLE', 'Redis service unavailable')
    }

    // Default to 500 for unknown errors
    set.status = 500
    return createErrorResponse(
      'INTERNAL_ERROR',
      process.env.NODE_ENV === 'production'
        ? 'Internal server error'
        : error.message || 'An unexpected error occurred'
    )
  })

