# Research: Frontend Internationalization (i18n)

**Date:** 2025-11-30

**Status:** Complete

---

## Overview

This document captures research findings for implementing internationalization in the Marketbel React frontend using react-i18next ecosystem.

---

## Technology Stack Decisions

### Primary Library: react-i18next

**Decision:** Use `react-i18next` as the React integration layer.

**Rationale:**
- Industry standard for React i18n (268 code snippets in documentation)
- High source reputation and active maintenance
- Native React hooks (`useTranslation`)
- Built-in Suspense support for async loading states
- Seamless integration with i18next ecosystem plugins

**Alternatives Considered:**

| Library | Pros | Cons | Decision |
|---------|------|------|----------|
| `react-i18next` | Mature, hooks API, Suspense support | Requires multiple packages | ✅ Selected |
| `react-intl` | ICU message format, good pluralization | Heavier bundle, different API style | ❌ Rejected |
| `next-intl` | Great for Next.js | Overkill for Vite/React | ❌ Not applicable |
| `lingui` | Message extraction, smaller runtime | Less ecosystem support | ❌ Rejected |

---

### Translation Loading: i18next-http-backend

**Decision:** Use `i18next-http-backend` to load translations from `/public/locales/`.

**Rationale:**
- Translations loaded on-demand (better initial bundle size)
- Simple JSON file management
- Easy to update translations without code changes
- Supports multiple namespaces for code splitting
- Compatible with Vite dev server

**Configuration:**
```javascript
backend: {
  loadPath: '/locales/{{lng}}/{{ns}}.json'
}
```

**Alternatives Considered:**

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| HTTP Backend | Lazy loading, easy updates | Extra network request | ✅ Selected |
| Bundled resources | Faster initial load | Larger bundle, requires rebuild | ❌ Rejected |
| Dynamic import | Code splitting | More complex setup | ❌ Over-engineering |

---

### Language Detection: i18next-browser-languagedetector

**Decision:** Use `i18next-browser-languagedetector` with detection order: `localStorage → cookie → navigator`.

**Rationale:**
- Automatic browser language detection via `navigator.language`
- Configurable detection order (stored preference takes precedence)
- Built-in caching to localStorage/cookies
- No custom code needed for persistence

**Configuration:**
```javascript
detection: {
  order: ['localStorage', 'cookie', 'navigator'],
  caches: ['localStorage', 'cookie'],
  cookieExpirationDate: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000), // 1 year
  lookupLocalStorage: 'i18nextLng',
  lookupCookie: 'i18nextLng'
}
```

**Detection Flow:**
1. Check localStorage for saved preference → if found, use it
2. Check cookie for saved preference → if found, use it
3. Check navigator.language/languages → if `ru` or `en`, use it
4. Fallback to English (`en`)

---

### Namespace Strategy

**Decision:** Use single `translation` namespace for MVP, organized by key prefixes.

**Rationale:**
- Simpler configuration and fewer HTTP requests
- All translations load in one request (acceptable for 2 languages)
- Namespace splitting deferred until translation files grow large
- Follows KISS principle

**Key Organization:**
```json
{
  "common.loading": "Loading...",
  "common.error": "Something went wrong",
  "header.catalog": "Catalog",
  "header.cart": "Cart",
  "catalog.title": "Product Catalog",
  "catalog.searchPlaceholder": "Search products..."
}
```

**Future Evolution:**
- When translation files exceed ~200 keys, split into namespaces (`common`, `catalog`, `admin`)
- Add lazy loading per namespace

---

### Suspense vs Non-Suspense Loading

**Decision:** Use `useSuspense: true` with React Suspense boundary.

**Rationale:**
- Cleaner component code (no loading state checks)
- Prevents flash of untranslated content
- Native React pattern for async data
- App-level Suspense boundary handles all translation loading

**Implementation:**
```jsx
// App.tsx
<Suspense fallback={<LoadingSpinner />}>
  <RouterProvider router={router} />
</Suspense>
```

---

### TypeScript Integration

**Decision:** Start without strict typing for translation keys (KISS). Add types as iteration 2.

**Rationale:**
- Strict typing requires additional tooling (i18next-parser, custom types)
- MVP has limited number of keys (~50-100), easy to manually verify
- Missing key warnings in development mode sufficient for now

**Future Evolution:**
- Use `i18next-cli` to generate TypeScript definitions from JSON files
- Add eslint-plugin-i18next to catch hardcoded strings

---

## Component Integration Patterns

### Pattern 1: Component with useTranslation Hook

```tsx
import { useTranslation } from 'react-i18next';

export function Header() {
  const { t } = useTranslation();
  
  return (
    <nav>
      <Link to="/">{t('header.catalog')}</Link>
      <Link to="/cart">{t('header.cart')}</Link>
    </nav>
  );
}
```

### Pattern 2: Language Switcher

```tsx
import { useTranslation } from 'react-i18next';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  
  const languages = [
    { code: 'en', label: 'EN', name: 'English' },
    { code: 'ru', label: 'RU', name: 'Русский' }
  ];
  
  return (
    <div role="group" aria-label={t('header.languageSelect')}>
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => i18n.changeLanguage(lang.code)}
          aria-pressed={i18n.language === lang.code}
          aria-label={lang.name}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
}
```

### Pattern 3: Interpolation for Dynamic Values

```tsx
// Translation: "Showing {{start}}-{{end}} of {{total}} products"
<p>{t('catalog.paginationInfo', { start: 1, end: 12, total: 156 })}</p>

// Translation: "{{count}} supplier" / "{{count}} suppliers"
<span>{t('product.supplierCount', { count: supplier_count })}</span>
```

---

## Translation File Organization

### Directory Structure

```
public/
└── locales/
    ├── en/
    │   └── translation.json
    └── ru/
        └── translation.json
```

### Key Naming Convention

**Format:** `{namespace}.{component}.{element}`

| Key | Description |
|-----|-------------|
| `common.*` | Shared UI elements (buttons, loading, errors) |
| `header.*` | Header navigation, user menu |
| `footer.*` | Footer links, copyright |
| `catalog.*` | Catalog page specific text |
| `cart.*` | Cart page and cart icon |
| `product.*` | Product card and detail |
| `auth.*` | Login/logout UI |

---

## Accessibility Considerations

### HTML `lang` Attribute

The `i18next-browser-languagedetector` automatically updates `document.documentElement.lang` when language changes, ensuring screen readers announce correct language.

### Language Switcher Accessibility

- Use `role="group"` with descriptive `aria-label`
- Each option has `aria-pressed` to indicate current selection
- Keyboard navigable (Tab + Enter/Space)
- Visible focus indicators (existing Tailwind focus styles)

### Translation Considerations

- Keep translated strings contextually meaningful
- Use proper punctuation for Russian text
- Ensure translated text doesn't break layouts (Russian is typically 15-20% longer)

---

## Performance Considerations

### Initial Load

1. i18next initializes synchronously with language detection
2. HTTP backend starts loading translations
3. React Suspense boundary shows fallback
4. When translations load, app renders

**Expected Impact:** ~50-100ms additional load time (acceptable)

### Language Switch

1. User clicks language option
2. `i18n.changeLanguage()` called
3. HTTP backend loads new language file (if not cached)
4. React re-renders with new translations

**Expected Impact:** <100ms for cached, ~100-200ms for uncached

### Bundle Size Impact

| Package | Size (gzipped) |
|---------|---------------|
| `i18next` | ~8.5 KB |
| `react-i18next` | ~3.5 KB |
| `i18next-http-backend` | ~2 KB |
| `i18next-browser-languagedetector` | ~2 KB |
| **Total** | **~16 KB** |

---

## Testing Strategy

### Unit Tests

- Test translation key existence
- Test interpolation with different values
- Test pluralization rules

### Integration Tests

- Test language detection on first visit
- Test manual language switch
- Test persistence across page reload

### E2E Tests (Manual Verification)

- Verify all visible text changes on language switch
- Verify no mixed-language content
- Verify Russian text doesn't overflow UI elements

---

## Migration Path

### Phase 1: Infrastructure (This Feature)
- Install packages
- Configure i18n
- Create translation files
- Add LanguageSwitcher to Header

### Phase 2: Shell Components
- Translate Header navigation
- Translate Footer content
- Translate error/loading states

### Phase 3: Catalog Page
- Translate FilterBar
- Translate ProductCard
- Translate ProductGrid
- Translate pagination

### Future Phases (Out of Scope)
- Admin panel translation
- Date/number formatting
- Pluralization for complex cases

---

## References

- [react-i18next Documentation](https://react.i18next.com/)
- [i18next Documentation](https://www.i18next.com/)
- [i18next-browser-languagedetector](https://github.com/i18next/i18next-browser-languagedetector)
- [i18next-http-backend](https://github.com/i18next/i18next-http-backend)

