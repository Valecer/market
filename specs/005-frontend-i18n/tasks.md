# Task List: Frontend Internationalization (i18n)

**Epic/Feature:** [spec.md](./spec.md) | [plan.md](./plan.md)

**Sprint/Milestone:** Phase 5 - Frontend Enhancements

**Owner:** Development Team

**Total Estimated Time:** ~8 hours

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 28 |
| **Phase 1 (Setup)** | 4 tasks |
| **Phase 2 (Foundational)** | 4 tasks |
| **Phase 3 (US-3: Manual Switch)** | 4 tasks |
| **Phase 4 (FR-4: Shell Translations)** | 6 tasks |
| **Phase 5 (FR-5: Catalog Translations)** | 6 tasks |
| **Phase 6 (Polish)** | 4 tasks |
| **Parallel Opportunities** | 12 tasks marked [P] |

---

## User Story Mapping

| Story | Description | Primary Tasks |
|-------|-------------|---------------|
| US-1 | Browser Language Detection | T005, T006, T025 |
| US-2 | Unsupported Language Fallback | T005, T006, T025 |
| US-3 | Manual Language Switch | T009-T012 |
| US-4 | Language Preference Persistence | T005, T006, T026 |
| US-5 | Language Switcher Accessibility | T009, T011, T027 |

---

## Phase 1: Setup

**Goal:** Install dependencies and create i18n infrastructure files.

**Duration:** 30 minutes

**Independent Test:** After Phase 1, `bun run dev` should start without errors.

### Tasks

- [ ] T001 Install i18next packages via `bun add i18next react-i18next i18next-http-backend i18next-browser-languagedetector` in `services/frontend/`
- [ ] T002 [P] Create i18n TypeScript types in `services/frontend/src/types/i18n.ts`
- [ ] T003 Create i18n configuration file in `services/frontend/src/i18n.ts`
- [ ] T004 Update app entry to import i18n and wrap with Suspense in `services/frontend/src/main.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Goal:** Create translation resource files that all user stories depend on.

**Duration:** 45 minutes

**Independent Test:** After Phase 2, app loads with English translations from `/locales/en/translation.json`.

### Tasks

- [ ] T005 Create directory structure for locales via `mkdir -p public/locales/en public/locales/ru` in `services/frontend/`
- [ ] T006 [P] Create English translation file with all keys in `services/frontend/public/locales/en/translation.json`
- [ ] T007 [P] Create Russian translation file with all keys in `services/frontend/public/locales/ru/translation.json`
- [ ] T008 Verify translations load correctly by checking browser console for i18next debug messages

---

## Phase 3: US-3 - Manual Language Switch

**Goal:** Enable users to manually switch between English and Russian via UI control.

**Duration:** 1 hour

**User Story:** As a user viewing the catalog, I want to manually switch between English and Russian so that I can use my preferred language regardless of browser settings.

**Acceptance Criteria:**
- [ ] Language switcher visible in header on all pages
- [ ] Switcher indicates currently active language
- [ ] Click changes language instantly (no page reload)
- [ ] All visible text updates to selected language

**Independent Test:** After Phase 3, clicking EN/RU buttons in header immediately changes hardcoded test text.

### Tasks

- [ ] T009 [US-3] Create LanguageSwitcher component with accessible button group in `services/frontend/src/components/shared/LanguageSwitcher.tsx`
- [ ] T010 [US-3] Export LanguageSwitcher from barrel file in `services/frontend/src/components/shared/index.ts`
- [ ] T011 [US-3] Add aria-label, aria-pressed, and role="group" for accessibility in `services/frontend/src/components/shared/LanguageSwitcher.tsx`
- [ ] T012 [US-3] Import and place LanguageSwitcher in header right section in `services/frontend/src/components/shared/PublicLayout.tsx`

---

## Phase 4: FR-4 - Global Shell Translations

**Goal:** Translate all static text in the global application shell (Header, Footer, Error/Loading states).

**Duration:** 1.5 hours

**Functional Requirement:** FR-4 (Priority: Critical) - All static text in the global application shell must be translated.

**Acceptance Criteria:**
- [ ] Header navigation items display in selected language
- [ ] User menu items (if logged in) display in selected language
- [ ] Footer content (copyright, links) displays in selected language
- [ ] No untranslated strings visible in shell components

**Independent Test:** After Phase 4, switching language updates Header, Footer, and error states.

### Tasks

- [ ] T013 [P] Add useTranslation hook and translate header navigation (Catalog, Cart, Admin, Login, Logout) in `services/frontend/src/components/shared/PublicLayout.tsx`
- [ ] T014 [P] Translate footer content (copyright with year interpolation, Privacy, Terms, Contact) in `services/frontend/src/components/shared/PublicLayout.tsx`
- [ ] T015 [P] Translate mobile menu aria-label in `services/frontend/src/components/shared/PublicLayout.tsx`
- [ ] T016 [P] Add useTranslation hook and translate error messages and retry button in `services/frontend/src/components/shared/ErrorState.tsx`
- [ ] T017 [P] Translate EmptyState default title and message in `services/frontend/src/components/shared/ErrorState.tsx`
- [ ] T018 [P] Translate loading aria-labels and sr-only text in `services/frontend/src/components/shared/LoadingSkeleton.tsx`

---

## Phase 5: FR-5 - Catalog Page Translations

**Goal:** Translate all static text on the public catalog page.

**Duration:** 2 hours

**Functional Requirement:** FR-5 (Priority: High) - All static text on the public catalog page must be translated.

**Acceptance Criteria:**
- [ ] Page headings and titles display in selected language
- [ ] Filter labels and placeholders display in selected language
- [ ] Pagination controls display in selected language
- [ ] Empty state messages display in selected language
- [ ] "Add to Cart" and similar action buttons display in selected language

**Independent Test:** After Phase 5, entire catalog page text changes when switching language.

### Tasks

- [ ] T019 [P] Add useTranslation hook and translate page title, subtitle, and updating indicator in `services/frontend/src/pages/CatalogPage.tsx`
- [ ] T020 [P] Translate search placeholder, category dropdown label, price range labels in `services/frontend/src/components/catalog/FilterBar.tsx`
- [ ] T021 [P] Translate "Clear" button and filter tag labels in `services/frontend/src/components/catalog/FilterBar.tsx`
- [ ] T022 [P] Translate "Add" button and supplier count with pluralization in `services/frontend/src/components/catalog/ProductCard.tsx`
- [ ] T023 [P] Translate pagination info with interpolation (Showing X-Y of Z) in `services/frontend/src/components/catalog/ProductGrid.tsx`
- [ ] T024 [P] Translate cart icon aria-label with item count pluralization in `services/frontend/src/components/cart/CartIcon.tsx`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal:** Verify all user stories work correctly and fix any layout issues.

**Duration:** 1.5 hours

**Independent Test:** All acceptance criteria pass for US-1 through US-5.

### Tasks

- [ ] T025 Verify language detection works for Russian browser (test with browser DevTools → Sensors → Locale) - validates US-1, US-2
- [ ] T026 Verify language preference persists after browser close/reopen (check localStorage for i18nextLng) - validates US-4
- [ ] T027 Verify keyboard navigation of LanguageSwitcher (Tab, Enter/Space) and screen reader announcements - validates US-5
- [ ] T028 Test Russian text layout in all components and fix any overflow/truncation issues

---

## Dependencies Graph

```
Phase 1: Setup
    T001 ─────────────────────────────┐
    T002 [P] ─────────────────────────┤
    T003 (depends on T002) ───────────┼──► Phase 2
    T004 (depends on T001, T003) ─────┘

Phase 2: Foundational
    T005 ─────────────────────────────┐
    T006 [P] (depends on T005) ───────┤
    T007 [P] (depends on T005) ───────┼──► Phase 3
    T008 (depends on T004, T006) ─────┘

Phase 3: US-3 Manual Switch
    T009 (depends on T003) ───────────┐
    T010 (depends on T009) ───────────┤
    T011 (depends on T009) ───────────┼──► Phase 4
    T012 (depends on T009, T010) ─────┘

Phase 4: FR-4 Shell Translations      Phase 5: FR-5 Catalog Translations
    T013-T018 [P] ────────────────┬───► T019-T024 [P] ──► Phase 6
                                  │
    (All depend on T004, T006)    └───► (All depend on T004, T006)

Phase 6: Polish
    T025-T028 (depend on all previous phases)
```

---

## Parallel Execution Opportunities

### Within Phase 1

```
T001 (install packages) ────┬──► T003 (config)
T002 (types) [P] ───────────┘
```

### Within Phase 2

```
T005 (mkdir) ──┬──► T006 (en.json) [P]
               └──► T007 (ru.json) [P]
```

### Within Phase 4 (All Independent)

```
T013 (header nav) [P] ──────────┐
T014 (footer) [P] ──────────────┤
T015 (mobile menu) [P] ─────────┤ (all can run in parallel)
T016 (error state) [P] ─────────┤
T017 (empty state) [P] ─────────┤
T018 (loading skeleton) [P] ────┘
```

### Within Phase 5 (All Independent)

```
T019 (CatalogPage) [P] ─────────┐
T020 (FilterBar search) [P] ────┤
T021 (FilterBar clear) [P] ─────┤ (all can run in parallel)
T022 (ProductCard) [P] ─────────┤
T023 (ProductGrid) [P] ─────────┤
T024 (CartIcon) [P] ────────────┘
```

---

## Implementation Strategy

### MVP Scope (Recommended First Delivery)

**Phases 1-3 only (~2 hours)**

Delivers:
- Working language switcher in header
- Language detection from browser
- Language persistence in localStorage
- Hardcoded English strings (not yet translated)

**Value:** Users can switch languages, preference persists. Foundation ready for translation work.

### Full Scope

**All Phases 1-6 (~8 hours)**

Delivers:
- Complete i18n infrastructure
- All shell and catalog text translated
- Russian text verified for layout
- All user stories complete

---

## File Changes Checklist

### New Files (5)

- [ ] `services/frontend/src/types/i18n.ts`
- [ ] `services/frontend/src/i18n.ts`
- [ ] `services/frontend/src/components/shared/LanguageSwitcher.tsx`
- [ ] `services/frontend/public/locales/en/translation.json`
- [ ] `services/frontend/public/locales/ru/translation.json`

### Modified Files (10)

- [ ] `services/frontend/src/main.tsx`
- [ ] `services/frontend/src/components/shared/index.ts`
- [ ] `services/frontend/src/components/shared/PublicLayout.tsx`
- [ ] `services/frontend/src/components/shared/ErrorState.tsx`
- [ ] `services/frontend/src/components/shared/LoadingSkeleton.tsx`
- [ ] `services/frontend/src/pages/CatalogPage.tsx`
- [ ] `services/frontend/src/components/catalog/FilterBar.tsx`
- [ ] `services/frontend/src/components/catalog/ProductCard.tsx`
- [ ] `services/frontend/src/components/catalog/ProductGrid.tsx`
- [ ] `services/frontend/src/components/cart/CartIcon.tsx`

---

## Success Verification

After all tasks complete, verify:

| Criterion | How to Test |
|-----------|-------------|
| Language Detection (US-1) | Set browser to Russian, visit app → interface in Russian |
| Fallback (US-2) | Set browser to German, visit app → interface in English |
| Manual Switch (US-3) | Click RU button → all text changes to Russian instantly |
| Persistence (US-4) | Select Russian, close browser, reopen → still Russian |
| Accessibility (US-5) | Tab to switcher, press Enter → language changes |
| Translation Coverage | No English text visible when Russian selected (except brand name) |
| Performance | Language switch feels instant (<100ms) |

---

## Notes

- Tasks marked `[P]` can be parallelized with other `[P]` tasks in same phase
- All file paths are relative to repository root
- Translation content provided in `plan/data-model.md`
- Use `bun run dev` to test changes with hot reload
- Check browser console for i18next debug messages if translations not loading

---

## References

- [Quickstart Guide](./plan/quickstart.md) - 20-minute setup walkthrough
- [Data Model](./plan/data-model.md) - Complete translation JSON content
- [Research](./plan/research.md) - Technology decisions and patterns
- [Translation Schema](./plan/contracts/translation-schema.json) - JSON Schema for validation

