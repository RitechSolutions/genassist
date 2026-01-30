// Translation types and utilities
import defaultTranslationsData from './en.json';
import spanishTranslationsData from './es.json';
import frenchTranslationsData from './fr.json';
import germanTranslationsData from './de.json';
import italianTranslationsData from './it.json';
import portugueseTranslationsData from './pt.json';

export interface Translations {
  header: {
    subtitle: string;
  };
  menu: {
    title: string;
    resetConversation: string;
    language: string;
  };
  buttons: {
    startConversation: string;
    cancel: string;
    reset: string;
    save: string;
    saveChanges: string;
    add: string;
  };
  input: {
    placeholder: string;
  };
  labels: {
    agent: string;
    you: string;
  };
  dialog: {
    resetConversation: {
      title: string;
      message: string;
    };
  };
  feedback: {
    thumbsUp: string;
    thumbsDown: string;
  };
  thinking: {
    messages: string[];
  };
  time: {
    justNow: string;
    today: string;
    yesterday: string;
  };
  settings: {
    defaultDescription: string;
  };
  metadata: {
    addParameter: string;
    editParameter: string;
    defineKeyValue: string;
  };
  fileUpload?: {
    fileTypeNotSupported: string;
  };
}

// Default English translations loaded from JSON file
export const defaultTranslations: Translations = defaultTranslationsData as Translations;

/**
 * Get browser language code (e.g., 'en', 'es')
 * Returns the primary language code without region
 */
export function getBrowserLanguage(): string {
  if (typeof window === 'undefined' || !navigator.language) {
    return 'en';
  }
  // Extract primary language code (e.g., 'en' from 'en-US')
  return navigator.language.split('-')[0].toLowerCase();
}

/**
 * Get translation value by key path
 * Supports nested keys like 'header.subtitle' or 'dialog.resetConversation.title'
 */
export function getTranslation(
  key: string,
  translations: Translations,
  fallback?: string
): string | string[] {
  const keys = key.split('.');
  let value: any = translations;

  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = value[k as keyof typeof value];
    } else {
      return fallback || key;
    }
  }

  return value;
}

/**
 * Get a string translation (non-array)
 */
export function getTranslationString(
  key: string,
  translations: Translations,
  fallback?: string
): string {
  const value = getTranslation(key, translations, fallback);
  return Array.isArray(value) ? (fallback || key) : value;
}

/**
 * Get an array translation
 */
export function getTranslationArray(
  key: string,
  translations: Translations,
  fallback?: string[]
): string[] {
  const value = getTranslation(key, translations);
  return Array.isArray(value) ? value : (fallback || []);
}

/**
 * Resolve the language to use
 * Priority: prop → browser → 'en'
 */
export function resolveLanguage(languageProp?: string): string {
  if (languageProp) {
    return languageProp.toLowerCase();
  }
  return getBrowserLanguage();
}

/**
 * Merge custom translations with defaults
 * Custom translations override defaults, but don't need to include all keys
 */
export function mergeTranslations(
  custom?: Partial<Translations>,
  defaults: Translations = defaultTranslations
): Translations {
  if (!custom) {
    return defaults;
  }

  // Deep merge function
  const deepMerge = (target: any, source: any): any => {
    const output = { ...target };
    if (isObject(target) && isObject(source)) {
      Object.keys(source).forEach((key) => {
        if (isObject(source[key])) {
          if (!(key in target)) {
            Object.assign(output, { [key]: source[key] });
          } else {
            output[key] = deepMerge(target[key], source[key]);
          }
        } else {
          Object.assign(output, { [key]: source[key] });
        }
      });
    }
    return output;
  };

  return deepMerge(defaults, custom);
}

function isObject(item: any): boolean {
  return item && typeof item === 'object' && !Array.isArray(item);
}

// Spanish translations loaded from JSON file
export const spanishTranslations: Partial<Translations> = spanishTranslationsData as Partial<Translations>;

// French translations loaded from JSON file
export const frenchTranslations: Partial<Translations> = frenchTranslationsData as Partial<Translations>;

// German translations loaded from JSON file
export const germanTranslations: Partial<Translations> = germanTranslationsData as Partial<Translations>;

// Italian translations loaded from JSON file
export const italianTranslations: Partial<Translations> = italianTranslationsData as Partial<Translations>;

// Portuguese translations loaded from JSON file
export const portugueseTranslations: Partial<Translations> = portugueseTranslationsData as Partial<Translations>;

// Translations map for easy access by language code
export const translationsByLanguage: Record<string, Partial<Translations>> = {
  en: defaultTranslations,
  es: spanishTranslations,
  fr: frenchTranslations,
  de: germanTranslations,
  it: italianTranslations,
  pt: portugueseTranslations,
};

/**
 * Get translations for a specific language
 */
export function getTranslationsForLanguage(language: string): Translations {
  const langTranslations = translationsByLanguage[language.toLowerCase()];
  if (langTranslations) {
    return mergeTranslations(langTranslations, defaultTranslations);
  }
  return defaultTranslations;
}

