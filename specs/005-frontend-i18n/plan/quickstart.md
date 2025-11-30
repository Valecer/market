# Quickstart: Frontend Internationalization (i18n)

**Time to Complete:** ~20 minutes

**Prerequisites:**
- Frontend service running (`services/frontend`)
- Bun installed

---

## Step 1: Install Dependencies (2 min)

```bash
cd services/frontend

bun add i18next react-i18next i18next-http-backend i18next-browser-languagedetector
```

**Packages:**
- `i18next` - Core i18n framework
- `react-i18next` - React integration (hooks, provider)
- `i18next-http-backend` - Load translations from `/public/locales/`
- `i18next-browser-languagedetector` - Auto-detect browser language

---

## Step 2: Create i18n Configuration (3 min)

Create `src/i18n.ts`:

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import Backend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';

i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ['en', 'ru'],
    
    debug: import.meta.env.DEV,
    
    interpolation: {
      escapeValue: false, // React already escapes
    },
    
    detection: {
      order: ['localStorage', 'cookie', 'navigator'],
      caches: ['localStorage', 'cookie'],
      lookupLocalStorage: 'i18nextLng',
      lookupCookie: 'i18nextLng',
    },
    
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
    
    react: {
      useSuspense: true,
    },
  });

export default i18n;
```

---

## Step 3: Initialize i18n in App Entry (1 min)

Update `src/main.tsx`:

```typescript
import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/api-client';
import App from './App';
import './i18n'; // Add this import
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading...</div>}>
        <App />
      </Suspense>
    </QueryClientProvider>
  </React.StrictMode>
);
```

---

## Step 4: Create Translation Files (5 min)

Create directory structure:

```bash
mkdir -p public/locales/en public/locales/ru
```

Create `public/locales/en/translation.json`:

```json
{
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "retry": "Try Again",
    "clear": "Clear"
  },
  "header": {
    "catalog": "Catalog",
    "cart": "Cart",
    "admin": "Admin",
    "login": "Login",
    "logout": "Logout",
    "languageSelect": "Select language"
  },
  "footer": {
    "copyright": "© {{year}} Marketbel. All rights reserved.",
    "privacy": "Privacy",
    "terms": "Terms",
    "contact": "Contact"
  },
  "catalog": {
    "title": "Product Catalog",
    "subtitle": "Browse our selection of products from multiple suppliers",
    "searchPlaceholder": "Search products by name or SKU...",
    "allCategories": "All Categories",
    "updating": "Updating..."
  },
  "product": {
    "addToCart": "Add"
  }
}
```

Create `public/locales/ru/translation.json`:

```json
{
  "common": {
    "loading": "Загрузка...",
    "error": "Ошибка",
    "retry": "Повторить",
    "clear": "Очистить"
  },
  "header": {
    "catalog": "Каталог",
    "cart": "Корзина",
    "admin": "Админ",
    "login": "Войти",
    "logout": "Выйти",
    "languageSelect": "Выбор языка"
  },
  "footer": {
    "copyright": "© {{year}} Marketbel. Все права защищены.",
    "privacy": "Конфиденциальность",
    "terms": "Условия",
    "contact": "Контакты"
  },
  "catalog": {
    "title": "Каталог товаров",
    "subtitle": "Просмотрите наш ассортимент товаров от различных поставщиков",
    "searchPlaceholder": "Поиск товаров по названию или артикулу...",
    "allCategories": "Все категории",
    "updating": "Обновление..."
  },
  "product": {
    "addToCart": "Добавить"
  }
}
```

---

## Step 5: Create LanguageSwitcher Component (5 min)

Create `src/components/shared/LanguageSwitcher.tsx`:

```tsx
/**
 * LanguageSwitcher Component
 *
 * Toggle between English and Russian languages.
 * Uses i18next for language management.
 *
 * Accessibility: Keyboard navigable, aria-pressed state
 */

import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'ru', label: 'RU', name: 'Русский' },
] as const;

interface LanguageSwitcherProps {
  className?: string;
}

export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation();
  const currentLang = i18n.language?.split('-')[0] || 'en';

  return (
    <div
      role="group"
      aria-label={t('header.languageSelect')}
      className={cn('flex items-center gap-1', className)}
    >
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          onClick={() => i18n.changeLanguage(lang.code)}
          aria-pressed={currentLang === lang.code}
          aria-label={lang.name}
          className={cn(
            'px-2 py-1 text-sm font-medium rounded transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
            currentLang === lang.code
              ? 'bg-primary text-white'
              : 'text-slate-600 hover:bg-slate-100'
          )}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
}
```

Export from index:

```typescript
// src/components/shared/index.ts
export { LanguageSwitcher } from './LanguageSwitcher';
```

---

## Step 6: Add LanguageSwitcher to Header (2 min)

Update `src/components/shared/PublicLayout.tsx`:

```tsx
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from './LanguageSwitcher';

export function PublicLayout() {
  const { t } = useTranslation();
  // ... existing code

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <header className="sticky top-0 z-40 bg-white border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link to="/" className="...">
              <span>Marketbel</span>
            </Link>

            {/* Navigation - Update with translations */}
            <nav className="hidden md:flex items-center gap-6">
              <Link to="/">{t('header.catalog')}</Link>
              <Link to="/cart">{t('header.cart')}</Link>
            </nav>

            {/* Right side - Add LanguageSwitcher */}
            <div className="flex items-center gap-4">
              <LanguageSwitcher />
              <CartIcon />
              {/* ... auth buttons */}
            </div>
          </div>
        </div>
      </header>
      {/* ... rest of component */}
    </div>
  );
}
```

---

## Step 7: Verify Setup (2 min)

1. Start the dev server:
   ```bash
   bun run dev
   ```

2. Open browser at `http://localhost:5173`

3. Verify:
   - [ ] Header shows "Catalog" / "Cart" in English
   - [ ] Language switcher appears in header
   - [ ] Click "RU" → text changes to Russian
   - [ ] Refresh page → language preference persists
   - [ ] Clear localStorage → language auto-detects from browser

---

## Troubleshooting

### Translations not loading?

1. Check browser Network tab for `/locales/en/translation.json`
2. Verify JSON file is valid (no trailing commas)
3. Check console for i18next debug messages

### Language not persisting?

1. Check localStorage for `i18nextLng` key
2. Verify detection order includes `localStorage`

### Flash of untranslated content?

1. Ensure `<Suspense>` wraps the app
2. Check `useSuspense: true` in config

---

## Next Steps

After basic setup is verified:

1. Add remaining translations to JSON files (see `data-model.md`)
2. Update remaining components with `useTranslation` hook
3. Test Russian text layout (may need CSS adjustments)

---

## Reference Files

- Full translation schemas: `specs/005-frontend-i18n/plan/data-model.md`
- Technology decisions: `specs/005-frontend-i18n/plan/research.md`
- Implementation plan: `specs/005-frontend-i18n/plan.md`

