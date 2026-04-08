export interface LlmCostRate {
  id: string;
  provider_key: string;
  model_key: string;
  input_per_1k: number;
  output_per_1k: number;
  updated_at: string;
}

export interface LlmCostRateImportResult {
  inserted: number;
  updated: number;
  errors: string[];
}
