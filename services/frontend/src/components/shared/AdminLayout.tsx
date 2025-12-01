/**
 * AdminLayout Component
 *
 * Layout wrapper for admin pages (sales, procurement).
 * Includes collapsible sidebar with role-based navigation.
 *
 * Design System: Radix UI + Tailwind CSS
 * Inspired by: 21st.dev Dashboard with Collapsible Sidebar
 * Accessibility: Semantic HTML, keyboard navigation, ARIA labels
 * i18n: All text content is translatable
 */

import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/hooks/useAuth'
import { LanguageSwitcher } from './LanguageSwitcher'

// Icons (inline SVGs to avoid additional dependencies)
const icons = {
  dashboard: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  ),
  sales: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  procurement: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
    </svg>
  ),
  ingestion: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  ),
  products: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
  ),
  chevronRight: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  ),
  logout: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  ),
  catalog: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  ),
}

interface NavItemConfig {
  nameKey: string
  href: string
  icon: React.ReactNode
  roles: ('admin' | 'sales' | 'procurement')[]
}

const navItemsConfig: NavItemConfig[] = [
  {
    nameKey: 'admin.dashboard',
    href: '/admin',
    icon: icons.dashboard,
    roles: ['admin', 'sales', 'procurement'],
  },
  {
    nameKey: 'admin.salesCatalog',
    href: '/admin/sales',
    icon: icons.sales,
    roles: ['admin', 'sales'],
  },
  {
    nameKey: 'admin.procurement',
    href: '/admin/procurement',
    icon: icons.procurement,
    roles: ['admin', 'procurement'],
  },
  {
    nameKey: 'admin.ingestion',
    href: '/admin/ingestion',
    icon: icons.ingestion,
    roles: ['admin'],
  },
]

export function AdminLayout() {
  const { t } = useTranslation()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const isActive = (path: string) => {
    if (path === '/admin') {
      return location.pathname === '/admin'
    }
    return location.pathname.startsWith(path)
  }

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  // Filter nav items by user role
  const filteredNavItems = navItemsConfig.filter(
    (item) => user?.role && item.roles.includes(user.role)
  )

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col bg-slate-900 text-white transition-all duration-300 ease-in-out ${
          sidebarOpen ? 'w-64' : 'w-20'
        }`}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-700">
          <Link
            to="/admin"
            className="flex items-center gap-3 text-white hover:text-white/90 transition-colors"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
              <svg
                className="w-6 h-6"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12 2L2 7V17L12 22L22 17V7L12 2Z"
                  className="stroke-white"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            {sidebarOpen && (
              <span className="font-bold text-lg">Marketbel</span>
            )}
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {filteredNavItems.map((item) => {
            const name = t(item.nameKey)
            return (
            <Link
                key={item.nameKey}
              to={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                isActive(item.href)
                  ? 'bg-primary text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
                title={!sidebarOpen ? name : undefined}
            >
              {item.icon}
              {sidebarOpen && (
                  <span className="font-medium">{name}</span>
              )}
            </Link>
            )
          })}

          {/* Separator */}
          <div className="my-4 border-t border-slate-700" />

          {/* Back to Catalog */}
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            title={!sidebarOpen ? t('admin.viewCatalog') : undefined}
          >
            {icons.catalog}
            {sidebarOpen && <span className="font-medium">{t('admin.viewCatalog')}</span>}
          </Link>
        </nav>

        {/* User Info */}
        <div className="p-4 border-t border-slate-700">
          {sidebarOpen && user && (
            <div className="mb-3 px-3">
              <p className="text-sm font-medium text-white truncate">
                {user.username}
              </p>
              <p className="text-xs text-slate-400 capitalize">{user.role}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
            title={!sidebarOpen ? t('header.logout') : undefined}
          >
            {icons.logout}
            {sidebarOpen && <span className="font-medium">{t('header.logout')}</span>}
          </button>
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full bg-slate-700 text-slate-300 hover:bg-slate-600 hover:text-white transition-colors shadow-md"
          aria-label={sidebarOpen ? t('admin.collapseSidebar') : t('admin.expandSidebar')}
        >
          <div
            className={`transition-transform duration-300 ${
              sidebarOpen ? 'rotate-180' : ''
            }`}
          >
            {icons.chevronRight}
          </div>
        </button>
      </aside>

      {/* Main Content */}
      <div
        className={`flex-1 transition-all duration-300 ${
          sidebarOpen ? 'ml-64' : 'ml-20'
        }`}
      >
        {/* Top Bar */}
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between bg-white border-b border-border px-6 shadow-sm">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">
              {t('admin.dashboard')}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <span className="text-sm text-slate-500">
              {t('admin.welcome', { name: user?.username })}
            </span>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
