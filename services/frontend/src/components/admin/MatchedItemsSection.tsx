/**
 * MatchedItemsSection Component
 *
 * Displays products with their linked supplier items in collapsible dropdowns.
 * Includes "Unlink" button with confirmation for each supplier item.
 *
 * Used in the procurement matching page to show existing associations.
 * i18n: All text content is translatable
 */

import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { AlertDialog, Button, Flex } from '@radix-ui/themes'
import type { AdminProduct, SupplierItem } from '@/lib/api-client'

// =============================================================================
// Icons
// =============================================================================

const UnlinkIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
  </svg>
)

const ProductIcon = () => (
  <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
  </svg>
)

const SupplierIcon = () => (
  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
  </svg>
)

const ChevronIcon = ({ isOpen }: { isOpen: boolean }) => (
  <svg 
    className={`w-5 h-5 text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} 
    fill="none" 
    stroke="currentColor" 
    viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface MatchedItemsSectionProps {
  /** Products with their linked supplier items */
  products: AdminProduct[]
  /** Loading state */
  isLoading?: boolean
  /** Callback when unlink is clicked */
  onUnlink?: (productId: string, supplierItemId: string) => void
  /** Whether an unlink operation is in progress */
  isUnlinking?: boolean
}

interface UnlinkConfirmState {
  open: boolean
  productId: string
  productName: string
  supplierItemId: string
  supplierItemName: string
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Format currency display
 */
function formatCurrency(value: string | number): string {
  const numValue = typeof value === 'string' ? parseFloat(value) : value
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(numValue)
}

/**
 * Format date for display
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

/**
 * Get status badge styling
 */
function getStatusBadge(status: AdminProduct['status'], t: (key: string) => string): { text: string; className: string } {
  switch (status) {
    case 'active':
      return { 
        text: t('admin.sales.active'), 
        className: 'bg-emerald-50 text-emerald-700 border-emerald-200' 
      }
    case 'draft':
      return { 
        text: t('admin.sales.draft'), 
        className: 'bg-slate-50 text-slate-600 border-slate-200' 
      }
    case 'archived':
      return { 
        text: t('admin.sales.archived'), 
        className: 'bg-slate-50 text-slate-400 border-slate-200' 
      }
    default:
      return { 
        text: status, 
        className: 'bg-slate-50 text-slate-500 border-slate-200' 
      }
  }
}

// =============================================================================
// Component
// =============================================================================

export function MatchedItemsSection({
  products,
  isLoading = false,
  onUnlink,
  isUnlinking = false,
}: MatchedItemsSectionProps) {
  const { t } = useTranslation()
  const [confirmState, setConfirmState] = useState<UnlinkConfirmState>({
    open: false,
    productId: '',
    productName: '',
    supplierItemId: '',
    supplierItemName: '',
  })
  
  // Track which products are expanded (default: all collapsed)
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(new Set())

  const toggleProduct = useCallback((productId: string) => {
    setExpandedProducts((prev) => {
      const next = new Set(prev)
      if (next.has(productId)) {
        next.delete(productId)
      } else {
        next.add(productId)
      }
      return next
    })
  }, [])

  const handleUnlinkClick = useCallback((
    productId: string,
    productName: string,
    supplierItem: SupplierItem
  ) => {
    setConfirmState({
      open: true,
      productId,
      productName,
      supplierItemId: supplierItem.id,
      supplierItemName: `${supplierItem.supplier_name} - ${supplierItem.supplier_sku}`,
    })
  }, [])

  const handleConfirmUnlink = useCallback(() => {
    onUnlink?.(confirmState.productId, confirmState.supplierItemId)
    setConfirmState((prev) => ({ ...prev, open: false }))
  }, [confirmState.productId, confirmState.supplierItemId, onUnlink])

  // Filter to only show products with supplier items
  const productsWithItems = products.filter(
    (product) => product.supplier_items && product.supplier_items.length > 0
  )

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-border">
          <div className="h-5 w-32 bg-slate-200 rounded animate-pulse" />
        </div>
        <div className="p-4 space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="border border-border rounded-lg p-4 animate-pulse">
              <div className="h-5 w-48 bg-slate-200 rounded mb-3" />
              <div className="space-y-2">
                <div className="h-4 w-64 bg-slate-100 rounded" />
                <div className="h-4 w-48 bg-slate-100 rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Empty state
  if (productsWithItems.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-border p-8 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-50 mb-4">
          <ProductIcon />
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-1">{t('admin.procurementPage.noMatchedItems')}</h3>
        <p className="text-slate-500">{t('admin.procurementPage.noMatchedItemsDesc')}</p>
      </div>
    )
  }

  return (
    <>
      <div className="bg-white rounded-lg border border-border overflow-hidden shadow-sm">
        <div className="px-4 py-3 bg-slate-50 border-b border-border">
          <h3 className="text-sm font-semibold text-slate-700">
            {t('admin.procurementPage.matchedProducts')}
            <span className="ml-2 text-xs font-normal text-slate-500">
              ({t('admin.procurementPage.itemCount', { count: productsWithItems.length })})
            </span>
          </h3>
        </div>
        <div className="divide-y divide-border">
          {productsWithItems.map((product) => {
            const statusBadge = getStatusBadge(product.status, t)
            const isExpanded = expandedProducts.has(product.id)
            const itemCount = product.supplier_items?.length ?? 0
            
            return (
              <div key={product.id}>
                {/* Product Header - Clickable to toggle */}
                <button
                  type="button"
                  onClick={() => toggleProduct(product.id)}
                  className="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-50 transition-colors text-left focus:outline-none focus:bg-slate-50"
                  aria-expanded={isExpanded}
                  aria-controls={`supplier-items-${product.id}`}
                >
                  <div className="shrink-0">
                    <ProductIcon />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-900">{product.name}</span>
                      <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium border ${statusBadge.className}`}>
                        {statusBadge.text}
                      </span>
                      <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                        {t('admin.procurementPage.itemCount', { count: itemCount })}
                      </span>
                    </div>
                    <span className="text-sm text-slate-500 font-mono block mt-0.5">
                      {product.internal_sku}
                    </span>
                  </div>
                  <ChevronIcon isOpen={isExpanded} />
                </button>

                {/* Supplier Items - Collapsible */}
                <div
                  id={`supplier-items-${product.id}`}
                  className={`transition-all duration-200 ease-in-out ${
                    isExpanded 
                      ? 'max-h-[400px] opacity-100 overflow-y-auto' 
                      : 'max-h-0 opacity-0 overflow-hidden'
                  }`}
                >
                  <div className="px-4 pb-4 pt-1 ml-8 space-y-2">
                    {product.supplier_items?.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <SupplierIcon />
                          <div className="min-w-0">
                            <span className="text-sm font-medium text-slate-700 block truncate">
                              {item.supplier_name}
                            </span>
                            <span className="text-xs text-slate-500 font-mono block truncate">
                              {item.supplier_sku}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <span className="text-sm font-medium text-slate-900 block">
                              {formatCurrency(item.current_price)}
                            </span>
                            <span className="text-xs text-slate-400 block">
                              {formatDate(item.last_ingested_at)}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleUnlinkClick(product.id, product.name, item)
                            }}
                            disabled={isUnlinking}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-red-500/50"
                            aria-label={t('admin.procurementPage.unlinkAriaLabel', { supplier: item.supplier_name, product: product.name })}
                          >
                            <UnlinkIcon />
                            {t('admin.procurementPage.unlink')}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Confirmation Dialog */}
      <AlertDialog.Root open={confirmState.open} onOpenChange={(open) => setConfirmState((prev) => ({ ...prev, open }))}>
        <AlertDialog.Content maxWidth="450px">
          <AlertDialog.Title>{t('admin.procurementPage.unlinkTitle')}</AlertDialog.Title>
          <AlertDialog.Description size="2">
            {t('admin.procurementPage.unlinkDescription', { 
              supplier: confirmState.supplierItemName, 
              product: confirmState.productName 
            })}
          </AlertDialog.Description>

          <Flex gap="3" mt="4" justify="end">
            <AlertDialog.Cancel>
              <Button variant="soft" color="gray" disabled={isUnlinking}>
                {t('common.cancel')}
              </Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <Button 
                variant="solid" 
                color="red" 
                onClick={handleConfirmUnlink}
                disabled={isUnlinking}
              >
                {isUnlinking ? t('admin.procurementPage.unlinking') : t('admin.procurementPage.unlink')}
              </Button>
            </AlertDialog.Action>
          </Flex>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </>
  )
}
