/**
 * Authentication Types
 *
 * Frontend-only types for authentication state management.
 * User type is imported from API types (auto-generated).
 */

import type { User, UserRole } from '@/lib/api-client'

export interface AuthState {
  /** Current authenticated user (null if not logged in) */
  user: User | null
  /** JWT token */
  token: string | null
  /** Convenience flag */
  isAuthenticated: boolean
}

export type AuthAction =
  | { type: 'LOGIN'; payload: { user: User; token: string } }
  | { type: 'LOGOUT' }

export interface AuthContextValue {
  state: AuthState
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  user: User | null
  userRole: UserRole | null
}

export interface LoginCredentials {
  username: string
  password: string
}

