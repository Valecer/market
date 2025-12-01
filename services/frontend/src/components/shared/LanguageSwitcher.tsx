/**
 * LanguageSwitcher Component
 *
 * Simple toggle button to switch between English and Russian.
 * Displays current language code and toggles to the other language on click.
 *
 * Design System: Tailwind CSS with minimal button styling
 * Accessibility: Keyboard navigable, aria-label describes action
 */

import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import type { Locale } from '@/types/i18n';

interface LanguageSwitcherProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * Language toggle button - shows current language, clicks to switch
 */
export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation();
  
  // Get current language, normalize regional variants (e.g., en-US → en)
  const currentLang = (i18n.language?.split('-')[0] || 'en') as Locale;
  const nextLang: Locale = currentLang === 'en' ? 'ru' : 'en';
  
  // Display label for current language
  const displayLabel = currentLang.toUpperCase();

  const handleToggle = () => {
    i18n.changeLanguage(nextLang);
  };

  return (
    <button
      onClick={handleToggle}
      aria-label={t('header.languageSelect')}
      className={cn(
        'inline-flex items-center justify-center px-3 py-1.5',
        'text-sm font-semibold rounded-md transition-all duration-200',
        'bg-slate-100 text-slate-700 hover:bg-slate-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
        className
      )}
    >
      {displayLabel}
    </button>
  );
}
