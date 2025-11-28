/**
 * Cart Type Definitions
 *
 * Type interfaces for shopping cart functionality.
 * KISS: Simple types, no over-engineering.
 */

/**
 * Product reference for cart item (minimal data needed for display)
 */
export interface CartProduct {
  id: string
  name: string
  sku: string
  price: number
  image_url?: string | null
  category?: string | null
}

/**
 * Cart item with quantity
 */
export interface CartItem {
  product: CartProduct
  quantity: number
}

/**
 * Full cart state
 */
export interface Cart {
  items: CartItem[]
  updatedAt: number // timestamp for localStorage sync
}

/**
 * Cart action types for useReducer
 */
export type CartAction =
  | { type: 'ADD_ITEM'; payload: { product: CartProduct; quantity?: number } }
  | { type: 'REMOVE_ITEM'; payload: { productId: string } }
  | { type: 'UPDATE_QUANTITY'; payload: { productId: string; quantity: number } }
  | { type: 'CLEAR_CART' }
  | { type: 'LOAD_CART'; payload: Cart }

/**
 * Cart context value exposed to consumers
 */
export interface CartContextValue {
  cart: Cart
  itemCount: number
  subtotal: number
  addItem: (product: CartProduct, quantity?: number) => void
  removeItem: (productId: string) => void
  updateQuantity: (productId: string, quantity: number) => void
  clearCart: () => void
  getItemQuantity: (productId: string) => number
}

/**
 * Cart totals for checkout summary
 */
export interface CartTotals {
  subtotal: number
  tax: number
  shipping: number
  total: number
}

/**
 * Calculate cart totals with tax rate
 */
export function calculateCartTotals(
  items: CartItem[],
  taxRate: number = 0.08,
  shippingCost: number = 5.99
): CartTotals {
  const subtotal = items.reduce(
    (sum, item) => sum + item.product.price * item.quantity,
    0
  )
  const tax = subtotal * taxRate
  const shipping = subtotal > 0 ? shippingCost : 0
  const total = subtotal + tax + shipping

  return { subtotal, tax, shipping, total }
}

/**
 * Format currency for display
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

