import { BrowserRouter, Routes, Route } from 'react-router-dom'

/**
 * Main App Component
 *
 * Sets up routing for the Marketbel frontend application.
 * Routes will be added as features are implemented.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Placeholder route - will be replaced with actual pages */}
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPlaceholder />} />
      </Routes>
    </BrowserRouter>
  )
}

/**
 * Temporary Home Page placeholder
 * Will be replaced with CatalogPage in Phase 3
 */
function HomePage() {
  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-white shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-primary">Marketbel</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <svg
              className="w-8 h-8 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>

          <h2 className="text-xl font-semibold text-slate-900 mb-2">
            Setup Complete!
          </h2>

          <p className="text-slate-500 mb-6">
            Phase 1 initialization successful. The frontend is ready for development.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center max-w-2xl mx-auto">
            <div className="p-4 bg-slate-50 rounded-lg text-left flex-1">
              <h3 className="font-medium text-slate-900 mb-1">✓ Vite + React</h3>
              <p className="text-sm text-slate-500">Build tooling configured</p>
            </div>
            <div className="p-4 bg-slate-50 rounded-lg text-left flex-1">
              <h3 className="font-medium text-slate-900 mb-1">✓ TanStack Query</h3>
              <p className="text-sm text-slate-500">Data fetching ready</p>
            </div>
            <div className="p-4 bg-slate-50 rounded-lg text-left flex-1">
              <h3 className="font-medium text-slate-900 mb-1">✓ Tailwind CSS</h3>
              <p className="text-sm text-slate-500">Styling configured</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

/**
 * Temporary Login placeholder
 * Will be replaced with actual LoginPage in Phase 2
 */
function LoginPlaceholder() {
  const urlParams = new URLSearchParams(window.location.search)
  const expired = urlParams.get('expired') === 'true'

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Login</h1>

        {expired && (
          <div className="mb-4 p-3 bg-warning/10 border border-warning/20 rounded-md">
            <p className="text-sm text-warning">
              Your session has expired. Please login again.
            </p>
          </div>
        )}

        <p className="text-muted mb-4">
          Login functionality will be implemented in Phase 2.
        </p>

        <a
          href="/"
          className="inline-block px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90"
        >
          Back to Home
        </a>
      </div>
    </div>
  )
}

export default App
