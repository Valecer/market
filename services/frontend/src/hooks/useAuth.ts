/**
 * useAuth Hook
 *
 * Provides access to authentication state and actions.
 * Must be used within an AuthProvider.
 */

import { useContext } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import type { AuthContextValue } from '@/types/auth'

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}

