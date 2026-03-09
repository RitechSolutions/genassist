import { apiRequest } from "@/config/api";
import { Language, Translation } from "@/interfaces/translation.interface";

export type TranslationPayload = {
  key: string;
  default?: string | null;
  translations: Record<string, string>;
};

export type TranslationUpdatePayload = {
  default?: string | null;
  translations?: Record<string, string>;
};

export const getLanguages = async (): Promise<Language[]> => {
  const data = await apiRequest<Language[]>("GET", "translations/languages");
  if (!data || !Array.isArray(data)) {
    return [];
  }
  return data;
};

export const getTranslations = async (): Promise<Translation[]> => {
  const data = await apiRequest<Translation[]>("GET", "translations");

  if (!data || !Array.isArray(data)) {
    return [];
  }

  return data;
};

export const createTranslation = async (
  translation: TranslationPayload
): Promise<Translation> => {
  const response = await apiRequest<Translation>(
    "POST",
    "translations",
    translation
  );

  if (!response) {
    throw new Error("Failed to create translation");
  }

  return response;
};

export const updateTranslation = async (
  key: string,
  updates: TranslationUpdatePayload
): Promise<Translation> => {
  const response = await apiRequest<Translation>(
    "PATCH",
    `translations/${encodeURIComponent(key)}`,
    updates
  );

  if (!response) {
    throw new Error("Failed to update translation");
  }

  return response;
};

export const deleteTranslation = async (key: string): Promise<void> => {
  await apiRequest("DELETE", `translations/${encodeURIComponent(key)}`);
};

export const getTranslationByKey = async (
  key: string
): Promise<Translation | null> => {
  try {
    const data = await apiRequest<Translation>(
      "GET",
      `translations/${encodeURIComponent(key)}`
    );
    return data;
  } catch (_error) {
    return null;
  }
};
