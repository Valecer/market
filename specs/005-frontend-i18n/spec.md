# Feature Specification: Frontend Internationalization (i18n)

**Version:** 1.0.0

**Last Updated:** 2025-11-30

**Status:** Draft

---

## Constitutional Alignment

**Relevant Principles:**

- **Single Responsibility:** Translation concerns isolated from business logic components
- **Separation of Concerns:** Language detection, persistence, and display are distinct concerns
- **Strong Typing:** Translation keys are typed to prevent missing translations
- **KISS:** Simple key-value translation files, no complex pluralization rules initially
- **DRY:** Centralized translation resources, reusable language switcher component

**Compliance Statement:**

This specification adheres to all constitutional principles. Translation infrastructure integrates with existing React architecture without modifying business logic components.

---

## Overview

### Purpose

Enable users to view the Marketbel application interface in their preferred language (English or Russian), improving accessibility for the target market which includes both English and Russian-speaking users.

### Scope

**In Scope:**

- Language detection from browser/system settings
- Manual language switching via UI control
- Language preference persistence across sessions
- Translation of static UI text in:
  - Global Header (navigation, user menu, logo text)
  - Sidebar navigation items
  - Footer content
  - Catalog page (headings, filters, buttons, empty states, pagination)
  - Common UI elements (buttons, labels, error messages, tooltips)

**Out of Scope:**

- Database schema changes for dynamic content (product names, descriptions, categories)
- Backend API localization (error messages from API remain in English)
- Date/time/number formatting localization (future enhancement)
- Right-to-left (RTL) language support
- Additional languages beyond English and Russian
- Admin panel translation (procurement/sales interfaces)

---

## User Scenarios & Testing

### US-1: First-Time Visitor (Browser Language Detection)

**Actor:** New visitor with browser set to Russian

**Scenario:**
1. User visits Marketbel for the first time
2. System detects browser language preference (Russian)
3. Interface displays in Russian automatically
4. User browses catalog without any manual language configuration

**Expected Outcome:** Russian-speaking users see interface in their language without any action required.

### US-2: First-Time Visitor (Unsupported Language Fallback)

**Actor:** New visitor with browser set to German (unsupported)

**Scenario:**
1. User visits Marketbel for the first time
2. System detects browser language (German) but it's not supported
3. Interface displays in English (fallback default)
4. User can manually switch to Russian if preferred

**Expected Outcome:** Users with unsupported browser languages receive a usable English interface.

### US-3: Manual Language Switch

**Actor:** Any authenticated or anonymous user

**Scenario:**
1. User is viewing the catalog in English
2. User locates language switcher in header
3. User clicks to switch to Russian
4. Interface immediately updates to Russian without page reload
5. All visible text (header, sidebar, catalog content) changes to Russian

**Expected Outcome:** Instant language change provides smooth, app-like experience.

### US-4: Language Preference Persistence

**Actor:** Returning visitor who previously selected Russian

**Scenario:**
1. User previously visited and manually selected Russian
2. User closes browser and returns days later
3. Interface loads in Russian (remembered preference)
4. User's choice persists regardless of browser language setting

**Expected Outcome:** Users don't need to re-select language on every visit.

### US-5: Language Switcher Accessibility

**Actor:** User navigating with keyboard only

**Scenario:**
1. User tabs through header navigation
2. Language switcher is focusable and clearly indicated
3. User activates switcher with keyboard (Enter/Space)
4. Language options are navigable and selectable via keyboard
5. Screen reader announces current language and available options

**Expected Outcome:** All users, including those with accessibility needs, can change language.

---

## Functional Requirements

### FR-1: Language Detection

**Priority:** Critical

**Description:** The system must automatically detect the user's preferred language on first visit using browser/system language settings.

**Acceptance Criteria:**

- [ ] AC-1: When a new user visits with browser language set to Russian (`ru`, `ru-RU`), interface displays in Russian
- [ ] AC-2: When a new user visits with browser language set to English (`en`, `en-US`, `en-GB`), interface displays in English
- [ ] AC-3: When a new user visits with unsupported browser language, interface displays in English (fallback)
- [ ] AC-4: Detection occurs before first render to prevent language flash/flicker

**Dependencies:** None

---

### FR-2: Language Preference Persistence

**Priority:** Critical

**Description:** When a user manually changes the language, this preference must persist across browser sessions.

**Acceptance Criteria:**

- [ ] AC-1: After manual language change, preference is saved to browser storage
- [ ] AC-2: On return visit, saved preference takes precedence over browser detection
- [ ] AC-3: Clearing browser storage resets to auto-detection behavior
- [ ] AC-4: Preference persists for at least 1 year unless manually cleared

**Dependencies:** FR-1 (Language Detection)

---

### FR-3: Language Switcher Component

**Priority:** Critical

**Description:** A visible, accessible UI control must allow users to manually switch between supported languages.

**Acceptance Criteria:**

- [ ] AC-1: Switcher is visible in the global header on all pages
- [ ] AC-2: Switcher clearly indicates the currently active language
- [ ] AC-3: Switcher shows available language options (EN/RU)
- [ ] AC-4: Clicking a language option immediately updates the interface
- [ ] AC-5: Language change occurs without full page reload
- [ ] AC-6: Switcher is keyboard accessible (focusable, activatable via Enter/Space)
- [ ] AC-7: Switcher has appropriate ARIA labels for screen readers

**Dependencies:** FR-2 (Language Preference Persistence)

---

### FR-4: Global Shell Translations

**Priority:** Critical

**Description:** All static text in the global application shell must be translated.

**Acceptance Criteria:**

- [ ] AC-1: Header navigation items display in selected language
- [ ] AC-2: User menu items (if logged in) display in selected language
- [ ] AC-3: Sidebar navigation labels display in selected language
- [ ] AC-4: Footer content (copyright, links) displays in selected language
- [ ] AC-5: No untranslated strings visible in shell components

**Dependencies:** FR-3 (Language Switcher)

---

### FR-5: Catalog Page Translations

**Priority:** High

**Description:** All static text on the public catalog page must be translated.

**Acceptance Criteria:**

- [ ] AC-1: Page headings and titles display in selected language
- [ ] AC-2: Filter labels and options display in selected language
- [ ] AC-3: Sort options display in selected language
- [ ] AC-4: Pagination controls display in selected language
- [ ] AC-5: Empty state messages display in selected language
- [ ] AC-6: Loading state messages display in selected language
- [ ] AC-7: Error messages for catalog operations display in selected language
- [ ] AC-8: "Add to Cart" and similar action buttons display in selected language

**Dependencies:** FR-4 (Global Shell Translations)

---

### FR-6: Translation Resource Management

**Priority:** High

**Description:** Translation content must be organized in maintainable, structured resource files.

**Acceptance Criteria:**

- [ ] AC-1: Each supported language has its own translation resource file
- [ ] AC-2: Translation keys are organized by feature/page namespace
- [ ] AC-3: Missing translation keys display the key name (not blank) in development
- [ ] AC-4: Translation files are loadable without application code changes
- [ ] AC-5: Adding new translated strings requires only resource file updates

**Dependencies:** None

---

## Non-Functional Requirements

### NFR-1: Performance

- Language switch completes in under 100 milliseconds (perceived instant)
- Initial language detection adds no visible delay to page load
- Translation resources load efficiently (bundled or lazy-loaded appropriately)

### NFR-2: User Experience

- No visible flash of wrong language content on page load
- Language switcher is discoverable but not intrusive
- Consistent language across all components after switch (no mixed languages)

### NFR-3: Accessibility

- Language switcher meets WCAG 2.1 Level AA compliance
- `lang` attribute on HTML element updates to reflect selected language
- Screen readers announce language changes appropriately

### NFR-4: Maintainability

- Adding a new language requires minimal code changes (primarily new resource file)
- Translation keys follow consistent naming convention
- Missing translations are logged for developer awareness

---

## Success Criteria

1. **Language Detection Accuracy:** 95% of users with supported browser languages see correct language on first visit
2. **Preference Retention:** 100% of manually-selected language preferences persist across sessions for returning users
3. **Translation Coverage:** 100% of in-scope UI strings are translated in both English and Russian
4. **User Task Completion:** Users can complete catalog browsing tasks equally well in either language
5. **Accessibility Compliance:** Language switcher passes automated accessibility testing (axe-core, Lighthouse)
6. **Performance:** Language switch is perceived as instant (< 100ms) by users

---

## Key Entities

### Translation Resource Structure

| Namespace | Content Examples |
|-----------|------------------|
| `common` | Buttons (Save, Cancel, Submit), Loading states, Error messages |
| `header` | Navigation items, User menu, Language switcher labels |
| `sidebar` | Navigation categories, Section headings |
| `footer` | Copyright text, Legal links |
| `catalog` | Page title, Filter labels, Sort options, Empty states |
| `cart` | Cart button label, Item count text |

### Supported Locales

| Code | Language | Direction | Status |
|------|----------|-----------|--------|
| `en` | English | LTR | Default/Fallback |
| `ru` | Russian | LTR | Supported |

---

## Assumptions

1. **Browser API Availability:** Modern browsers support `navigator.language` or `navigator.languages` for language detection
2. **LocalStorage Availability:** Browser localStorage is available for preference persistence (cookies as fallback if needed)
3. **Existing Design System:** Current Tailwind v4.1 CSS supports any additional styling needed for language switcher
4. **Translation Content:** Product/business team will provide Russian translations for all UI strings
5. **Single Active Language:** Only one language is active at a time (no mixed-language interface)

---

## Open Questions

None - all requirements are sufficiently defined for implementation planning.

---

## Appendix

### References

- [WCAG 2.1 Language Requirements](https://www.w3.org/WAI/WCAG21/Understanding/language-of-page.html)
- Phase 3 Frontend Spec: `/specs/003-frontend-app/spec.md`

### Glossary

- **i18n:** Internationalization - the process of designing software so it can be adapted to different languages
- **Locale:** A combination of language and regional settings (e.g., `en-US`, `ru-RU`)
- **LTR:** Left-to-right text direction
- **Translation Key:** A unique identifier used to look up translated text (e.g., `header.navigation.home`)

---

**Approval:**

- [ ] Tech Lead: [Name] - [Date]
- [ ] Product: [Name] - [Date]
- [ ] QA: [Name] - [Date]
