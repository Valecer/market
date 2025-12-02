/**
 * CartPage
 *
 * Shopping cart page displaying all cart items with quantity controls,
 * empty state, and order summary.
 * 
 * i18n: All text content is translatable
 */

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCart } from '@/hooks/useCart'
import { CartItemRow, CartSummary } from '@/components/cart'

export function CartPage() {
  const { t } = useTranslation()
  const { cart, clearCart, itemCount } = useCart()
  const isEmpty = cart.items.length === 0

  return (
    <div className="min-h-screen bg-surface">
      {/* Page Header */}
      <div className="bg-white border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">
                {t('cart.title')}
              </h1>
              <p className="mt-1 text-slate-500">
                {isEmpty
                  ? t('cart.emptySubtitle')
                  : t('cart.subtitle', { count: itemCount })}
              </p>
            </div>

            {!isEmpty && (
              <button
                onClick={clearCart}
                className="text-sm font-medium text-danger hover:text-danger/80 transition-colors flex items-center gap-1"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
                {t('cart.clearCart')}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isEmpty ? (
          /* Empty Cart State */
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-slate-100 mb-6">
              <svg
                className="w-12 h-12 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-slate-900 mb-2">
              {t('cart.empty.title')}
            </h2>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              {t('cart.empty.message')}
            </p>
            <Link
              to="/"
              className="inline-flex items-center px-6 py-3 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              {t('cart.browseProducts')}
            </Link>
          </div>
        ) : (
          /* Cart with Items */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Cart Items */}
            <div className="lg:col-span-2 space-y-4">
              {cart.items.map((item) => (
                <CartItemRow key={item.product.id} item={item} />
              ))}
            </div>

            {/* Order Summary - Sticky on desktop */}
            <div className="lg:col-span-1">
              <div className="lg:sticky lg:top-24">
                <CartSummary />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
