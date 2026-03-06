import { apiRequest } from "@/config/api";
import { Translation } from "@/interfaces/translation.interface";

export type TranslationPayload = {
  key: string;
  default?: string | null;
  en?: string | null;
  es?: string | null;
  fr?: string | null;
  de?: string | null;
  pt?: string | null;
  zh?: string | null;
};

export type TranslationUpdatePayload = Partial<Omit<TranslationPayload, "key">>;

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
    // If translation does not exist or request fails, treat as missing
    return null;
  }
};


