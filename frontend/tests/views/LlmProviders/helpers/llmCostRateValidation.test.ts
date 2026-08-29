import { describe, expect, it } from 'vitest';
import { LlmCostRateFormValues, validateLlmCostRateForm } from '@/views/LlmProviders/helpers/llmCostRateValidation';

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
