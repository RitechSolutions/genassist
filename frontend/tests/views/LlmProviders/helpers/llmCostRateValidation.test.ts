import { describe, expect, it } from 'vitest';
import {
  changedCacheRates,
  LlmCostRateFormValues,
  serializeCacheRate,
  validateLlmCostRateForm,
} from '@/views/LlmProviders/helpers/llmCostRateValidation';

const VALID: LlmCostRateFormValues = {
  provider: 'openai',
  model: 'gpt-4o',
  input_per_1k: '0.0025',
  output_per_1k: '0.01',
  cache_read_per_1k: '',
  cache_creation_per_1k: '',
};

const form = (over: Partial<LlmCostRateFormValues> = {}): LlmCostRateFormValues => ({
  ...VALID,
  ...over,
});

const rateErrors = (value: string) => validateLlmCostRateForm(form({ input_per_1k: value })).input_per_1k;

describe('validateLlmCostRateForm', () => {
  it('accepts a complete, well-formed row', () => {
    expect(validateLlmCostRateForm(form())).toEqual({});
  });

  it('accepts configured cache rates, zero included', () => {
    expect(validateLlmCostRateForm(form({ cache_read_per_1k: '0.000025', cache_creation_per_1k: '0' }))).toEqual({});
  });

  it('treats blank cache rates as not configured', () => {
    expect(validateLlmCostRateForm(form({ cache_read_per_1k: '  ', cache_creation_per_1k: '' }))).toEqual({});
  });

  it('reports one message per field', () => {
    const errors = validateLlmCostRateForm(form({ provider: '', input_per_1k: '  ' }));

    expect(Object.keys(errors).sort()).toEqual(['input_per_1k', 'provider']);
    expect(errors.model).toBeUndefined();
  });
});

describe('identity fields', () => {
  it.each([
    ['provider', ''],
    ['provider', '   '],
    ['model', ''],
    ['model', '\t'],
  ] as const)('requires a non-blank %s', (field, value) => {
    expect(validateLlmCostRateForm(form({ [field]: value }))[field]).toBeDefined();
  });

  it("enforces the backend's length caps", () => {
    expect(validateLlmCostRateForm(form({ provider: 'p'.repeat(64) })).provider).toBeUndefined();
    expect(validateLlmCostRateForm(form({ provider: 'p'.repeat(65) })).provider).toBeDefined();
    expect(validateLlmCostRateForm(form({ model: 'm'.repeat(512) })).model).toBeUndefined();
    expect(validateLlmCostRateForm(form({ model: 'm'.repeat(513) })).model).toBeDefined();
  });
});

describe('rate values', () => {
  it.each(['0', '0.5', '0.00015', '12345678', '99999999.9999999999'])('accepts %s', (value) => {
    expect(rateErrors(value)).toBeUndefined();
  });

  it.each(['.5', '+1', '1.', '1e-7', '1E+3', '1_000'])('leaves backend-valid %s to the backend', (value) => {
    expect(rateErrors(value)).toBeUndefined();
  });

  it.each(['abc', '-0.001', '0.00000000001'])('does not pre-judge %s client-side', (value) => {
    expect(rateErrors(value)).toBeUndefined();
  });

  it.each(['', '   '])('requires a value (%s)', (value) => {
    expect(rateErrors(value)).toBe('A rate is required.');
  });

  it('trims surrounding whitespace, matching what the dialog submits', () => {
    expect(rateErrors('  0.5  ')).toBeUndefined();
  });
});

describe('serializeCacheRate', () => {
  it.each(['', '   '])('sends a blank rate as null so the bucket stays unset (%j)', (value) => {
    expect(serializeCacheRate(value)).toBeNull();
  });

  it.each(['0', '0.0', ' 0 '])('keeps an explicit zero as a configured free rate (%j)', (value) => {
    expect(serializeCacheRate(value)).toBe(value.trim());
  });

  it('trims a configured rate without reformatting it', () => {
    expect(serializeCacheRate(' 0.000025 ')).toBe('0.000025');
  });
});

describe('changedCacheRates', () => {
  const prefill = form({ cache_read_per_1k: '0.0001', cache_creation_per_1k: '' });

  it('omits both fields when neither was touched, so the backend keeps what it has', () => {
    expect(changedCacheRates(form({ ...prefill }), prefill)).toEqual({});
  });

  it('sends null only for the field the user cleared', () => {
    const edited = form({ ...prefill, cache_read_per_1k: '' });

    expect(changedCacheRates(edited, prefill)).toEqual({ cache_read_per_1k: null });
  });

  it('sends a newly configured rate, zero included', () => {
    const edited = form({ ...prefill, cache_creation_per_1k: '0' });

    expect(changedCacheRates(edited, prefill)).toEqual({ cache_creation_per_1k: '0' });
  });

  it('treats a whitespace-only edit of a blank field as untouched', () => {
    expect(changedCacheRates(form({ ...prefill, cache_creation_per_1k: '  ' }), prefill)).toEqual({});
  });
});
