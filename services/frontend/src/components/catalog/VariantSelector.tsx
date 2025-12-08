/**
 * VariantSelector Component
 * 
 * Phase 10: Product Variants
 * 
 * Displays product variant options (like memory, color, battery specs)
 * with visual selectors similar to e-commerce sites (e.g., Onliner.by).
 */

import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import type { ProductVariant } from '@/lib/api-client'

interface VariantSelectorProps {
  /** Available variants for this product */
  variants: ProductVariant[]
  
  /** Schema defining which attributes to display and their possible values */
  variantSchema?: Record<string, string[]>
  
  /** Currently selected variant */
  selectedVariant: ProductVariant | null
  
  /** Callback when user selects a variant */
  onSelectVariant: (variant: ProductVariant) => void
  
  /** Additional CSS classes */
  className?: string
}

/**
 * Human-readable labels for variant attributes
 */
const ATTRIBUTE_LABELS: Record<string, { en: string; ru: string }> = {
  voltage: { en: 'Voltage', ru: 'Напряжение' },
  capacity: { en: 'Capacity', ru: 'Ёмкость' },
  power: { en: 'Power', ru: 'Мощность' },
  storage: { en: 'Storage', ru: 'Память' },
  ram: { en: 'RAM', ru: 'ОЗУ' },
  color: { en: 'Color', ru: 'Цвет' },
  size: { en: 'Size', ru: 'Размер' },
  model: { en: 'Model', ru: 'Модель' },
  year: { en: 'Year', ru: 'Год' },
}

/**
 * Get localized label for an attribute key
 */
function getAttributeLabel(key: string, locale: string): string {
  const labels = ATTRIBUTE_LABELS[key.toLowerCase()]
  if (labels) {
    return locale === 'ru' ? labels.ru : labels.en
  }
  // Capitalize first letter for unknown attributes
  return key.charAt(0).toUpperCase() + key.slice(1)
}

/**
 * Format price for display
 */
function formatPrice(price: string): string {
  const num = parseFloat(price)
  if (isNaN(num)) return price
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(num)
}

/**
 * VariantSelector - displays variant options for product selection
 */
export function VariantSelector({
  variants,
  variantSchema,
  selectedVariant,
  onSelectVariant,
  className,
}: VariantSelectorProps) {
  const { i18n, t } = useTranslation()
  const locale = i18n.language || 'en'

  const handleSelect = useCallback(
    (variant: ProductVariant) => {
      onSelectVariant(variant)
    },
    [onSelectVariant]
  )

  if (variants.length === 0) {
    return null
  }

  // Single variant - no selector needed
  if (variants.length === 1) {
    return null
  }

  // Determine attribute keys to display
  const attributeKeys = variantSchema 
    ? Object.keys(variantSchema)
    : variants.length > 0 
      ? Object.keys(variants[0].variant_attributes) 
      : []

  // If no attribute keys, show simple variant list by variant_key
  if (attributeKeys.length === 0) {
    return (
      <div className={cn('space-y-4', className)}>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            {t('product.selectVariant', 'Select option')}:
          </label>
          <div className="flex flex-wrap gap-2">
            {variants
              .sort((a, b) => a.display_order - b.display_order)
              .map((variant) => {
                const isSelected = selectedVariant?.id === variant.id
                return (
                  <button
                    key={variant.id}
                    type="button"
                    onClick={() => handleSelect(variant)}
                    className={cn(
                      'px-4 py-2 rounded-lg border-2 text-sm font-medium transition-all',
                      'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                      isSelected
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                    )}
                    aria-pressed={isSelected}
                  >
                    <span className="font-semibold">{variant.variant_key}</span>
                    <span className="ml-2 text-slate-500">
                      {formatPrice(variant.min_price)}
                    </span>
                  </button>
                )
              })}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      {attributeKeys.map((attrKey) => {
        // Get unique values for this attribute
        const uniqueValues = variantSchema?.[attrKey] ?? 
          [...new Set(variants.map(v => String(v.variant_attributes[attrKey] ?? '')))].filter(Boolean)

        return (
          <div key={attrKey} className="space-y-2">
            {/* Attribute Label */}
            <label className="block text-sm font-medium text-slate-700">
              {getAttributeLabel(attrKey, locale)}:
            </label>

            {/* Variant Buttons */}
            <div className="flex flex-wrap gap-2">
              {uniqueValues.map((value) => {
                // Find a variant that matches this attribute value
                const matchingVariant = variants.find(
                  v => String(v.variant_attributes[attrKey]) === value
                )
                
                if (!matchingVariant) return null

                // Compare as strings to handle type mismatches
                const isSelected = selectedVariant 
                  ? String(selectedVariant.variant_attributes[attrKey]) === value
                  : false

                return (
                  <button
                    key={`${attrKey}-${value}`}
                    type="button"
                    onClick={() => handleSelect(matchingVariant)}
                    className={cn(
                      'px-4 py-2 rounded-lg border-2 text-sm font-medium transition-all',
                      'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                      isSelected
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                    )}
                    aria-pressed={isSelected}
                    aria-label={`${getAttributeLabel(attrKey, locale)}: ${value}`}
                  >
                    <span className="font-semibold">{value}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}

      {/* Selected Variant Info */}
      {selectedVariant && (
        <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-slate-500">
                {t('product.selectedVariant', 'Selected variant')}:
              </span>
              <span className="ml-2 font-medium text-slate-900">
                {selectedVariant.variant_key}
              </span>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-primary">
                {selectedVariant.min_price === selectedVariant.max_price
                  ? formatPrice(selectedVariant.min_price)
                  : `${formatPrice(selectedVariant.min_price)} - ${formatPrice(selectedVariant.max_price)}`}
              </div>
              {selectedVariant.supplier_count > 0 && (
                <div className="text-xs text-slate-500">
                  {selectedVariant.supplier_count} supplier{selectedVariant.supplier_count !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VariantSelector
