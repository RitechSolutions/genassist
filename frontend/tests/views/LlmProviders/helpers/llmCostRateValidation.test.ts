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
    const errors = validateLlmCostRateForm(form({ provider: '', input_per_1k: 'abc', cache_read_per_1k: '-1' }));

    expect(Object.keys(errors).sort()).toEqual(['cache_read_per_1k', 'input_per_1k', 'provider']);
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

describe('rate syntax', () => {
  it.each(['0', '0.5', '0.00015', '12345678', '99999999.9999999999', '000000001', '0.12345678900'])(
    'accepts %s',
    (value) => {
      expect(rateErrors(value)).toBeUndefined();
    }
  );

  it.each(['', '   '])('requires a value (%s)', (value) => {
    expect(rateErrors(value)).toBe('A rate is required.');
  });

  it('trims surrounding whitespace, matching what the dialog submits', () => {
    expect(rateErrors('  0.5  ')).toBeUndefined();
  });

  it.each(['abc', '.', '.5', '+1', '-0', '-0.001', '1e-10', '1.', '1,5', '0x1'])(
    'rejects %s as not a plain decimal',
    (value) => {
      expect(rateErrors(value)).toBe('Enter a plain decimal number, for example 0.00015.');
    }
  );
});

describe("decimal precision, pinned to the backend's Decimal constraints", () => {
  it.each(['123456789', '123456789.1', '100000000'])('rejects %s for exceeding 8 whole digits', (value) => {
    expect(rateErrors(value)).toBe('Use at most 8 digits before the decimal point.');
  });

  it('counts whole digits after dropping insignificant leading zeros', () => {
    expect(rateErrors('0000012345678')).toBeUndefined();
    expect(rateErrors('0000123456789')).toBeDefined();
  });

  it.each(['0.00000000001', '12345678.99999999999'])('rejects %s for exceeding 10 decimal places', (value) => {
    expect(rateErrors(value)).toBe('Use at most 10 decimal places.');
  });

  it('counts decimal places after dropping insignificant trailing zeros', () => {
    expect(rateErrors('0.123456789000')).toBeUndefined();
    expect(rateErrors('0.0000000000')).toBeUndefined();
    expect(rateErrors('0.1234567890123456789')).toBeDefined();
  });

  it('applies the same rules to cache rates', () => {
    const errors = validateLlmCostRateForm(
      form({ cache_read_per_1k: '123456789', cache_creation_per_1k: '0.00000000001' })
    );

    expect(errors.cache_read_per_1k).toBe('Use at most 8 digits before the decimal point.');
    expect(errors.cache_creation_per_1k).toBe('Use at most 10 decimal places.');
  });
});
