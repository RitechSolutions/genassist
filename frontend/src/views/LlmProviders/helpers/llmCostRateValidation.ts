/**
 * Validates presence and length only. Backend RateDecimal validates syntax,
 * precision, and range; 422 errors surface as formError.
 */

import type { LlmCostRateUpdatePayload } from '@/interfaces/llmCostRate.interface';

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

/** Trimmed rate for the API. Blank clears the rate to unset; "0" is kept as a real price. */
export function serializeCacheRate(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

type CacheRatePatch = Pick<LlmCostRateUpdatePayload, 'cache_read_per_1k' | 'cache_creation_per_1k'>;

const CACHE_FIELDS = ['cache_read_per_1k', 'cache_creation_per_1k'] as const;

/**
 * Only send changed cache-rate fields: skip unchanged ones, send null for fields the user cleared.
 */
export function changedCacheRates(values: LlmCostRateFormValues, prefill: LlmCostRateFormValues): CacheRatePatch {
  const patch: CacheRatePatch = {};
  for (const field of CACHE_FIELDS) {
    if (values[field].trim() !== prefill[field].trim()) {
      patch[field] = serializeCacheRate(values[field]);
    }
  }
  return patch;
}
