import type { MLModel } from '@/interfaces/ml-model.interface';

type FeatureDefault = string | number | boolean;

export const buildInferenceParams = (
  existing: MLModel['inference_params'],
  featureDefaults: Record<string, FeatureDefault>
): MLModel['inference_params'] => {
  const inferenceParams = { ...(existing ?? {}) };
  if (Object.keys(featureDefaults).length > 0) {
    inferenceParams.featureDefaults = featureDefaults;
  } else {
    delete inferenceParams.featureDefaults;
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

export const featureDefaultsUpdate = (
  existing: MLModel['inference_params'],
  next: Record<string, FeatureDefault>
): { featureDefaults: Record<string, FeatureDefault> } | undefined =>
  featureDefaultsChanged(existing, next) ? { featureDefaults: next } : undefined;

export const latestInferenceParams = (
  latestModel: Pick<MLModel, 'inference_params'> | null | undefined,
  cached: MLModel['inference_params']
): MLModel['inference_params'] => (latestModel ? latestModel.inference_params : cached);
