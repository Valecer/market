/**
 * i18n Configuration
 *
 * Initializes i18next with:
 * - HTTP backend for loading translations from /public/locales/
 * - Browser language detector for automatic language selection
 * - React integration with Suspense support
 *
 * Detection order: localStorage → cookie → navigator
 * Fallback language: English (en)
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import Backend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';
import { I18N_CONFIG } from '@/types/i18n';

i18n
  // Load translations from /public/locales/
  .use(Backend)
  // Detect user language from browser/localStorage
  .use(LanguageDetector)
  // Pass i18n instance to react-i18next
  .use(initReactI18next)
  // Initialize i18next
  .init({
    // Fallback language if detection fails or key is missing
    fallbackLng: I18N_CONFIG.fallbackLocale,
    // Supported languages
    supportedLngs: I18N_CONFIG.supportedLocales,

    // Debug output in development only
    debug: import.meta.env.DEV,

    // Default namespace
    defaultNS: 'translation',
    ns: ['translation'],

    // Don't escape values (React handles XSS protection)
    interpolation: {
      escapeValue: false,
    },

    // Language detection configuration
    detection: {
      // Detection order: stored preference first, then browser language
      order: ['localStorage', 'cookie', 'navigator'],
      // Cache detected language
      caches: ['localStorage', 'cookie'],
      // localStorage key
      lookupLocalStorage: I18N_CONFIG.localStorageKey,
      // Cookie key and settings
      lookupCookie: I18N_CONFIG.cookieKey,
      cookieOptions: {
        path: '/',
        // Cookie expires in 1 year
        maxAge: I18N_CONFIG.cookieExpiration * 24 * 60 * 60,
      },
    },

    // HTTP backend configuration
    backend: {
      // Path to translation files
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },

    // React-specific options
    react: {
      // Use Suspense for loading states
      useSuspense: true,
    },
  });

export default i18n;


