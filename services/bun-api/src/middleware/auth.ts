import { Elysia } from 'elysia'
import type { JWTPayload } from '../types/auth.types'

/**
 * JWT Authentication Middleware
 * 
 * Verifies JWT tokens from Authorization header and extracts user information
 * into the context for use in route handlers.
 */

export const authMiddleware = new Elysia({ name: 'auth' })
  .derive(async ({ jwt, headers }) => {
    const authHeader = headers.authorization

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return {
        user: null as JWTPayload | null,
      }
    }

    const token = authHeader.substring(7) // Remove 'Bearer ' prefix

    try {
      const payload = await jwt.verify(token)

      if (!payload) {
        return {
          user: null as JWTPayload | null,
        }
      }

      // Verify payload structure matches JWTPayload
      if (
        typeof payload.sub === 'string' &&
        typeof payload.role === 'string' &&
        typeof payload.exp === 'number' &&
        typeof payload.iss === 'string'
      ) {
        return {
          user: payload as JWTPayload,
        }
      }

      return {
        user: null as JWTPayload | null,
      }
    } catch (error) {
      // Token verification failed (expired, invalid signature, etc.)
      return {
        user: null as JWTPayload | null,
      }
    }
  })

/**
 * Guard that requires authentication
 * 
 * Use this in routes that require a valid JWT token
 */
export const requireAuth = new Elysia({ name: 'require-auth' })
  .derive(({ user }) => {
    // Just pass user through - we'll check in beforeHandle
    return { user }
  })
  .onBeforeHandle(({ user, set, error }) => {
    if (!user) {
      return error(401, {
        error: {
          code: 'UNAUTHORIZED',
          message: 'Unauthorized',
        },
      })
    }
  })

