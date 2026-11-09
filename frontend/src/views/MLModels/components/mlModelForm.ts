import type { MLModel } from '@/interfaces/ml-model.interface';
import { extractErrorMessage } from '@/helpers/apiError';

type FeatureDefault = string | number | boolean;

export const usesTrainingFills = (params: MLModel['inference_params']): boolean =>
  params?.useTrainingFills === true;

/** Applies the given settings on top of existing; an omitted setting keeps its existing value. */
export const buildInferenceParams = (
  existing: MLModel['inference_params'],
  featureDefaults: Record<string, FeatureDefault> = existing?.featureDefaults ?? {},
  useTrainingFills: boolean = usesTrainingFills(existing)
): MLModel['inference_params'] => {
  const inferenceParams = { ...(existing ?? {}) };
  if (Object.keys(featureDefaults).length > 0) {
    inferenceParams.featureDefaults = featureDefaults;
  } else {
    delete inferenceParams.featureDefaults;
  }
  if (useTrainingFills) {
    inferenceParams.useTrainingFills = true;
  } else {
    delete inferenceParams.useTrainingFills;
  }
  return Object.keys(inferenceParams).length > 0 ? inferenceParams : null;
};

export const featureDefaultsChanged = (
  existing: MLModel['inference_params'],
  next: Record<string, FeatureDefault>
): boolean => {
  const current = existing?.featureDefaults ?? {};
  const currentNames = Object.keys(current);
  const nextNames = Object.keys(next);

  return (
    currentNames.length !== nextNames.length ||
    nextNames.some(
      (name) => !Object.prototype.hasOwnProperty.call(current, name) || !Object.is(current[name], next[name])
    )
  );
};

export interface InferenceParamsEdit {
  featureDefaults?: Record<string, FeatureDefault>;
  useTrainingFills?: boolean;
}

/**
 * Only the inference settings the form changed, or undefined when none did.
 * Unchanged settings are left out so saving never overwrites a newer stored
 * value with the form's copy.
 */
export const inferenceParamsUpdate = (
  existing: MLModel['inference_params'],
  next: Required<InferenceParamsEdit>
): InferenceParamsEdit | undefined => {
  const update: InferenceParamsEdit = {};
  if (featureDefaultsChanged(existing, next.featureDefaults)) {
    update.featureDefaults = next.featureDefaults;
  }
  if (usesTrainingFills(existing) !== next.useTrainingFills) {
    update.useTrainingFills = next.useTrainingFills;
  }
  return Object.keys(update).length > 0 ? update : undefined;
};

export const latestInferenceParams = (
  latestModel: Pick<MLModel, 'inference_params'> | null | undefined,
  cached: MLModel['inference_params']
): MLModel['inference_params'] => (latestModel ? latestModel.inference_params : cached);

/**
 * True when the server answered with a 4xx (other than a timeout), so the request
 * was refused and nothing was saved. Timeouts, network errors and 5xx answers are
 * not, because the server may still have saved.
 */
export const isRejectedRequest = (error: unknown): boolean => {
  const status = (error as { response?: { status?: unknown } } | null)?.response?.status;
  return typeof status === 'number' && status >= 400 && status < 500 && status !== 408;
};

export const mlModelSaveErrorMessage = (
  error: unknown,
  action: 'create' | 'update'
): string => {
  const errorKey = (
    error as { response?: { data?: { error_key?: unknown } } } | null
  )?.response?.data?.error_key;

  if (errorKey === 'ML_MODEL_NAME_EXISTS') {
    return 'An ML model with this name already exists.';
  }

  return extractErrorMessage(error, `Failed to ${action} ML model.`);
};
