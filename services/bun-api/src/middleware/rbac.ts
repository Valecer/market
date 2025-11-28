import { Elysia } from 'elysia'
import type { UserRole } from '../types/auth.types'

/**
 * Role-Based Access Control (RBAC) Middleware
 * 
 * Checks if the authenticated user has the required role(s) to access a route
 */

/**
 * Creates a guard that requires specific role(s)
 * 
 * Uses functional plugin pattern to ensure user from authMiddleware is accessible.
 * See CLAUDE.md for explanation of Elysia plugin scoping.
 * 
 * @param allowedRoles - Array of roles that are allowed to access the route
 * @returns Elysia plugin function that enforces role-based access
 */
export function requireRole(allowedRoles: UserRole[]) {
  return (app: Elysia) =>
    app
      .derive((context: any) => {
        // Pass user through from authMiddleware context
        // Type assertion needed because TypeScript can't infer user from parent plugin
        const user = context.user
        return { user }
      })
      .onBeforeHandle(({ user, set }) => {
        if (!user) {
          set.status = 401
          return {
            error: {
              code: 'UNAUTHORIZED',
              message: 'Unauthorized',
            },
          }
        }

        if (!allowedRoles.includes(user.role)) {
          set.status = 403
          return {
            error: {
              code: 'FORBIDDEN',
              message: 'Forbidden: Insufficient permissions',
            },
          }
        }
      })
}

/**
 * Convenience guards for common role combinations
 */
export const requireAdmin = requireRole(['admin'])
export const requireProcurement = requireRole(['procurement', 'admin'])
export const requireSales = requireRole(['sales', 'procurement', 'admin'])

