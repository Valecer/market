/**
 * Authentication Context
 *
 * Provides authentication state management for the application.
 * Handles login, logout, and JWT token persistence.
 *
 * KISS: Simple Context + reducer pattern, no complex state management.
 * Strong Typing: Full TypeScript with proper type definitions.
 */

import {
  createContext,
  useReducer,
  useEffect,
  useCallback,
  useState,
  type ReactNode,
} from 'react'
import { apiClient, type User } from '@/lib/api-client'
import type { AuthState, AuthAction, AuthContextValue } from '@/types/auth'

// =============================================================================
// Initial State
// =============================================================================

const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
}

// =============================================================================
// Reducer
// =============================================================================

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'LOGIN':
      return {
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
      }
    case 'LOGOUT':
      return {
        user: null,
        token: null,
        isAuthenticated: false,
      }
    default:
      return state
  }
}

// =============================================================================
// Context
// =============================================================================

export const AuthContext = createContext<AuthContextValue | null>(null)

// =============================================================================
// Provider
// =============================================================================

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, initialState)
  const [isLoading, setIsLoading] = useState(true)

  // Load auth state from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem('jwt_token')
    const userJson = localStorage.getItem('user')

    if (token && userJson) {
      try {
        const user = JSON.parse(userJson) as User
        dispatch({ type: 'LOGIN', payload: { user, token } })
      } catch {
        // Invalid user data, clear storage
        localStorage.removeItem('jwt_token')
        localStorage.removeItem('user')
      }
    }
    
    // Done checking localStorage
    setIsLoading(false)
  }, [])

  // Login function
  const login = useCallback(async (username: string, password: string) => {
    const { data, error } = await apiClient.POST('/api/v1/auth/login', {
      body: { username, password },
    })

    if (error) {
      throw new Error(
        'error' in error && typeof error.error === 'object' && error.error !== null
          ? (error.error as { message?: string }).message || 'Login failed'
          : 'Login failed'
      )
    }

    if (!data) {
      throw new Error('No data returned from login')
    }

    // Persist to localStorage
    localStorage.setItem('jwt_token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))

    // Update state
    dispatch({
      type: 'LOGIN',
      payload: { user: data.user, token: data.token },
    })
  }, [])

  // Logout function
  const logout = useCallback(() => {
    // Clear localStorage
    localStorage.removeItem('jwt_token')
    localStorage.removeItem('user')

    // Update state
    dispatch({ type: 'LOGOUT' })
  }, [])

  const value: AuthContextValue = {
    state,
    login,
    logout,
    isAuthenticated: state.isAuthenticated,
    isLoading,
    user: state.user,
    userRole: state.user?.role ?? null,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

