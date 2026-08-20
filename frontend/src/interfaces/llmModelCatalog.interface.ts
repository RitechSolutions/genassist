/**
 * A tenant-registered LLM model.
 *
 * These extend the built-in model lists that ship with each provider type — they
 * never replace them. The built-in entry wins whenever both define the same
 * model key, in which case `is_shadowed_by_builtin` is true.
 */
export interface LlmModelCatalogEntry {
  id: string;
  provider_key: string;
  model_key: string;
  label: string;
  is_active: number;
  created_at?: string | null;
  updated_at?: string | null;
  is_shadowed_by_builtin: boolean;
}

/** A provider type that exposes a Model field, plus the models already built in. */
export interface LlmModelCatalogProvider {
  provider_key: string;
  name: string;
  builtin_model_keys: string[];
}

export interface LlmModelCatalogCreatePayload {
  provider_key: string;
  model_key: string;
  label: string;
  is_active?: number;
}

/** Identity (provider + model key) is fixed: delete and re-add to move an entry. */
export interface LlmModelCatalogUpdatePayload {
  label?: string;
  is_active?: number;
}
