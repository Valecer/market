/**
 * CartSummary Component
 *
 * Order summary with subtotal, tax, shipping, and total calculations.
 * Includes proceed to checkout button.
 * 
 * i18n: All text content is translatable
 */

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCart } from '@/hooks/useCart'
import { calculateCartTotals, formatCurrency } from '@/types/cart'

interface CartSummaryProps {
  showCheckoutButton?: boolean
}

export function CartSummary({ showCheckoutButton = true }: CartSummaryProps) {
  const { t } = useTranslation()
  const { cart, itemCount } = useCart()
  const { subtotal, tax, shipping, total } = calculateCartTotals(cart.items)

  const isEmpty = cart.items.length === 0

  return (
    <div className="bg-white rounded-lg border border-border shadow-sm p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">
        {t('cart.orderSummary')}
      </h2>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-600">
            {t('cart.subtotal')} ({t('cart.itemCount', { count: itemCount })})
          </span>
          <span className="font-medium text-slate-900">
            {formatCurrency(subtotal)}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-slate-600">{t('cart.shipping')}</span>
          <span className="font-medium text-slate-900">
            {shipping > 0 ? formatCurrency(shipping) : t('common.free')}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-slate-600">{t('cart.tax')}</span>
          <span className="font-medium text-slate-900">
            {formatCurrency(tax)}
          </span>
        </div>

        <hr className="border-border my-3" />

        <div className="flex justify-between text-base font-semibold">
          <span className="text-slate-900">{t('cart.total')}</span>
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
            {t('cart.checkout')}
          </Link>

          <Link
            to="/"
            className="block w-full py-3 px-4 text-center font-medium text-slate-600 border border-border rounded-lg hover:bg-slate-50 transition-colors"
          >
            {t('cart.continueShopping')}
          </Link>
        </div>
      )}
    </div>
  )
}
