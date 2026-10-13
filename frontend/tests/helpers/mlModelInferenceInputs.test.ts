import { describe, expect, it } from 'vitest';
import { pruneInferenceInputs } from '@/views/AIAgents/Workflows/nodeDialogs/mlModelInferenceInputs';

const model = {
  id: 'model-x',
  features: ['hour', 'lag_24'],
  inference_params: { ratioBaselineColumn: 'baseline' },
};

describe('pruneInferenceInputs', () => {
  it('does not prune inputs for a different selected model', () => {
    const inferenceInputs = { hour: '8', lag_24: '5' };

    const result = pruneInferenceInputs(inferenceInputs, 'model-y', model);

    expect(result).toEqual({ inferenceInputs, removedInputs: [] });
  });

  it('removes only inputs outside the matching model contract', () => {
    const result = pruneInferenceInputs({ hour: '8', lag_24: '5', baseline: '10', obsolete: '1' }, 'model-x', model);

    expect(result).toEqual({
      inferenceInputs: { hour: '8', lag_24: '5', baseline: '10' },
      removedInputs: ['obsolete'],
    });
  });

  it('preserves saved inputs when a legacy model has no inference params', () => {
    const inferenceInputs = { hour: '8', revenue_prev: '100' };
    const legacyModel = {
      id: 'model-x',
      features: ['hour'],
      inference_params: null,
    };

    const result = pruneInferenceInputs(inferenceInputs, 'model-x', legacyModel);

    expect(result).toEqual({ inferenceInputs, removedInputs: [] });
  });

  it('preserves saved inputs when a legacy model has empty inference params', () => {
    const inferenceInputs = { hour: '8', revenue_prev: '100' };
    const legacyModel = {
      id: 'model-x',
      features: ['hour'],
      inference_params: {},
    };

    const result = pruneInferenceInputs(inferenceInputs, 'model-x', legacyModel);

    expect(result).toEqual({ inferenceInputs, removedInputs: [] });
  });

  it('preserves a legacy baseline after feature defaults are saved', () => {
    const inferenceInputs = { hour: '8', revenue_prev: '100' };
    const legacyModel = {
      id: 'model-x',
      features: ['hour'],
      inference_params: { featureDefaults: { hour: 12 } },
    };

    const result = pruneInferenceInputs(inferenceInputs, 'model-x', legacyModel);

    expect(result).toEqual({ inferenceInputs, removedInputs: [] });
  });
});
