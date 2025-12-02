/**
 * PublicLayout Component
 *
 * Layout wrapper for public-facing pages (catalog, product detail, cart).
 * Includes header with navigation, language switcher, and cart icon.
 *
 * Design System: Radix UI + Tailwind CSS
 * Accessibility: Semantic HTML, proper navigation structure
 * i18n: All text content is translatable
 */

import { Link, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/hooks/useAuth'
import { CartIcon } from '@/components/cart'
import { LanguageSwitcher } from './LanguageSwitcher'

export function PublicLayout() {
  const { t } = useTranslation()
  const { isAuthenticated, user, logout } = useAuth()
  const location = useLocation()

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link
              to="/"
              className="flex items-center gap-2 text-xl font-bold text-primary hover:text-primary/90 transition-colors"
            >
              <svg
                className="w-8 h-8"
                viewBox="0 0 32 32"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <rect
                  width="32"
                  height="32"
                  rx="8"
                  className="fill-primary"
                />
                <path
                  d="M8 12L16 8L24 12V20L16 24L8 20V12Z"
                  className="stroke-white"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                <path
                  d="M16 8V24M8 12L24 20M24 12L8 20"
                  className="stroke-white/50"
                  strokeWidth="1.5"
                />
              </svg>
              <span>Marketbel</span>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-6">
              <Link
                to="/"
                className={`text-sm font-medium transition-colors ${
                  isActive('/')
                    ? 'text-primary'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {t('header.catalog')}
              </Link>
              <Link
                to="/cart"
                className={`text-sm font-medium transition-colors ${
                  isActive('/cart')
                    ? 'text-primary'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {t('header.cart')}
              </Link>
            </nav>

            {/* Right side - Language Switcher, Auth & Cart */}
            <div className="flex items-center gap-4">
              {/* Language Switcher */}
              <LanguageSwitcher className="hidden sm:flex" />

              {/* Cart Icon with badge */}
              <CartIcon />

              {/* Auth */}
              {isAuthenticated ? (
                <div className="flex items-center gap-3">
                  <span className="hidden sm:inline text-sm text-slate-600">
                    {user?.username}
                  </span>
                  {(user?.role === 'admin' ||
                    user?.role === 'sales' ||
                    user?.role === 'procurement') && (
                    <Link
                      to="/admin"
                      className="text-sm font-medium text-slate-600 hover:text-primary transition-colors"
                    >
                      {t('header.admin')}
                    </Link>
                  )}
                  <button
                    onClick={logout}
                    className="text-sm font-medium text-slate-600 hover:text-danger transition-colors"
                  >
                    {t('header.logout')}
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary/90 transition-colors"
                >
                  {t('header.login')}
                </Link>
              )}

              {/* Mobile menu button */}
              <button
                className="md:hidden p-2 text-slate-600 hover:text-slate-900"
                aria-label={t('header.openMenu')}
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-border py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted">
              {t('footer.copyright', { year: new Date().getFullYear() })}
            </p>
            <div className="flex items-center gap-4">
              {/* Mobile Language Switcher (shown only on small screens) */}
              <LanguageSwitcher className="sm:hidden" />
            <nav className="flex gap-6">
              <a
                href="#"
                className="text-sm text-muted hover:text-slate-900 transition-colors"
              >
                  {t('footer.privacy')}
              </a>
              <a
                href="#"
                className="text-sm text-muted hover:text-slate-900 transition-colors"
              >
                  {t('footer.terms')}
              </a>
              <a
                href="#"
                className="text-sm text-muted hover:text-slate-900 transition-colors"
              >
                  {t('footer.contact')}
              </a>
            </nav>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
