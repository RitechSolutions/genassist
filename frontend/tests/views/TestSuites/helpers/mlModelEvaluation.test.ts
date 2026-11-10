import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MLModel } from '@/interfaces/ml-model.interface';
import { getModelPipelineRuns } from '@/services/mlModelPipelines';
import { extractTrainingMetrics, getModelEvaluationMetrics } from '@/views/TestSuites/helpers/mlModelEvaluation';

vi.mock('@/services/mlModelPipelines', () => ({
  getModelPipelineRuns: vi.fn(),
}));

const mockedGetModelPipelineRuns = vi.mocked(getModelPipelineRuns);

function model(trainingMetrics: MLModel['training_metrics']): MLModel {
  return {
    id: 'model-1',
    name: 'forecast',
    description: 'Forecast model',
    model_type: 'linear_regression',
    features: ['hour'],
    target_variable: 'revenue',
    training_metrics: trainingMetrics,
  };
}

describe('extractTrainingMetrics', () => {
  it('recognizes classification metrics', () => {
    expect(extractTrainingMetrics({ accuracy: 0.9, precision: 0.8, f1_score: 0.85 })).toEqual({
      taskType: 'classification',
      metrics: {
        accuracy: 0.9,
        precision: 0.8,
        recall: undefined,
        f1_score: 0.85,
      },
    });
  });

  it('recognizes regression metrics and derives RMSE when needed', () => {
    expect(extractTrainingMetrics({ mse: 0.25, mae: 0.4, r2_score: 0.8 })).toEqual({
      taskType: 'regression',
      metrics: { mse: 0.25, rmse: 0.5, mae: 0.4, r2_score: 0.8 },
    });
  });
});

describe('getModelEvaluationMetrics', () => {
  beforeEach(() => {
    mockedGetModelPipelineRuns.mockReset();
  });

  it('uses Train Model metrics without requiring a pipeline run', async () => {
    const result = await getModelEvaluationMetrics(
      model({ accuracy: 0.92, precision: 0.9, recall: 0.89, f1_score: 0.91 })
    );

    expect(result.taskType).toBe('classification');
    expect(result.metrics.f1_score).toBe(0.91);
    expect(mockedGetModelPipelineRuns).not.toHaveBeenCalled();
  });

  it('falls back to the latest completed run for legacy models', async () => {
    mockedGetModelPipelineRuns.mockResolvedValue([
      {
        id: 'run-1',
        model_id: 'model-1',
        pipeline_config_id: 'config-1',
        workflow_id: 'workflow-1',
        status: 'completed',
        execution_output: {
          output: { metrics: { mse: 1, mae: 0.8, r2_score: 0.75 } },
        },
      },
    ]);

    const result = await getModelEvaluationMetrics(model(null));

    expect(result).toEqual({
      taskType: 'regression',
      metrics: { mse: 1, rmse: 1, mae: 0.8, r2_score: 0.75 },
    });
  });

  it('does not borrow an older run for a model stored without metrics', async () => {
    const result = await getModelEvaluationMetrics(model({}));

    expect(result).toEqual({ taskType: null, metrics: {} });
    expect(mockedGetModelPipelineRuns).not.toHaveBeenCalled();
  });
});
