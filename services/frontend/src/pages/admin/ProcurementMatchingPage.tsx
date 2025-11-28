/**
 * ProcurementMatchingPage
 *
 * Page for procurement team members to link supplier items to internal products.
 * Displays unmatched supplier items and allows linking them to products.
 *
 * Features:
 * - View unmatched supplier items in a sortable table
 * - Search and select products to link via modal
 * - View and manage existing product-supplier associations
 * - Optimistic updates for instant feedback
 * - Toast notifications for success/error messages
 */

import { useState, useCallback } from 'react'
import { useUnmatchedItems, type UnmatchedSupplierItem } from '@/hooks/useUnmatchedItems'
import { useMatchSupplier } from '@/hooks/useMatchSupplier'
import { useAdminProducts } from '@/hooks/useAdminProducts'
import { useToast } from '@/components/shared/Toast'
import { UnmatchedItemsTable } from '@/components/admin/UnmatchedItemsTable'
import { ProductSearchModal } from '@/components/admin/ProductSearchModal'
import { MatchedItemsSection } from '@/components/admin/MatchedItemsSection'
import type { ProductSearchResult } from '@/hooks/useProductSearch'

// =============================================================================
// Component
// =============================================================================

export function ProcurementMatchingPage() {
  const toast = useToast()

  // State for modal - supports single item or array of items
  const [modalState, setModalState] = useState<{
    open: boolean
    supplierItems: UnmatchedSupplierItem[]
  }>({
    open: false,
    supplierItems: [],
  })

  // Fetch unmatched items
  const {
    data: unmatchedData,
    isLoading: isLoadingUnmatched,
    error: unmatchedError,
  } = useUnmatchedItems()

  // Fetch admin products (for matched items section)
  const {
    data: productsData,
    isLoading: isLoadingProducts,
  } = useAdminProducts()

  // Match/unmatch mutation
  const matchMutation = useMatchSupplier({
    onSuccess: (data, variables) => {
      if (variables.action === 'link') {
        toast.success(`Successfully linked supplier item to ${data.product.name}`)
      } else {
        toast.success('Supplier item unlinked successfully')
      }
      // Close modal only if it's the last item being linked
      // For multi-item linking, we close after all are processed in handleSelectProduct
    },
    onError: (error) => {
      toast.error(error.message || 'An error occurred')
    },
  })

  // Handle "Link to Product" click (single item)
  const handleLinkClick = useCallback((item: UnmatchedSupplierItem) => {
    setModalState({ open: true, supplierItems: [item] })
  }, [])

  // Handle "Link Selected" click (multiple items)
  const handleLinkSelectedClick = useCallback((items: UnmatchedSupplierItem[]) => {
    setModalState({ open: true, supplierItems: items })
  }, [])

  // Handle product selection in modal - supports multiple items
  const handleSelectProduct = useCallback(async (
    product: ProductSearchResult,
    supplierItems: UnmatchedSupplierItem[]
  ) => {
    const itemCount = supplierItems.length
    
    // Link all items sequentially
    for (let i = 0; i < supplierItems.length; i++) {
      const item = supplierItems[i]
      try {
        await matchMutation.mutateAsync({
          productId: product.id,
          supplierItemId: item.id,
          action: 'link',
        })
      } catch {
        // Error is already handled by onError callback
        // Stop processing if one fails
        break
      }
    }
    
    // Close modal and show success message
    setModalState({ open: false, supplierItems: [] })
    if (itemCount > 1) {
      toast.success(`Successfully linked ${itemCount} items to ${product.name}`)
    }
  }, [matchMutation, toast])

  // Handle unlink
  const handleUnlink = useCallback((productId: string, supplierItemId: string) => {
    matchMutation.mutate({
      productId,
      supplierItemId,
      action: 'unlink',
    })
  }, [matchMutation])

  // Handle modal close
  const handleModalOpenChange = useCallback((open: boolean) => {
    if (!open) {
      setModalState({ open: false, supplierItems: [] })
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Procurement Matching</h1>
        <p className="mt-1 text-sm text-slate-500">
          Link supplier items to internal products to track pricing and inventory.
        </p>
      </div>

      {/* Error State */}
      {unmatchedError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="text-sm font-medium text-red-800">Error loading data</h3>
              <p className="text-sm text-red-600 mt-1">
                {unmatchedError instanceof Error ? unmatchedError.message : 'Failed to load unmatched items'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500">Unmatched Items</p>
              <p className="text-2xl font-semibold text-slate-900">
                {isLoadingUnmatched ? '—' : unmatchedData?.total_count || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500">Products with Links</p>
              <p className="text-2xl font-semibold text-slate-900">
                {isLoadingProducts 
                  ? '—' 
                  : productsData?.data?.filter(p => p.supplier_items?.length > 0).length || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500">Total Associations</p>
              <p className="text-2xl font-semibold text-slate-900">
                {isLoadingProducts 
                  ? '—' 
                  : productsData?.data?.reduce((acc, p) => acc + (p.supplier_items?.length || 0), 0) || 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Unmatched Items Table */}
      <UnmatchedItemsTable
        items={unmatchedData?.data || []}
        isLoading={isLoadingUnmatched}
        onLinkClick={handleLinkClick}
        onLinkSelectedClick={handleLinkSelectedClick}
      />

      {/* Matched Items Section */}
      <MatchedItemsSection
        products={productsData?.data || []}
        isLoading={isLoadingProducts}
        onUnlink={handleUnlink}
        isUnlinking={matchMutation.isPending}
      />

      {/* Product Search Modal */}
      <ProductSearchModal
        open={modalState.open}
        onOpenChange={handleModalOpenChange}
        supplierItems={modalState.supplierItems}
        onSelectProduct={handleSelectProduct}
        isMatching={matchMutation.isPending}
      />
    </div>
  )
}

