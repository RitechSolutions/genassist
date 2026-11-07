import { describe, expect, it } from 'vitest';

import {
  buildInferenceParams,
  featureDefaultsChanged,
  inferenceParamsUpdate,
  latestInferenceParams,
  featureListError,
  featuresText,
  formFeatures,
  mlModelSaveErrorMessage,
  parseModelFeatures,
} from '@/views/MLModels/components/mlModelForm';

describe('parseModelFeatures', () => {
  it.each([
    ['year, month, dow', ['year', 'month', 'dow']],
    ['x,y', ['x', 'y']],
    ["'x', 'y'", ['x', 'y']],
    ['"x", "y"', ['x', 'y']],
    ["['x', 'y']", ['x', 'y']],
    ['["x", "y"]', ['x', 'y']],
    ["year, month, dow,", ['year', 'month', 'dow']],
    [" 'hour_cos', 'hour_sin', 'sessions', ", ['hour_cos', 'hour_sin', 'sessions']],
    ["O'Brien, customer_age", ["O'Brien", 'customer_age']],
    [" , , ", []],
    ["'', \"\"", []],
    ['', []],
    ['hour, dow, hour', ['hour', 'dow']],
    ["'hour', 'dow', 'hour'", ['hour', 'dow']],
    ['["a,b", "c"]', ['a,b', 'c']],
    ['["say \\"hi\\"", "x"]', ['say "hi"', 'x']],
    ['["x", "x", " "]', ['x']],
  ])('reads %j in order', (raw, expected) => {
    expect(parseModelFeatures(raw)).toEqual(expected);
  });
});

describe('featuresText', () => {
  it('shows ordinary names as a plain comma list', () => {
    expect(featuresText(['year', 'month', 'dow'])).toBe('year, month, dow');
    expect(featuresText(null)).toBe('');
  });

  it.each([
    [['a,b', 'year']],
    [[' padded', 'year']],
    [["O'Brien", 'x']],
    [['"quoted"', 'x']],
    [['[x]']],
    [['line\nbreak', 'x']],
    [['year', 'month', 'dow']],
  ])('reads %j back exactly', (stored) => {
    expect(parseModelFeatures(featuresText(stored))).toEqual(stored);
  });

  it('keeps an odd name intact when another feature is added', () => {
    expect(parseModelFeatures(featuresText(['a,b', 'year']).replace(/]$/, ', "month"]'))).toEqual([
      'a,b',
      'year',
      'month',
    ]);
  });
});

describe('featureListError', () => {
  it.each([
    ['["a,b","year"], month'],
    ['["a", "b]'],
    ['["a", "b"'],
  ])('rejects the mistyped list %j', (raw) => {
    expect(featureListError(raw)).toMatch(/brackets and quotes/);
  });

  it.each([
    ['year, month'],
    ["['x', 'y']"],
    ['["a,b", "c"]'],
    ["O'Brien, x"],
    [''],
  ])('accepts %j', (raw) => {
    expect(featureListError(raw)).toBeNull();
  });
});

describe('formFeatures', () => {
  it('sends the stored list unchanged while the box still shows it', () => {
    const stored = [' ', 'x', 'x'];
    expect(formFeatures(featuresText(stored), stored)).toEqual(stored);
  });

  it('reads the box once it has been edited', () => {
    expect(formFeatures('x, y', ['x'])).toEqual(['x', 'y']);
    expect(formFeatures("'x', 'y'", null)).toEqual(['x', 'y']);
  });
});

describe('buildInferenceParams', () => {
  it('applies changed defaults to the latest model settings', () => {
    expect(buildInferenceParams({ ratioBaselineColumn: 'latest' }, { hour: 1 })).toEqual({
      ratioBaselineColumn: 'latest',
      featureDefaults: { hour: 1 },
    });
  });

  it('keeps the training-fills switch unless it is changed', () => {
    expect(buildInferenceParams({ useTrainingFills: true }, { hour: 1 })).toEqual({
      useTrainingFills: true,
      featureDefaults: { hour: 1 },
    });
    expect(buildInferenceParams({ ratioBaselineColumn: 'latest' }, {}, true)).toEqual({
      ratioBaselineColumn: 'latest',
      useTrainingFills: true,
    });
  });

  it('removes the training-fills switch when it is turned off', () => {
    expect(buildInferenceParams({ useTrainingFills: true }, {}, false)).toBeNull();
  });

  it('removes defaults without removing the latest baseline', () => {
    expect(buildInferenceParams({ ratioBaselineColumn: 'latest', featureDefaults: { hour: 0 } }, {})).toEqual({
      ratioBaselineColumn: 'latest',
    });
  });
});

describe('featureDefaultsChanged', () => {
  it('does not mark an unchanged defaults field as changed', () => {
    expect(featureDefaultsChanged({ ratioBaselineColumn: 'baseline', featureDefaults: { hour: 0 } }, { hour: 0 })).toBe(
      false
    );
  });

  it('detects added, changed, and removed defaults', () => {
    expect(featureDefaultsChanged(null, { hour: 0 })).toBe(true);
    expect(featureDefaultsChanged({ featureDefaults: { hour: 0 } }, { hour: 1 })).toBe(true);
    expect(featureDefaultsChanged({ featureDefaults: { hour: 0 } }, {})).toBe(true);
  });
});

describe('inferenceParamsUpdate', () => {
  it('omits inference params when neither setting changed', () => {
    expect(
      inferenceParamsUpdate(
        { ratioBaselineColumn: 'latest', featureDefaults: { hour: 0 }, useTrainingFills: true },
        { featureDefaults: { hour: 0 }, useTrainingFills: true }
      )
    ).toBeUndefined();
    expect(
      inferenceParamsUpdate({ featureDefaults: { hour: 0 } }, { featureDefaults: { hour: 0 }, useTrainingFills: false })
    ).toBeUndefined();
  });

  it('returns only the defaults when only the defaults changed', () => {
    expect(
      inferenceParamsUpdate(
        { ratioBaselineColumn: 'cached', featureDefaults: { hour: 0 } },
        { featureDefaults: { hour: 1 }, useTrainingFills: false }
      )
    ).toEqual({ featureDefaults: { hour: 1 } });
  });

  it('returns only the switch when only the training-fills switch changed', () => {
    expect(
      inferenceParamsUpdate({ featureDefaults: { hour: 0 } }, { featureDefaults: { hour: 0 }, useTrainingFills: true })
    ).toEqual({ useTrainingFills: true });
    expect(
      inferenceParamsUpdate({ useTrainingFills: true }, { featureDefaults: {}, useTrainingFills: false })
    ).toEqual({ useTrainingFills: false });
  });

  it('keeps newer stored defaults when only the switch is saved', () => {
    // The form loaded { hour: 0 }; someone else has since saved { hour: 5 }.
    const update = inferenceParamsUpdate(
      { featureDefaults: { hour: 0 } },
      { featureDefaults: { hour: 0 }, useTrainingFills: true }
    );
    expect(
      buildInferenceParams({ featureDefaults: { hour: 5 } }, update?.featureDefaults, update?.useTrainingFills)
    ).toEqual({ featureDefaults: { hour: 5 }, useTrainingFills: true });
  });

  it('keeps a newer stored switch when only the defaults are saved', () => {
    const update = inferenceParamsUpdate(
      { featureDefaults: { hour: 0 } },
      { featureDefaults: { hour: 1 }, useTrainingFills: false }
    );
    expect(
      buildInferenceParams({ useTrainingFills: true }, update?.featureDefaults, update?.useTrainingFills)
    ).toEqual({ featureDefaults: { hour: 1 }, useTrainingFills: true });
  });
});

describe('latestInferenceParams', () => {
  it('uses a fetched null value instead of restoring cached settings', () => {
    expect(latestInferenceParams({ inference_params: null }, { ratioBaselineColumn: 'cached' })).toBeNull();
  });

  it('falls back only when no fresh model was returned', () => {
    const cached = { ratioBaselineColumn: 'cached' };

    expect(latestInferenceParams(undefined, cached)).toEqual(cached);
  });
});

describe('mlModelSaveErrorMessage', () => {
  it('keeps the duplicate-name message specific to that error key', () => {
    expect(
      mlModelSaveErrorMessage(
        { response: { data: { error_key: 'ML_MODEL_NAME_EXISTS' } } },
        'create'
      )
    ).toBe('An ML model with this name already exists.');
  });

  it('surfaces artifact contract mismatch details from other 400 responses', () => {
    expect(
      mlModelSaveErrorMessage(
        {
          response: {
            data: {
              error_key: 'ML_MODEL_ARTIFACT_INVALID',
              error_detail: 'Registry fields do not match the model file. Missing features: lag_24.',
            },
          },
        },
        'update'
      )
    ).toBe('Registry fields do not match the model file. Missing features: lag_24.');
  });
});
