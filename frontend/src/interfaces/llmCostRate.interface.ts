/**
 * A tenant-configured LLM price row (USD per 1K tokens)
 */
export interface LlmCostRate {
  id: string;
  provider_key: string;
  model_key: string;
  input_per_1k: string;
  output_per_1k: string;
  /** null = not configured, the provider default applies. "0" = free */
  cache_read_per_1k: string | null;
  cache_creation_per_1k: string | null;
  updated_at: string;
}

/** New rate. Provider/model are normalized (trim + lowercase) server-side */
export interface LlmCostRateCreatePayload {
  provider: string;
  model: string;
  input_per_1k: string;
  output_per_1k: string;
  cache_read_per_1k?: string | null;
  cache_creation_per_1k?: string | null;
}

/** Rate edit. Identity (provider/model) is fixed: delete and recreate to move a rate */
export interface LlmCostRateUpdatePayload {
  input_per_1k: string;
  output_per_1k: string;
  cache_read_per_1k?: string | null;
  cache_creation_per_1k?: string | null;
}

export interface LlmCostRateImportResult {
  inserted: number;
  updated: number;
  errors: string[];
}
