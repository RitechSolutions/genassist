/**
 * Client-side checks for the LLM cost rate form: presence and identity-field
 * length only. Rate syntax, precision, and range belong to the backend's
 * `RateDecimal`, the CSV import path uses the same schema, so both entry paths
 * accept the same values, and its 422s surface through the dialog's formError.
 */

export interface LlmCostRateFormValues {
  provider: string;
  model: string;
  input_per_1k: string;
  output_per_1k: string;
  cache_read_per_1k: string;
  cache_creation_per_1k: string;
}

export type LlmCostRateFieldErrors = Partial<Record<keyof LlmCostRateFormValues, string>>;

const PROVIDER_MAX = 64;
const MODEL_MAX = 512;

function keyError(value: string, label: string, max: number): string | undefined {
  if (!value) return `${label} is required.`;
  if (value.length > max) return `${label} must be ${max} characters or fewer.`;
  return undefined;
}

export function validateLlmCostRateForm(values: LlmCostRateFormValues): LlmCostRateFieldErrors {
  const errors: LlmCostRateFieldErrors = {};

  const provider = keyError(values.provider.trim(), 'Provider', PROVIDER_MAX);
  if (provider) errors.provider = provider;
  const model = keyError(values.model.trim(), 'Model', MODEL_MAX);
  if (model) errors.model = model;

  for (const field of ['input_per_1k', 'output_per_1k'] as const) {
    if (!values[field].trim()) errors[field] = 'A rate is required.';
  }

  // Cache rates may stay blank: "not configured" is not the same as 0.
  return errors;
}
