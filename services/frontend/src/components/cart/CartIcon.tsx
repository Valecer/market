/**
 * CartIcon Component
 *
 * Shopping cart icon with item count badge for header navigation.
 * Uses Tailwind CSS for styling, accessible with aria-label.
 * 
 * i18n: Aria-label is translatable with pluralization support
 */

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCart } from '@/hooks/useCart'

interface CartIconProps {
  className?: string
}

export function CartIcon({ className = '' }: CartIconProps) {
  const { t } = useTranslation()
  const { itemCount } = useCart()

  return (
    <Link
      to="/cart"
      className={`relative p-2 text-slate-600 hover:text-slate-900 transition-colors ${className}`}
      aria-label={t('cart.ariaLabel', { count: itemCount })}
    >
      {/* Cart Icon SVG */}
      <svg
        className="w-6 h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
        />
      </svg>

      {/* Badge - show only when cart has items */}
      {itemCount > 0 && (
        <span
          className="absolute -top-1 -right-1 flex items-center justify-center min-w-[20px] h-5 px-1 text-xs font-bold text-white bg-primary rounded-full"
          aria-hidden="true"
        >
          {itemCount > 99 ? '99+' : itemCount}
        </span>
      )}
    </Link>
  )
}
