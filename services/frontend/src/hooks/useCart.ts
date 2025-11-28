/**
 * useCart Hook
 *
 * Custom hook for accessing cart context.
 * Provides type-safe access to cart state and actions.
 */

import { useContext } from 'react'
import { CartContext } from '@/contexts/CartContext'
import type { CartContextValue } from '@/types/cart'

/**
 * Access cart context
 * @throws Error if used outside CartProvider
 */
export function useCart(): CartContextValue {
  const context = useContext(CartContext)

  if (!context) {
    throw new Error('useCart must be used within a CartProvider')
  }

  return context
}

