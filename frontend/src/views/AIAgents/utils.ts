import { Translation } from "@/interfaces/translation.interface";

export function pairsToObject(pairs: Array<{key: string, value: unknown}>): Record<string, unknown> {
    return pairs.reduce((obj, pair) => {
      if (typeof pair.value === 'string') {
        try {
          const parsedValue = JSON.parse(pair.value);
          obj[pair.key] = parsedValue;
        } catch (e) {
          obj[pair.key] = pair.value;
        }
      } else {
        obj[pair.key] = pair.value;
      }
      return obj;
    }, {} as Record<string, unknown>);
  }
  
  export function objectToPairs(obj: Record<string, unknown>): Array<{key: string, value: unknown}> {
    return Object.entries(obj).map(([key, value]) => ({
      key,
      value
    }));
  } 
  
export const getTranslationCount = (translation: Translation | null): number => {
  if (!translation) return 0;

  const locales: Array<keyof Pick<
    Translation,
    "en" | "es" | "fr" | "de" | "pt" | "zh"
  >> = ["en", "es", "fr", "de", "pt", "zh"];

  return locales.reduce((count, locale) => {
    const value = translation[locale];
    if (typeof value === "string" && value.trim().length > 0) {
      return count + 1;
    }
    return count;
  }, 0);
};