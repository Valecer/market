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
 * @param allowedRoles - Array of roles that are allowed to access the route
 * @returns Elysia plugin that enforces role-based access
 */
export function requireRole(allowedRoles: UserRole[]) {
  return new Elysia({ name: 'require-role' })
    .derive(({ user }) => {
      // Just pass user through - we'll check in beforeHandle
      return { user }
    })
    .onBeforeHandle(({ user, error }) => {
      if (!user) {
        return error(401, {
          error: {
            code: 'UNAUTHORIZED',
            message: 'Unauthorized',
          },
        })
      }

      if (!allowedRoles.includes(user.role)) {
        return error(403, {
          error: {
            code: 'FORBIDDEN',
            message: 'Forbidden: Insufficient permissions',
          },
        })
      }
    })
}

/**
 * Convenience guards for common role combinations
 */
export const requireAdmin = requireRole(['admin'])
export const requireProcurement = requireRole(['procurement', 'admin'])
export const requireSales = requireRole(['sales', 'procurement', 'admin'])

