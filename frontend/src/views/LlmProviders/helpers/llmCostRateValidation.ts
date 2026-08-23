/**
 * Client-side checks for the LLM cost rate form, mirroring the backend's
 * `LlmCostRateCreate` / `LlmCostRateUpdate` schemas.
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
const MAX_WHOLE_DIGITS = 8;
const MAX_DECIMAL_PLACES = 10;

const PLAIN_DECIMAL = /^\d+(?:\.\d+)?$/;

function rateError(value: string): string | undefined {
  if (!PLAIN_DECIMAL.test(value)) {
    return 'Enter a plain decimal number, for example 0.00015.';
  }

  const [whole, fraction = ''] = value.split('.');
  if (whole.replace(/^0+/, '').length > MAX_WHOLE_DIGITS) {
    return `Use at most ${MAX_WHOLE_DIGITS} digits before the decimal point.`;
  }
  if (fraction.replace(/0+$/, '').length > MAX_DECIMAL_PLACES) {
    return `Use at most ${MAX_DECIMAL_PLACES} decimal places.`;
  }
  return undefined;
}

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
    const value = values[field].trim();
    const error = value ? rateError(value) : 'A rate is required.';
    if (error) errors[field] = error;
  }

  // Blank means "not configured", which is not the same as 0
  for (const field of ['cache_read_per_1k', 'cache_creation_per_1k'] as const) {
    const value = values[field].trim();
    if (!value) continue;
    const error = rateError(value);
    if (error) errors[field] = error;
  }

  return errors;
}
