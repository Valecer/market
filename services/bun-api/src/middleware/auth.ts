import { Elysia } from 'elysia'
import type { JWTPayload } from '../types/auth.types'

/**
 * JWT Authentication Middleware
 * 
 * Verifies JWT tokens from Authorization header and extracts user information
 * into the context for use in route handlers.
 * 
 * Uses functional plugin pattern to ensure JWT plugin from parent app is accessible.
 * See CLAUDE.md for explanation of Elysia plugin scoping.
 */
export const authMiddleware = (app: Elysia) =>
  app.derive(async ({ jwt, headers }) => {
    // Elysia normalizes headers to lowercase
    const authHeader = headers.authorization || headers['authorization']

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return {
        user: null as JWTPayload | null,
      }
    }

    const token = authHeader.substring(7) // Remove 'Bearer ' prefix

    try {
      // Check if JWT plugin is available and has verify method
      if (!jwt || typeof jwt.verify !== 'function') {
        return {
          user: null as JWTPayload | null,
        }
      }

      // Attempt to verify the token
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
      // Don't log in production to avoid leaking token info
      return {
        user: null as JWTPayload | null,
      }
    }
  })

/**
 * Guard that requires authentication
 * 
 * Use this in routes that require a valid JWT token.
 * Uses functional plugin pattern for consistency.
 */
export const requireAuth = (app: Elysia) =>
  app
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

