import type { MLModel } from '@/interfaces/ml-model.interface';

type InferenceInputs = Record<string, string>;
type ModelInputContract = Pick<MLModel, 'id' | 'features' | 'inference_params'>;

export const pruneInferenceInputs = (
  inferenceInputs: InferenceInputs,
  modelId: string,
  selectedModel: ModelInputContract | null
): { inferenceInputs: InferenceInputs; removedInputs: string[] } => {
  if (!selectedModel || selectedModel.id !== modelId) {
    return { inferenceInputs, removedInputs: [] };
  }

  const allowedInputs = new Set(selectedModel.features ?? []);
  const baselineColumn = selectedModel.inference_params?.ratioBaselineColumn;
  if (baselineColumn) allowedInputs.add(baselineColumn);

  const removedInputs = Object.keys(inferenceInputs).filter((key) => !allowedInputs.has(key));
  if (removedInputs.length === 0) {
    return { inferenceInputs, removedInputs };
  }

  return {
    inferenceInputs: Object.fromEntries(Object.entries(inferenceInputs).filter(([key]) => allowedInputs.has(key))),
    removedInputs,
  };
};
