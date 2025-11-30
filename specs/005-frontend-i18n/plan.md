# Feature Plan: Frontend Internationalization (i18n)

**Date:** 2025-11-30

**Status:** Ready for Implementation

**Owner:** Development Team

---

## Overview

Implement internationalization (i18n) support for the Marketbel React frontend, enabling users to view the application in English or Russian. This feature adds automatic language detection, manual language switching via a UI control, and preference persistence across sessions.

**Primary Goal:** Improve accessibility for Russian-speaking users in the target market.

---

## Constitutional Compliance Check

This feature aligns with the following constitutional principles:

- **Single Responsibility:** Translation logic isolated in `i18n.ts`, language switcher as standalone component, translations in separate JSON files
- **Separation of Concerns:** Language detection, persistence, and UI display are distinct responsibilities handled by separate i18next plugins
- **Strong Typing:** TypeScript types for locale codes, language metadata, and component props
- **KISS:** Simple key-value JSON translations, single namespace for MVP, no complex pluralization beyond basic cases
- **DRY:** Centralized translation resources, reusable LanguageSwitcher component, shared translation keys for common UI elements
- **Design System Consistency:** LanguageSwitcher follows existing Tailwind CSS patterns, integrates with current header design

**Violations/Exceptions:** None

---

## Goals

- [x] Research react-i18next ecosystem best practices
- [x] Define translation file structure and key naming conventions
- [x] Design LanguageSwitcher component
- [ ] Install and configure i18next with React integration
- [ ] Implement automatic language detection from browser settings
- [ ] Implement language preference persistence (localStorage/cookie)
- [ ] Create English and Russian translation files
- [ ] Build accessible LanguageSwitcher component
- [ ] Translate global shell (Header, Footer)
- [ ] Translate Catalog page UI

---

## Non-Goals

Explicitly list what this feature will NOT accomplish to maintain scope discipline.

- Translating dynamic content (product names, descriptions, categories) from database
- Admin panel translation (procurement/sales interfaces)
- Date/time/number formatting localization
- Right-to-left (RTL) language support
- Additional languages beyond English and Russian
- Backend API error message localization
- Strict TypeScript typing for translation keys (deferred to iteration 2)

---

## Success Metrics

How will we measure success?

- **Language Detection Accuracy:** 95% of users with supported browser languages (en, ru) see correct language on first visit
- **Preference Persistence:** 100% of manually-selected language preferences persist across browser sessions
- **Translation Coverage:** 100% of in-scope UI strings translated in both English and Russian
- **Performance:** Language switch completes in <100ms (perceived instant)
- **Accessibility:** LanguageSwitcher passes Lighthouse/axe-core accessibility audit

---

## User Stories

### Story 1: First-Time Visitor Language Detection

**As a** new visitor with browser set to Russian
**I want** the interface to automatically display in Russian
**So that** I can immediately understand and use the application without configuration

**Acceptance Criteria:**

- [x] Browser language preference detected via `navigator.language`
- [x] Russian (`ru`, `ru-RU`) maps to Russian interface
- [x] English (`en`, `en-*`) maps to English interface
- [x] Unsupported languages fallback to English
- [ ] No visible flash of wrong language on page load

### Story 2: Manual Language Switch

**As a** user viewing the catalog
**I want** to manually switch between English and Russian
**So that** I can use my preferred language regardless of browser settings

**Acceptance Criteria:**

- [ ] Language switcher visible in header on all pages
- [ ] Switcher indicates currently active language
- [ ] Click changes language instantly (no page reload)
- [ ] All visible text updates to selected language

### Story 3: Language Preference Persistence

**As a** returning visitor who previously selected Russian
**I want** my language preference to be remembered
**So that** I don't need to re-select the language on every visit

**Acceptance Criteria:**

- [ ] Preference saved to localStorage on manual change
- [ ] Return visits use saved preference over browser detection
- [ ] Preference persists for at least 1 year

---

## Technical Approach

### Architecture

**Frontend Service (React + Vite + Tailwind v4.1):**

- **Responsibilities:**
  - Initialize i18next with plugins
  - Load translation resources from `/public/locales/`
  - Provide translation context to React components
  - Render LanguageSwitcher UI

- **Components:**
  - `src/i18n.ts` - i18next configuration
  - `src/types/i18n.ts` - TypeScript types
  - `src/components/shared/LanguageSwitcher.tsx` - Language toggle UI
  - Updated: `PublicLayout.tsx`, `CatalogPage.tsx`, `FilterBar.tsx`, `ProductCard.tsx`, etc.

- **State Management:**
  - i18next manages language state internally
  - React re-renders on language change via `react-i18next` context
  - Persistence via `i18next-browser-languagedetector` (localStorage/cookie)

- **API Integration:**
  - No API changes required
  - Translations are static JSON files served from `/public/locales/`

**Bun Service (API/User Logic):**

- Not affected by this feature

**Python Service (Data Processing):**

- Not affected by this feature

**Redis Queue Communication:**

- Not affected by this feature

**PostgreSQL Schema:**

- Not affected by this feature

### Design System

- [x] Collected documentation via `mcp context7` (react-i18next, i18next)
- [x] Tailwind v4.1 CSS-first approach confirmed (no `tailwind.config.js`)
- [ ] Consulted `mcp 21st-dev/magic` for UI design elements (LanguageSwitcher styling)

### Algorithm Choice

Following KISS principle, start with simplest solution:

- **Initial Implementation:** Simple key-value JSON translations with optional pluralization
- **Scalability Path:** If translation files grow large (>200 keys), split into namespaces with lazy loading

### Data Flow

```
User visits page
       ↓
i18next-browser-languagedetector checks:
  1. localStorage (saved preference)
  2. cookie (fallback persistence)
  3. navigator.language (browser setting)
       ↓
i18next-http-backend loads /locales/{lng}/translation.json
       ↓
React Suspense shows fallback until loaded
       ↓
App renders with translations via useTranslation hook
       ↓
User clicks LanguageSwitcher
       ↓
i18n.changeLanguage(lng) triggers:
  1. Language detector caches preference
  2. Backend loads new translation file (if not cached)
  3. React re-renders all translated components
```

---

## Type Safety

### TypeScript Types

```typescript
// src/types/i18n.ts

export type Locale = 'en' | 'ru';

export interface Language {
  code: Locale;
  label: string;
  name: string;
  flag?: string;
}

export const SUPPORTED_LANGUAGES: Language[] = [
  { code: 'en', label: 'EN', name: 'English', flag: '🇬🇧' },
  { code: 'ru', label: 'RU', name: 'Русский', flag: '🇷🇺' },
];

export const DEFAULT_LANGUAGE: Locale = 'en';

export const I18N_CONFIG = {
  defaultLocale: 'en' as Locale,
  fallbackLocale: 'en' as Locale,
  supportedLocales: ['en', 'ru'] as Locale[],
  localStorageKey: 'i18nextLng',
  cookieKey: 'i18nextLng',
  cookieExpiration: 365,
} as const;
```

### Component Props

```typescript
// src/components/shared/LanguageSwitcher.tsx

export interface LanguageSwitcherProps {
  className?: string;
}
```

---

## Testing Strategy

- **Unit Tests:**
  - Test translation key existence in both language files
  - Test interpolation with dynamic values
  - Test LanguageSwitcher renders correctly
  - Test language change callback fires

- **Integration Tests:**
  - Test language detection on fresh visit (mock navigator.language)
  - Test manual language switch updates all visible text
  - Test preference persistence across page reload

- **E2E Tests (Manual Verification):**
  - Verify all visible text changes on language switch
  - Verify no mixed-language content after switch
  - Verify Russian text doesn't overflow UI elements
  - Verify keyboard navigation of LanguageSwitcher

- **Coverage Target:** ≥80% for i18n-related business logic

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Russian text longer than English breaks layout | Medium | Medium | Test all components with Russian text, use CSS truncation/overflow |
| Missing translation keys cause blank text | High | Low | Enable i18next debug mode, log missing keys, show key as fallback |
| Translation files fail to load | High | Low | Bundle critical translations, use chained backend with fallback |
| Language flash on initial load | Medium | Medium | Use React Suspense with fallback, load translations before render |

---

## Dependencies

- **Bun Packages:**
  - `i18next` - Core i18n framework
  - `react-i18next` - React integration
  - `i18next-http-backend` - Load translations from server
  - `i18next-browser-languagedetector` - Detect browser language

- **Python Packages:** None

- **External Services:** None

- **Infrastructure:**
  - No Docker changes required
  - No environment variables required
  - Translation files served from `/public/locales/`

---

## Implementation Phases

| Phase | Tasks | Duration | Target |
|-------|-------|----------|--------|
| Phase 1: Setup | Install packages, configure i18n, create empty translation files | 30 min | Day 1 |
| Phase 2: Infrastructure | Create LanguageSwitcher component, add to Header | 1 hour | Day 1 |
| Phase 3: Shell Translation | Translate Header, Footer, ErrorState, LoadingSkeleton | 2 hours | Day 1 |
| Phase 4: Catalog Translation | Translate CatalogPage, FilterBar, ProductCard, ProductGrid | 2 hours | Day 2 |
| Phase 5: Testing & Polish | Verify all translations, test layouts, fix overflow issues | 2 hours | Day 2 |

**Total Estimated Time:** ~8 hours

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/i18n.ts` | i18next configuration |
| `src/types/i18n.ts` | TypeScript types for i18n |
| `src/components/shared/LanguageSwitcher.tsx` | Language toggle component |
| `public/locales/en/translation.json` | English translations |
| `public/locales/ru/translation.json` | Russian translations |

### Modified Files

| File | Changes |
|------|---------|
| `src/main.tsx` | Import i18n config, wrap app in Suspense |
| `src/components/shared/index.ts` | Export LanguageSwitcher |
| `src/components/shared/PublicLayout.tsx` | Add LanguageSwitcher, translate header/footer text |
| `src/components/shared/ErrorState.tsx` | Translate error messages |
| `src/components/shared/LoadingSkeleton.tsx` | Translate loading aria-labels |
| `src/pages/CatalogPage.tsx` | Translate page title, subtitle |
| `src/components/catalog/FilterBar.tsx` | Translate placeholders, labels |
| `src/components/catalog/ProductCard.tsx` | Translate "Add" button |
| `src/components/catalog/ProductGrid.tsx` | Translate pagination info |
| `src/components/cart/CartIcon.tsx` | Translate aria-label |

---

## Open Questions

All questions resolved during research phase. See `plan/research.md` for decisions.

---

## References

- Feature Specification: `/specs/005-frontend-i18n/spec.md`
- Research Document: `/specs/005-frontend-i18n/plan/research.md`
- Data Model: `/specs/005-frontend-i18n/plan/data-model.md`
- Quickstart Guide: `/specs/005-frontend-i18n/plan/quickstart.md`
- Translation Schema: `/specs/005-frontend-i18n/plan/contracts/translation-schema.json`
- [react-i18next Documentation](https://react.i18next.com/)
- [i18next Documentation](https://www.i18next.com/)

---

**Approval Signatures:**

- [ ] Technical Lead
- [ ] Product Owner
- [ ] Architecture Review
