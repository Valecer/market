# Data Model: Frontend Internationalization (i18n)

**Date:** 2025-11-30

**Status:** Complete

---

## Overview

This document defines TypeScript types, translation structures, and component interfaces for the i18n implementation.

---

## TypeScript Types

### i18n Configuration Types

```typescript
// src/types/i18n.ts

/**
 * Supported locale codes
 */
export type Locale = 'en' | 'ru';

/**
 * Language metadata for UI display
 */
export interface Language {
  code: Locale;
  label: string;      // Short display (e.g., "EN", "RU")
  name: string;       // Full name (e.g., "English", "Русский")
  flag?: string;      // Optional emoji flag
}

/**
 * Supported languages configuration
 */
export const SUPPORTED_LANGUAGES: Language[] = [
  { code: 'en', label: 'EN', name: 'English', flag: '🇬🇧' },
  { code: 'ru', label: 'RU', name: 'Русский', flag: '🇷🇺' },
];

/**
 * Default language (fallback)
 */
export const DEFAULT_LANGUAGE: Locale = 'en';

/**
 * i18n configuration constants
 */
export const I18N_CONFIG = {
  defaultLocale: 'en' as Locale,
  fallbackLocale: 'en' as Locale,
  supportedLocales: ['en', 'ru'] as Locale[],
  localStorageKey: 'i18nextLng',
  cookieKey: 'i18nextLng',
  cookieExpiration: 365, // days
} as const;
```

### Component Props Types

```typescript
// src/components/shared/LanguageSwitcher.tsx

import type { Locale, Language } from '@/types/i18n';

/**
 * LanguageSwitcher component props
 */
export interface LanguageSwitcherProps {
  /** Current active language code */
  currentLanguage?: Locale;
  /** Callback when language changes */
  onLanguageChange?: (locale: Locale) => void;
  /** Display variant */
  variant?: 'buttons' | 'dropdown' | 'minimal';
  /** Show full language names or codes only */
  showLabels?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * LanguageSwitcher internal state (when uncontrolled)
 */
interface LanguageSwitcherState {
  isOpen: boolean; // For dropdown variant
}
```

---

## Translation File Structure

### Namespace Organization

Single `translation` namespace with hierarchical key prefixes:

```
translation.json
├── common.*           # Shared UI elements
├── header.*          # Header/navigation
├── footer.*          # Footer content
├── catalog.*         # Catalog page
├── cart.*            # Cart page/icon
├── product.*         # Product cards/detail
├── auth.*            # Authentication
├── error.*           # Error states
└── loading.*         # Loading states
```

### Key Naming Convention

**Pattern:** `{section}.{component?}.{element}`

- Use camelCase for multi-word elements
- Keep keys descriptive but concise
- Group related keys under same prefix

---

## Translation Schemas

### English Translation (`en/translation.json`)

```json
{
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "retry": "Try Again",
    "save": "Save",
    "cancel": "Cancel",
    "submit": "Submit",
    "back": "Back",
    "next": "Next",
    "search": "Search",
    "clear": "Clear",
    "close": "Close",
    "all": "All"
  },
  
  "header": {
    "catalog": "Catalog",
    "cart": "Cart",
    "admin": "Admin",
    "login": "Login",
    "logout": "Logout",
    "languageSelect": "Select language",
    "openMenu": "Open menu"
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
    "minPrice": "Min $",
    "maxPrice": "Max $",
    "clearFilters": "Clear",
    "updating": "Updating...",
    "paginationInfo": "Showing {{start}}-{{end}} of {{total}} products",
    "noResults": {
      "title": "No results found",
      "message": "Try adjusting your filters or search terms."
    },
    "filters": {
      "search": "Search: \"{{query}}\"",
      "category": "Category: {{name}}",
      "minPrice": "Min: ${{price}}",
      "maxPrice": "Max: ${{price}}"
    }
  },
  
  "product": {
    "addToCart": "Add",
    "addToCartFull": "Add to Cart",
    "viewDetails": "View Details",
    "supplierCount": "{{count}} supplier",
    "supplierCount_plural": "{{count}} suppliers",
    "sku": "SKU",
    "price": "Price",
    "priceRange": "{{min}} - {{max}}",
    "outOfStock": "Out of Stock",
    "inStock": "In Stock"
  },
  
  "cart": {
    "title": "Shopping Cart",
    "empty": {
      "title": "Your cart is empty",
      "message": "Browse our catalog to find products."
    },
    "itemCount": "{{count}} item",
    "itemCount_plural": "{{count}} items",
    "ariaLabel": "Shopping cart with {{count}} item",
    "ariaLabel_plural": "Shopping cart with {{count}} items",
    "total": "Total",
    "checkout": "Proceed to Checkout",
    "continueShopping": "Continue Shopping",
    "removeItem": "Remove",
    "quantity": "Quantity"
  },
  
  "auth": {
    "username": "Username",
    "password": "Password",
    "loginButton": "Sign In",
    "loggingIn": "Signing in...",
    "loginError": "Invalid username or password",
    "loginRequired": "Please log in to continue"
  },
  
  "error": {
    "title": "Something went wrong",
    "message": "An unexpected error occurred. Please try again.",
    "notFound": "Page not found",
    "networkError": "Network error. Please check your connection.",
    "serverError": "Server error. Please try again later."
  },
  
  "loading": {
    "products": "Loading products...",
    "product": "Loading product...",
    "cart": "Loading cart...",
    "translations": "Loading...",
    "table": "Loading table data..."
  }
}
```

### Russian Translation (`ru/translation.json`)

```json
{
  "common": {
    "loading": "Загрузка...",
    "error": "Ошибка",
    "retry": "Повторить",
    "save": "Сохранить",
    "cancel": "Отмена",
    "submit": "Отправить",
    "back": "Назад",
    "next": "Далее",
    "search": "Поиск",
    "clear": "Очистить",
    "close": "Закрыть",
    "all": "Все"
  },
  
  "header": {
    "catalog": "Каталог",
    "cart": "Корзина",
    "admin": "Админ",
    "login": "Войти",
    "logout": "Выйти",
    "languageSelect": "Выбор языка",
    "openMenu": "Открыть меню"
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
    "minPrice": "Мин ₽",
    "maxPrice": "Макс ₽",
    "clearFilters": "Сбросить",
    "updating": "Обновление...",
    "paginationInfo": "Показано {{start}}-{{end}} из {{total}} товаров",
    "noResults": {
      "title": "Ничего не найдено",
      "message": "Попробуйте изменить фильтры или поисковый запрос."
    },
    "filters": {
      "search": "Поиск: \"{{query}}\"",
      "category": "Категория: {{name}}",
      "minPrice": "Мин: ₽{{price}}",
      "maxPrice": "Макс: ₽{{price}}"
    }
  },
  
  "product": {
    "addToCart": "Добавить",
    "addToCartFull": "В корзину",
    "viewDetails": "Подробнее",
    "supplierCount_one": "{{count}} поставщик",
    "supplierCount_few": "{{count}} поставщика",
    "supplierCount_many": "{{count}} поставщиков",
    "sku": "Артикул",
    "price": "Цена",
    "priceRange": "{{min}} - {{max}}",
    "outOfStock": "Нет в наличии",
    "inStock": "В наличии"
  },
  
  "cart": {
    "title": "Корзина",
    "empty": {
      "title": "Корзина пуста",
      "message": "Перейдите в каталог, чтобы выбрать товары."
    },
    "itemCount_one": "{{count}} товар",
    "itemCount_few": "{{count}} товара",
    "itemCount_many": "{{count}} товаров",
    "ariaLabel_one": "Корзина с {{count}} товаром",
    "ariaLabel_few": "Корзина с {{count}} товарами",
    "ariaLabel_many": "Корзина с {{count}} товарами",
    "total": "Итого",
    "checkout": "Оформить заказ",
    "continueShopping": "Продолжить покупки",
    "removeItem": "Удалить",
    "quantity": "Количество"
  },
  
  "auth": {
    "username": "Имя пользователя",
    "password": "Пароль",
    "loginButton": "Войти",
    "loggingIn": "Вход...",
    "loginError": "Неверное имя пользователя или пароль",
    "loginRequired": "Пожалуйста, войдите в систему"
  },
  
  "error": {
    "title": "Что-то пошло не так",
    "message": "Произошла непредвиденная ошибка. Попробуйте ещё раз.",
    "notFound": "Страница не найдена",
    "networkError": "Ошибка сети. Проверьте подключение.",
    "serverError": "Ошибка сервера. Попробуйте позже."
  },
  
  "loading": {
    "products": "Загрузка товаров...",
    "product": "Загрузка товара...",
    "cart": "Загрузка корзины...",
    "translations": "Загрузка...",
    "table": "Загрузка данных..."
  }
}
```

---

## Russian Pluralization Rules

Russian has 3 plural forms: `one`, `few`, `many`

| Count | Form | Example |
|-------|------|---------|
| 1, 21, 31... | one | 1 товар |
| 2-4, 22-24... | few | 2 товара |
| 0, 5-20, 25-30... | many | 5 товаров |

i18next handles this automatically with `_one`, `_few`, `_many` suffixes.

---

## Component Interface Updates

### Components Requiring Translation Integration

| Component | File | Translation Keys |
|-----------|------|-----------------|
| `PublicLayout` | `shared/PublicLayout.tsx` | `header.*`, `footer.*` |
| `CatalogPage` | `pages/CatalogPage.tsx` | `catalog.*` |
| `FilterBar` | `catalog/FilterBar.tsx` | `catalog.*`, `common.*` |
| `ProductCard` | `catalog/ProductCard.tsx` | `product.*` |
| `ProductGrid` | `catalog/ProductGrid.tsx` | `catalog.paginationInfo` |
| `CartIcon` | `cart/CartIcon.tsx` | `cart.ariaLabel*` |
| `ErrorState` | `shared/ErrorState.tsx` | `error.*`, `common.retry` |
| `EmptyState` | `shared/ErrorState.tsx` | `catalog.noResults.*` |
| `LoadingSkeleton` | `shared/LoadingSkeleton.tsx` | `loading.*` |
| `LoginPage` | `pages/LoginPage.tsx` | `auth.*` |

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| `LanguageSwitcher` | `shared/LanguageSwitcher.tsx` | Language selection UI |

---

## File Structure After Implementation

```
services/frontend/
├── public/
│   └── locales/
│       ├── en/
│       │   └── translation.json
│       └── ru/
│           └── translation.json
└── src/
    ├── i18n.ts                    # i18next configuration
    ├── types/
    │   └── i18n.ts                # i18n TypeScript types
    └── components/
        └── shared/
            └── LanguageSwitcher.tsx  # New component
```

---

## i18n Configuration File

```typescript
// src/i18n.ts

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import Backend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';
import { I18N_CONFIG } from '@/types/i18n';

i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: I18N_CONFIG.fallbackLocale,
    supportedLngs: I18N_CONFIG.supportedLocales,
    
    debug: import.meta.env.DEV,
    
    interpolation: {
      escapeValue: false, // React already escapes
    },
    
    detection: {
      order: ['localStorage', 'cookie', 'navigator'],
      caches: ['localStorage', 'cookie'],
      lookupLocalStorage: I18N_CONFIG.localStorageKey,
      lookupCookie: I18N_CONFIG.cookieKey,
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

## Integration with Existing Code

### Before (Hardcoded String)

```tsx
<Link to="/">Catalog</Link>
```

### After (Translated String)

```tsx
import { useTranslation } from 'react-i18next';

function Header() {
  const { t } = useTranslation();
  return <Link to="/">{t('header.catalog')}</Link>;
}
```

### Dynamic Values

```tsx
// Before
<span>{supplier_count} supplier{supplier_count !== 1 ? 's' : ''}</span>

// After
<span>{t('product.supplierCount', { count: supplier_count })}</span>
```

---

## Validation Rules

1. All translation keys must exist in both `en` and `ru` files
2. All interpolation variables (e.g., `{{year}}`) must be consistent across languages
3. Pluralization keys must follow i18next conventions (`_one`, `_few`, `_many` for Russian)
4. No hardcoded user-facing strings in components (except brand names)

---

## References

- [i18next Pluralization](https://www.i18next.com/translation-function/plurals)
- [React i18next useTranslation](https://react.i18next.com/latest/usetranslation-hook)

