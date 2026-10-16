import { describe, expect, it } from 'vitest';

import {
  buildInferenceParams,
  featureDefaultsChanged,
  featureDefaultsUpdate,
  latestInferenceParams,
} from '@/views/MLModels/components/mlModelForm';

describe('buildInferenceParams', () => {
  it('applies changed defaults to the latest model settings', () => {
    expect(buildInferenceParams({ ratioBaselineColumn: 'latest' }, { hour: 1 })).toEqual({
      ratioBaselineColumn: 'latest',
      featureDefaults: { hour: 1 },
    });
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

describe('featureDefaultsUpdate', () => {
  it('omits inference params when the defaults field did not change', () => {
    expect(
      featureDefaultsUpdate({ ratioBaselineColumn: 'latest', featureDefaults: { hour: 0 } }, { hour: 0 })
    ).toBeUndefined();
  });

  it('returns only the changed defaults field', () => {
    expect(featureDefaultsUpdate({ ratioBaselineColumn: 'cached', featureDefaults: { hour: 0 } }, { hour: 1 })).toEqual(
      { featureDefaults: { hour: 1 } }
    );
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
