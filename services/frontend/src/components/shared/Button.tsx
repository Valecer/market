/**
 * Button Component
 *
 * Reusable button with consistent styling and multiple variants.
 * Follows constitution principles: Single Responsibility, Design System Consistency.
 *
 * Design System: Tailwind CSS + Custom theme variables
 * Accessibility: ARIA labels, focus states, keyboard navigation
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual style variant */
  variant?: ButtonVariant
  /** Button size */
  size?: ButtonSize
  /** Show loading spinner */
  loading?: boolean
  /** Icon to display before label */
  icon?: ReactNode
  /** Icon to display after label */
  iconRight?: ReactNode
  /** Full width button */
  fullWidth?: boolean
  /** Button content */
  children?: ReactNode
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: `
    bg-primary text-white
    hover:bg-primary/90
    active:bg-primary/80
    focus-visible:ring-primary/50
    disabled:bg-primary/50
  `,
  secondary: `
    bg-slate-100 text-slate-900
    hover:bg-slate-200
    active:bg-slate-300
    focus-visible:ring-slate-400
    disabled:bg-slate-100 disabled:text-slate-400
    dark:bg-slate-800 dark:text-slate-100
    dark:hover:bg-slate-700
  `,
  danger: `
    bg-danger text-white
    hover:bg-danger/90
    active:bg-danger/80
    focus-visible:ring-danger/50
    disabled:bg-danger/50
  `,
  ghost: `
    bg-transparent text-slate-700
    hover:bg-slate-100
    active:bg-slate-200
    focus-visible:ring-slate-400
    disabled:text-slate-400 disabled:hover:bg-transparent
    dark:text-slate-300
    dark:hover:bg-slate-800
  `,
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5 rounded-md',
  md: 'h-10 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-lg',
}

/**
 * Button component with multiple variants and sizes.
 *
 * @example
 * // Primary button
 * <Button variant="primary">Save Changes</Button>
 *
 * @example
 * // Danger button with icon
 * <Button variant="danger" icon={<TrashIcon />}>Delete</Button>
 *
 * @example
 * // Ghost button, loading state
 * <Button variant="ghost" loading>Loading...</Button>
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      icon,
      iconRight,
      fullWidth = false,
      disabled,
      children,
      className = '',
      type = 'button',
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        className={`
          inline-flex items-center justify-center
          font-medium
          transition-all duration-200
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
          disabled:cursor-not-allowed disabled:opacity-60
          ${variantStyles[variant]}
          ${sizeStyles[size]}
          ${fullWidth ? 'w-full' : ''}
          ${className}
        `.trim().replace(/\s+/g, ' ')}
        aria-busy={loading}
        aria-disabled={isDisabled}
        {...props}
      >
        {/* Loading spinner */}
        {loading && (
          <svg
            className="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}

        {/* Left icon */}
        {!loading && icon && (
          <span className="inline-flex shrink-0" aria-hidden="true">
            {icon}
          </span>
        )}

        {/* Button label */}
        {children && <span>{children}</span>}

        {/* Right icon */}
        {!loading && iconRight && (
          <span className="inline-flex shrink-0" aria-hidden="true">
            {iconRight}
          </span>
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'

export type { ButtonProps, ButtonVariant, ButtonSize }

