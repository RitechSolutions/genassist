/**
 * A tenant-configured LLM price row (USD per 1K tokens)
 */
export interface LlmCostRate {
  id: string;
  provider_key: string;
  model_key: string;
  input_per_1k: string;
  output_per_1k: string;
  updated_at: string;
}

/** New rate. Provider/model are normalized (trim + lowercase) server-side */
export interface LlmCostRateCreatePayload {
  provider: string;
  model: string;
  input_per_1k: string;
  output_per_1k: string;
}

/** Rate edit. Identity (provider/model) is fixed: delete and recreate to move a rate */
export interface LlmCostRateUpdatePayload {
  input_per_1k: string;
  output_per_1k: string;
}

export interface LlmCostRateImportResult {
  inserted: number;
  updated: number;
  errors: string[];
}
