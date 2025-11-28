/**
 * CartItemRow Component
 *
 * Single cart item display with image, details, quantity controls, and remove button.
 * Used in CartPage for displaying cart contents.
 */

import { useCart } from '@/hooks/useCart'
import type { CartItem } from '@/types/cart'
import { formatCurrency } from '@/types/cart'

interface CartItemRowProps {
  item: CartItem
}

export function CartItemRow({ item }: CartItemRowProps) {
  const { updateQuantity, removeItem } = useCart()
  const { product, quantity } = item
  const itemTotal = product.price * quantity

  const handleIncrement = () => {
    updateQuantity(product.id, quantity + 1)
  }

  const handleDecrement = () => {
    if (quantity > 1) {
      updateQuantity(product.id, quantity - 1)
    }
  }

  const handleRemove = () => {
    removeItem(product.id)
  }

  const handleQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newQuantity = parseInt(e.target.value, 10)
    if (!isNaN(newQuantity) && newQuantity >= 1) {
      updateQuantity(product.id, newQuantity)
    }
  }

  return (
    <div className="flex items-center gap-4 p-4 bg-white rounded-lg border border-border shadow-sm">
      {/* Product Image */}
      <div className="flex-shrink-0 w-20 h-20 bg-slate-100 rounded-lg overflow-hidden">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-400">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}
      </div>

      {/* Product Details */}
      <div className="flex-1 min-w-0">
        <h3 className="font-medium text-slate-900 truncate">{product.name}</h3>
        <p className="text-sm text-muted">SKU: {product.sku}</p>
        {product.category && (
          <p className="text-sm text-muted">{product.category}</p>
        )}
        <p className="text-sm font-medium text-slate-600 mt-1">
          {formatCurrency(product.price)} each
        </p>
      </div>

      {/* Quantity Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleDecrement}
          disabled={quantity <= 1}
          className="w-8 h-8 flex items-center justify-center rounded-md border border-border text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          aria-label="Decrease quantity"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
        
        <input
          type="number"
          min="1"
          value={quantity}
          onChange={handleQuantityChange}
          className="w-14 h-8 text-center text-sm border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
          aria-label="Quantity"
        />
        
        <button
          onClick={handleIncrement}
          className="w-8 h-8 flex items-center justify-center rounded-md border border-border text-slate-600 hover:bg-slate-50 transition-colors"
          aria-label="Increase quantity"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* Item Total & Remove */}
      <div className="flex flex-col items-end gap-2">
        <p className="font-semibold text-lg text-slate-900">
          {formatCurrency(itemTotal)}
        </p>
        <button
          onClick={handleRemove}
          className="text-sm text-danger hover:text-danger/80 transition-colors flex items-center gap-1"
          aria-label={`Remove ${product.name} from cart`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          Remove
        </button>
      </div>
    </div>
  )
}

