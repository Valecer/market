/**
 * CartSummary Component
 *
 * Order summary with subtotal, tax, shipping, and total calculations.
 * Includes proceed to checkout button.
 */

import { Link } from 'react-router-dom'
import { useCart } from '@/hooks/useCart'
import { calculateCartTotals, formatCurrency } from '@/types/cart'

interface CartSummaryProps {
  showCheckoutButton?: boolean
}

export function CartSummary({ showCheckoutButton = true }: CartSummaryProps) {
  const { cart, itemCount } = useCart()
  const { subtotal, tax, shipping, total } = calculateCartTotals(cart.items)

  const isEmpty = cart.items.length === 0

  return (
    <div className="bg-white rounded-lg border border-border shadow-sm p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">
        Order Summary
      </h2>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-600">
            Subtotal ({itemCount} {itemCount === 1 ? 'item' : 'items'})
          </span>
          <span className="font-medium text-slate-900">
            {formatCurrency(subtotal)}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-slate-600">Shipping</span>
          <span className="font-medium text-slate-900">
            {shipping > 0 ? formatCurrency(shipping) : 'Free'}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-slate-600">Tax (8%)</span>
          <span className="font-medium text-slate-900">
            {formatCurrency(tax)}
          </span>
        </div>

        <hr className="border-border my-3" />

        <div className="flex justify-between text-base font-semibold">
          <span className="text-slate-900">Total</span>
          <span className="text-slate-900">{formatCurrency(total)}</span>
        </div>
      </div>

      {showCheckoutButton && (
        <div className="mt-6 space-y-3">
          <Link
            to="/checkout"
            className={`block w-full py-3 px-4 text-center font-medium rounded-lg transition-colors ${
              isEmpty
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-primary text-white hover:bg-primary/90'
            }`}
            onClick={(e) => isEmpty && e.preventDefault()}
            aria-disabled={isEmpty}
          >
            Proceed to Checkout
          </Link>

          <Link
            to="/"
            className="block w-full py-3 px-4 text-center font-medium text-slate-600 border border-border rounded-lg hover:bg-slate-50 transition-colors"
          >
            Continue Shopping
          </Link>
        </div>
      )}
    </div>
  )
}

