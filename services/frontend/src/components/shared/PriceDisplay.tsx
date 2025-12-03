/**
 * PriceDisplay Component
 *
 * Phase 9: Advanced Pricing & Categorization
 *
 * Displays formatted price with currency symbol.
 * Supports null values with placeholder.
 * 
 * Design: Clean typography with currency-aware formatting
 * Accessibility: Screen reader friendly price announcements
 */

import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { CURRENCY_CONFIG, type PriceDisplayProps, type DualPricingProps } from '@/types/product'

/**
 * Format price with currency symbol
 */
function formatPriceWithCurrency(
  price: string | number | null | undefined,
  currencyCode?: string | null
): string {
  if (price === null || price === undefined) {
    return ''
  }

  const numericPrice = typeof price === 'string' ? parseFloat(price) : price
  if (isNaN(numericPrice)) {
    return ''
  }

  const formattedPrice = numericPrice.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  if (!currencyCode) {
    return formattedPrice
  }

  const config = CURRENCY_CONFIG[currencyCode]
  if (!config) {
    // Default: show currency code after price
    return `${formattedPrice} ${currencyCode}`
  }

  return config.position === 'before'
    ? `${config.symbol}${formattedPrice}`
    : `${formattedPrice} ${config.symbol}`
}

/**
 * Single price display component
 */
export function PriceDisplay({
  price,
  currencyCode,
  showCurrency = true,
  className,
  size = 'md',
  placeholder,
}: PriceDisplayProps) {
  const { t } = useTranslation()
  
  const defaultPlaceholder = placeholder ?? t('product.pricing.notSet')
  
  // Handle null/undefined prices
  if (price === null || price === undefined) {
    return (
      <span
        className={cn(
          'text-muted tabular-nums',
          size === 'sm' && 'text-sm',
          size === 'md' && 'text-base',
          size === 'lg' && 'text-lg font-semibold',
          className
        )}
        aria-label={t('product.pricing.notSet')}
      >
        {defaultPlaceholder}
      </span>
    )
  }

  const formattedPrice = showCurrency
    ? formatPriceWithCurrency(price, currencyCode)
    : typeof price === 'string'
      ? parseFloat(price).toFixed(2)
      : price.toFixed(2)

  return (
    <span
      className={cn(
        'font-medium tabular-nums text-slate-900',
        size === 'sm' && 'text-sm',
        size === 'md' && 'text-base',
        size === 'lg' && 'text-xl font-bold',
        className
      )}
      aria-label={`${formattedPrice}`}
    >
      {formattedPrice}
    </span>
  )
}

/**
 * Dual pricing display (retail + wholesale)
 */
export function DualPricingDisplay({
  retailPrice,
  wholesalePrice,
  currencyCode,
  showBoth = true,
  className,
}: DualPricingProps) {
  const { t } = useTranslation()

  // Determine primary price (retail preferred, wholesale fallback)
  const primaryPrice = retailPrice ?? wholesalePrice
  const primaryLabel = retailPrice ? t('product.pricing.retail') : t('product.pricing.wholesale')

  if (!showBoth || !wholesalePrice || !retailPrice) {
    // Single price display mode
    return (
      <div className={cn('space-y-1', className)}>
        <PriceDisplay
          price={primaryPrice}
          currencyCode={currencyCode}
          size="lg"
          showCurrency
        />
      </div>
    )
  }

  // Dual price display mode
  return (
    <div className={cn('space-y-2', className)}>
      {/* Retail price (primary) */}
      <div className="flex items-baseline gap-2">
        <span className="text-sm text-muted font-medium">
          {t('product.pricing.retail')}:
        </span>
        <PriceDisplay
          price={retailPrice}
          currencyCode={currencyCode}
          size="lg"
          showCurrency
        />
      </div>

      {/* Wholesale price (secondary) */}
      <div className="flex items-baseline gap-2">
        <span className="text-sm text-muted font-medium">
          {t('product.pricing.wholesale')}:
        </span>
        <PriceDisplay
          price={wholesalePrice}
          currencyCode={currencyCode}
          size="md"
          showCurrency
          className="text-emerald-600"
        />
      </div>
    </div>
  )
}

/**
 * Price badge for compact display
 */
export function PriceBadge({
  price,
  currencyCode,
  className,
}: Pick<PriceDisplayProps, 'price' | 'currencyCode' | 'className'>) {
  const { t } = useTranslation()

  if (price === null || price === undefined) {
    return null
  }

  const formattedPrice = formatPriceWithCurrency(price, currencyCode)

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-1 rounded-md',
        'bg-primary/10 text-primary text-sm font-semibold tabular-nums',
        className
      )}
    >
      {formattedPrice}
    </span>
  )
}

export default PriceDisplay

