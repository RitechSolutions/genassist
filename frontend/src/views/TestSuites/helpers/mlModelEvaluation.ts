import type { MLModel } from '@/interfaces/ml-model.interface';
import { getModelPipelineRuns } from '@/services/mlModelPipelines';

export interface RegressionMetrics {
  rmse?: number;
  mae?: number;
  r2_score?: number;
  mse?: number;
}

export interface ClassificationMetrics {
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
}

export type MLTaskType = 'regression' | 'classification';
export type ModelMetrics = RegressionMetrics & ClassificationMetrics;

export interface ModelEvaluationMetrics {
  taskType: MLTaskType | null;
  metrics: ModelMetrics;
}

export function extractTrainingMetrics(
  metricValues: Record<string, unknown> | null | undefined
): ModelEvaluationMetrics {
  const metrics = metricValues ?? {};

  if (typeof metrics.accuracy === 'number') {
    return {
      taskType: 'classification',
      metrics: {
        accuracy: metrics.accuracy,
        precision: typeof metrics.precision === 'number' ? metrics.precision : undefined,
        recall: typeof metrics.recall === 'number' ? metrics.recall : undefined,
        f1_score: typeof metrics.f1_score === 'number' ? metrics.f1_score : undefined,
      },
    };
  }

  if (typeof metrics.mse === 'number' || typeof metrics.r2_score === 'number') {
    const mse = typeof metrics.mse === 'number' ? metrics.mse : undefined;
    const rmse = typeof metrics.rmse === 'number' ? metrics.rmse : mse !== undefined ? Math.sqrt(mse) : undefined;
    return {
      taskType: 'regression',
      metrics: {
        mse,
        rmse,
        mae: typeof metrics.mae === 'number' ? metrics.mae : undefined,
        r2_score: typeof metrics.r2_score === 'number' ? metrics.r2_score : undefined,
      },
    };
  }

  return { taskType: null, metrics: {} };
}

function extractPipelineRunMetrics(executionOutput: Record<string, unknown> | undefined): ModelEvaluationMetrics {
  const output = (executionOutput?.output ?? {}) as Record<string, unknown>;
  return extractTrainingMetrics(output.metrics as Record<string, unknown> | undefined);
}

export async function getModelEvaluationMetrics(model: MLModel): Promise<ModelEvaluationMetrics> {
  const stored = extractTrainingMetrics(model.training_metrics);
  // Any stored value is final: an empty object means the model's current file has
  // no validation metrics, so an older run's metrics must not stand in for it.
  if (model.training_metrics != null) return stored;

  // Compatibility for models created before training_metrics was introduced.
  // New Train Model runs and promoted pipeline runs use the model field directly.
  const runs = await getModelPipelineRuns(model.id);
  const latestCompleted = runs.find((run) => run.status === 'completed');
  return latestCompleted ? extractPipelineRunMetrics(latestCompleted.execution_output) : stored;
}
