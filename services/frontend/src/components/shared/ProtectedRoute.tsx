/**
 * ProtectedRoute Component
 *
 * Wraps routes that require authentication.
 * Redirects to login page if user is not authenticated.
 * Optionally restricts access based on user role.
 *
 * KISS: Simple redirect logic, no complex auth checks.
 */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { UserRole } from '@/lib/api-client'
import type { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
  /** Required roles to access this route (any match allows access) */
  allowedRoles?: UserRole[]
}

export function ProtectedRoute({
  children,
  allowedRoles,
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, userRole } = useAuth()
  const location = useLocation()

  // Still checking localStorage - show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  // Not authenticated - redirect to login
  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname }}
        replace
      />
    )
  }

  // Role check (if required)
  if (allowedRoles && userRole && !allowedRoles.includes(userRole)) {
    // User doesn't have required role - redirect to unauthorized or home
    return <Navigate to="/unauthorized" replace />
  }

  return <>{children}</>
}

