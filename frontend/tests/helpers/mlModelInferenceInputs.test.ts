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
});
