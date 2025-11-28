/**
 * Shared Components
 *
 * Re-exports all shared UI components for convenient imports.
 * Usage: import { Button, Input, Select } from '@/components/shared'
 */

export { AdminLayout } from './AdminLayout'
export { Button, type ButtonProps, type ButtonVariant, type ButtonSize } from './Button'
export { ErrorBoundary, type ErrorBoundaryProps, type FallbackProps } from './ErrorBoundary'
export { ErrorState } from './ErrorState'
export { Input, type InputProps } from './Input'
export { LoadingSkeleton } from './LoadingSkeleton'
export { ProtectedRoute } from './ProtectedRoute'
export { PublicLayout } from './PublicLayout'
export { Select, type SelectProps, type SelectOption } from './Select'
export { ToastProvider, useToast, type ToastType } from './Toast'

