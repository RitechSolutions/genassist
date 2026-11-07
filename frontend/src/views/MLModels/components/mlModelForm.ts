import type { MLModel } from '@/interfaces/ml-model.interface';
import { extractErrorMessage } from '@/helpers/apiError';

type FeatureDefault = string | number | boolean;

const jsonStringList = (text: string): string[] | null => {
  try {
    const parsed: unknown = JSON.parse(text);
    // Names are kept exactly as quoted; featuresText relies on this to show any list.
    return Array.isArray(parsed) && parsed.every((item) => typeof item === 'string')
      ? parsed
      : null;
  } catch {
    return null;
  }
};

const readFeatures = (raw: string): { names: string[]; broken: boolean } => {
  const text = raw.trim();
  // A JSON array is read whole, so a quoted name may itself contain a comma.
  const json = text.startsWith('[') ? jsonStringList(text) : null;
  const names =
    json ??
    text
      .replace(/^\[([\s\S]*)\]$/, '$1')
      .split(',')
      .map((value) => {
        const name = value.trim();
        const quote = name[0];
        return name.length >= 2 && (quote === "'" || quote === '"') && name.endsWith(quote)
          ? name.slice(1, -1).trim()
          : name;
      });
  return {
    names: [...new Set(names.filter((name) => name.trim()))],
    // Outside a valid JSON list, a leftover bracket or double quote means a list
    // was mistyped (e.g. text after `]`), not that a name really contains it.
    broken: !json && names.some((name) => /["[\]]/.test(name)),
  };
};

/**
 * Reads the Features text box: plain comma-separated names, or a list copied from
 * Python/JSON such as `'x', 'y'` or `["x", "y"]`. Order is kept; blanks and repeated
 * names are dropped, as the tag input this box replaced did.
 */
export const parseModelFeatures = (raw: string): string[] => readFeatures(raw).names;

/** The validation message for a Features box that can't be read reliably, or null. */
export const featureListError = (raw: string): string | null =>
  readFeatures(raw).broken
    ? 'Check the brackets and quotes, or write plain names separated by commas.'
    : null;

// A name the plain comma form would change: commas, quotes, brackets, line breaks or
// outer spaces.
const needsQuoting = (name: string): boolean =>
  /[,'"[\]\r\n\t]/.test(name) || name !== name.trim();

/**
 * How stored features are shown in the Features box: `a, b, c`, or a JSON list when a
 * name would not survive that form, so parseModelFeatures reads back the same names.
 */
export const featuresText = (features: string[] | null | undefined): string => {
  const list = features ?? [];
  return list.some(needsQuoting) ? JSON.stringify(list) : list.join(', ');
};

/**
 * The features to save. While the box still shows the stored list, that list is sent
 * exactly as stored, so editing another field never rewrites the model's features.
 */
export const formFeatures = (raw: string, stored?: string[] | null): string[] =>
  stored && raw === featuresText(stored) ? [...stored] : parseModelFeatures(raw);

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
