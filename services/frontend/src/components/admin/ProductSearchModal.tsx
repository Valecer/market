/**
 * ProductSearchModal Component
 *
 * Modal dialog for searching and selecting products to link supplier items to.
 * Features debounced search with fuzzy matching results.
 * Supports creating new products when no suitable match exists.
 *
 * Uses Radix UI Dialog for accessible modal behavior.
 * i18n: All text content is translatable
 */

import { useState, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog, Flex, Text, TextField, Button } from '@radix-ui/themes'
import { useProductSearch, type ProductSearchResult } from '@/hooks/useProductSearch'
import { useCreateProduct, type CreateProductResponse } from '@/hooks/useCreateProduct'
import type { UnmatchedSupplierItem } from '@/hooks/useUnmatchedItems'

// =============================================================================
// Icons
// =============================================================================

const SearchIcon = () => (
  <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
)

const LoadingIcon = () => (
  <svg className="w-4 h-4 text-slate-400 animate-spin" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

const ProductIcon = () => (
  <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
  </svg>
)

const PlusIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
)

// =============================================================================
// Types
// =============================================================================

interface ProductSearchModalProps {
  /** Whether the modal is open */
  open: boolean
  /** Callback when modal should close */
  onOpenChange: (open: boolean) => void
  /** The supplier item(s) being linked - supports single item or array */
  supplierItems: UnmatchedSupplierItem | UnmatchedSupplierItem[] | null
  /** Callback when a product is selected for linking */
  onSelectProduct: (product: ProductSearchResult, supplierItems: UnmatchedSupplierItem[]) => void
  /** Callback when a new product is created (used for single item only) */
  onProductCreated?: (product: CreateProductResponse) => void
  /** Whether a match operation is in progress */
  isMatching?: boolean
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Get status badge styling
 */
function getStatusBadge(status: ProductSearchResult['status'], t: (key: string) => string): { text: string; className: string } {
  switch (status) {
    case 'active':
      return { 
        text: t('admin.sales.active'), 
        className: 'bg-emerald-50 text-emerald-700' 
      }
    case 'draft':
      return { 
        text: t('admin.sales.draft'), 
        className: 'bg-slate-100 text-slate-600' 
      }
    case 'archived':
      return { 
        text: t('admin.sales.archived'), 
        className: 'bg-slate-100 text-slate-400' 
      }
    default:
      return { 
        text: status, 
        className: 'bg-slate-100 text-slate-500' 
      }
  }
}

// =============================================================================
// Component
// =============================================================================

export function ProductSearchModal({
  open,
  onOpenChange,
  supplierItems,
  onSelectProduct,
  onProductCreated,
  isMatching = false,
}: ProductSearchModalProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [newProductName, setNewProductName] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const { data: products, isSearching, searchQuery: debouncedQuery } = useProductSearch(searchQuery)

  // Create product hook
  const { createProduct, isCreating } = useCreateProduct({
    onSuccess: (product) => {
      onProductCreated?.(product)
      handleOpenChange(false)
    },
  })

  // Normalize to array for consistent handling
  const itemsArray = useMemo(() => {
    if (!supplierItems) return []
    return Array.isArray(supplierItems) ? supplierItems : [supplierItems]
  }, [supplierItems])

  const isMultiple = itemsArray.length > 1

  // Only allow creating new product for single item
  const canCreateProduct = itemsArray.length === 1

  const handleSelectProduct = useCallback((product: ProductSearchResult) => {
    if (itemsArray.length > 0 && !isMatching) {
      onSelectProduct(product, itemsArray)
    }
  }, [itemsArray, onSelectProduct, isMatching])

  // Handle creating a new product with the supplier item linked
  const handleCreateProduct = useCallback(async () => {
    if (!canCreateProduct || !newProductName.trim()) return

    const item = itemsArray[0]
    await createProduct({
      name: newProductName.trim(),
      supplier_item_id: item.id,
      status: 'draft',
    })
  }, [canCreateProduct, newProductName, itemsArray, createProduct])

  // Show create form with pre-filled name from supplier item
  const handleShowCreateForm = useCallback(() => {
    if (itemsArray.length === 1) {
      setNewProductName(itemsArray[0].name)
    }
    setShowCreateForm(true)
  }, [itemsArray])

  // Reset state when modal closes
  const handleOpenChange = useCallback((newOpen: boolean) => {
    if (!newOpen) {
      setSearchQuery('')
      setNewProductName('')
      setShowCreateForm(false)
    }
    onOpenChange(newOpen)
  }, [onOpenChange])

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content maxWidth="600px" aria-describedby={undefined}>
        <Dialog.Title>
          {isMultiple 
            ? t('admin.procurementPage.linkMultipleTitle', { count: itemsArray.length }) 
            : t('admin.procurementPage.linkToProductTitle')}
        </Dialog.Title>
        
        {itemsArray.length > 0 && (
          <div className="mt-2 mb-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
            <Text size="1" className="text-slate-500 block mb-1">
              {isMultiple 
                ? t('admin.procurementPage.linkingItemsMultiple', { count: itemsArray.length })
                : t('admin.procurementPage.linkingItems')}
            </Text>
            {isMultiple ? (
              <div className="max-h-32 overflow-y-auto mt-2 space-y-2">
                {itemsArray.map((item) => (
                  <div key={item.id} className="flex items-center gap-2 text-sm">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                    <span className="font-medium text-slate-900 truncate">{item.name}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500 text-xs font-mono truncate">{item.supplier_sku}</span>
                  </div>
                ))}
              </div>
            ) : (
              <>
                <Text weight="medium" className="text-slate-900 block">{itemsArray[0]?.name}</Text>
                <Text size="1" className="text-slate-500">
                  {itemsArray[0]?.supplier_name} • {itemsArray[0]?.supplier_sku}
                </Text>
              </>
            )}
          </div>
        )}

        {/* Search Input - hidden when create form is showing */}
        {!showCreateForm && (
          <div className="relative mb-4">
            <div className="absolute left-3 top-1/2 -translate-y-1/2">
              {isSearching ? <LoadingIcon /> : <SearchIcon />}
            </div>
            <TextField.Root
              size="2"
              placeholder={t('admin.procurementPage.searchProductsPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
              autoFocus
            />
          </div>
        )}

        {/* Results - hidden when create form is showing */}
        <div className="max-h-80 overflow-y-auto rounded-lg border border-border">
          {/* Initial state */}
          {!showCreateForm && !debouncedQuery && (
            <div className="p-8 text-center text-slate-500">
              <SearchIcon />
              <Text size="2" className="mt-2 block">
                {t('admin.procurementPage.typeToSearch')}
              </Text>
              {canCreateProduct && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <Text size="2" className="text-slate-600 block mb-3">
                    {t('admin.procurementPage.orCreateNew')}
                  </Text>
                  <Button
                    type="button"
                    variant="soft"
                    onClick={handleShowCreateForm}
                    className="inline-flex items-center gap-2"
                  >
                    <PlusIcon />
                    {t('admin.procurementPage.createNewProduct')}
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Loading */}
          {!showCreateForm && isSearching && (
            <div className="p-8 text-center text-slate-500">
              <LoadingIcon />
              <Text size="2" className="mt-2 block">
                {t('common.searching')}
              </Text>
            </div>
          )}

          {/* No results - with option to create new product */}
          {debouncedQuery && !isSearching && products && products.length === 0 && !showCreateForm && (
            <div className="p-6 text-center">
              <Text size="2" className="text-slate-500 block mb-4">
                {t('admin.procurementPage.noProductsForQuery', { query: debouncedQuery })}
              </Text>
              {canCreateProduct && (
                <div className="mt-4 pt-4 border-t border-slate-100">
                  <Text size="2" className="text-slate-600 block mb-3">
                    {t('admin.procurementPage.createNewProductHint')}
                  </Text>
                  <Button
                    type="button"
                    variant="soft"
                    onClick={handleShowCreateForm}
                    className="inline-flex items-center gap-2"
                  >
                    <PlusIcon />
                    {t('admin.procurementPage.createNewProduct')}
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Create new product form */}
          {showCreateForm && canCreateProduct && (
            <div className="p-4">
              <div className="mb-4">
                <Text size="2" weight="medium" className="text-slate-700 block mb-2">
                  {t('admin.procurementPage.createNewProductTitle')}
                </Text>
                <Text size="1" className="text-slate-500 block mb-3">
                  {t('admin.procurementPage.createNewProductDescription')}
                </Text>
              </div>
              <div className="space-y-3">
                <div>
                  <Text as="label" size="1" weight="medium" className="text-slate-600 block mb-1">
                    {t('admin.procurementPage.productName')}
                  </Text>
                  <TextField.Root
                    size="2"
                    placeholder={t('admin.procurementPage.productNamePlaceholder')}
                    value={newProductName}
                    onChange={(e) => setNewProductName(e.target.value)}
                    autoFocus
                  />
                </div>
                <Flex gap="2" justify="end" className="pt-2">
                  <Button
                    type="button"
                    variant="soft"
                    color="gray"
                    onClick={() => setShowCreateForm(false)}
                    disabled={isCreating}
                  >
                    {t('common.back')}
                  </Button>
                  <Button
                    type="button"
                    variant="solid"
                    onClick={handleCreateProduct}
                    disabled={isCreating || !newProductName.trim()}
                  >
                    {isCreating ? t('common.saving') : t('admin.procurementPage.createAndLink')}
                  </Button>
                </Flex>
              </div>
            </div>
          )}

          {/* Results list */}
          {!showCreateForm && !isSearching && products && products.length > 0 && (
            <ul className="divide-y divide-border" role="listbox">
              {products.map((product) => {
                const statusBadge = getStatusBadge(product.status, t)
                return (
                  <li key={product.id}>
                    <button
                      type="button"
                      onClick={() => handleSelectProduct(product)}
                      disabled={isMatching}
                      className="w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:bg-slate-50"
                      role="option"
                      aria-selected="false"
                    >
                      <div className="flex items-start gap-3">
                        <div className="shrink-0 mt-0.5">
                          <ProductIcon />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <Text weight="medium" className="text-slate-900 truncate">
                              {product.name}
                            </Text>
                            <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${statusBadge.className}`}>
                              {statusBadge.text}
                            </span>
                          </div>
                          <Text size="1" className="text-slate-500 mt-0.5 block font-mono">
                            {product.internal_sku}
                          </Text>
                          <Text size="1" className="text-slate-400 mt-1 block">
                            {t('product.suppliersLinked', { count: product.supplier_count })}
                          </Text>
                        </div>
                        <div className="shrink-0">
                          <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Actions - only show cancel when not in create form (create form has its own buttons) */}
        {!showCreateForm && (
          <Flex gap="3" mt="4" justify="end">
            <Dialog.Close>
              <Button variant="soft" color="gray" disabled={isMatching || isCreating}>
                {t('common.cancel')}
              </Button>
            </Dialog.Close>
          </Flex>
        )}
      </Dialog.Content>
    </Dialog.Root>
  )
}
