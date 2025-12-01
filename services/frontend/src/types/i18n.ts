/**
 * i18n TypeScript Types
 *
 * Type definitions for internationalization support.
 * Defines supported locales, language metadata, and configuration.
 */

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


