/**
 * Cart Context
 *
 * Provides shopping cart state management with localStorage persistence.
 * KISS: useReducer for state, localStorage for persistence.
 * Strong Typing: Full TypeScript with CartAction discriminated unions.
 */

import {
  createContext,
  useReducer,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'
import type {
  Cart,
  CartAction,
  CartContextValue,
  CartItem,
  CartProduct,
} from '@/types/cart'

// =============================================================================
// Constants
// =============================================================================

const CART_STORAGE_KEY = 'marketbel_cart'

const initialCart: Cart = {
  items: [],
  updatedAt: Date.now(),
}

// =============================================================================
// Reducer
// =============================================================================

function cartReducer(state: Cart, action: CartAction): Cart {
  switch (action.type) {
    case 'ADD_ITEM': {
      const { product, quantity = 1 } = action.payload
      const existingIndex = state.items.findIndex(
        (item) => item.product.id === product.id
      )

      let newItems: CartItem[]
      if (existingIndex >= 0) {
        // Update existing item quantity
        newItems = state.items.map((item, index) =>
          index === existingIndex
            ? { ...item, quantity: item.quantity + quantity }
            : item
        )
      } else {
        // Add new item
        newItems = [...state.items, { product, quantity }]
      }

      return {
        items: newItems,
        updatedAt: Date.now(),
      }
    }

    case 'REMOVE_ITEM': {
      const { productId } = action.payload
      return {
        items: state.items.filter((item) => item.product.id !== productId),
        updatedAt: Date.now(),
      }
    }

    case 'UPDATE_QUANTITY': {
      const { productId, quantity } = action.payload
      
      // Remove item if quantity is 0 or less
      if (quantity <= 0) {
        return {
          items: state.items.filter((item) => item.product.id !== productId),
          updatedAt: Date.now(),
        }
      }

      return {
        items: state.items.map((item) =>
          item.product.id === productId ? { ...item, quantity } : item
        ),
        updatedAt: Date.now(),
      }
    }

    case 'CLEAR_CART':
      return {
        items: [],
        updatedAt: Date.now(),
      }

    case 'LOAD_CART':
      return action.payload

    default:
      return state
  }
}

// =============================================================================
// Context
// =============================================================================

export const CartContext = createContext<CartContextValue | null>(null)

// =============================================================================
// Provider
// =============================================================================

interface CartProviderProps {
  children: ReactNode
}

export function CartProvider({ children }: CartProviderProps) {
  const [cart, dispatch] = useReducer(cartReducer, initialCart)

  // ==========================================================================
  // localStorage Persistence - Load on mount
  // ==========================================================================
  useEffect(() => {
    try {
      const stored = localStorage.getItem(CART_STORAGE_KEY)
      if (stored) {
        const parsedCart = JSON.parse(stored) as Cart
        // Validate parsed data has expected structure
        if (parsedCart && Array.isArray(parsedCart.items)) {
          dispatch({ type: 'LOAD_CART', payload: parsedCart })
        }
      }
    } catch {
      // Invalid cart data, keep initial state
      console.warn('Failed to load cart from localStorage')
    }
  }, [])

  // ==========================================================================
  // localStorage Persistence - Save on change
  // ==========================================================================
  useEffect(() => {
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart))
    } catch {
      console.warn('Failed to save cart to localStorage')
    }
  }, [cart])

  // ==========================================================================
  // Actions
  // ==========================================================================

  const addItem = useCallback((product: CartProduct, quantity: number = 1) => {
    dispatch({ type: 'ADD_ITEM', payload: { product, quantity } })
  }, [])

  const removeItem = useCallback((productId: string) => {
    dispatch({ type: 'REMOVE_ITEM', payload: { productId } })
  }, [])

  const updateQuantity = useCallback((productId: string, quantity: number) => {
    dispatch({ type: 'UPDATE_QUANTITY', payload: { productId, quantity } })
  }, [])

  const clearCart = useCallback(() => {
    dispatch({ type: 'CLEAR_CART' })
  }, [])

  const getItemQuantity = useCallback(
    (productId: string): number => {
      const item = cart.items.find((item) => item.product.id === productId)
      return item?.quantity ?? 0
    },
    [cart.items]
  )

  // ==========================================================================
  // Derived State
  // ==========================================================================

  const itemCount = useMemo(
    () => cart.items.reduce((sum, item) => sum + item.quantity, 0),
    [cart.items]
  )

  const subtotal = useMemo(
    () =>
      cart.items.reduce(
        (sum, item) => sum + item.product.price * item.quantity,
        0
      ),
    [cart.items]
  )

  // ==========================================================================
  // Context Value
  // ==========================================================================

  const value: CartContextValue = useMemo(
    () => ({
      cart,
      itemCount,
      subtotal,
      addItem,
      removeItem,
      updateQuantity,
      clearCart,
      getItemQuantity,
    }),
    [
      cart,
      itemCount,
      subtotal,
      addItem,
      removeItem,
      updateQuantity,
      clearCart,
      getItemQuantity,
    ]
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

