import type { HyperparameterOptimizationMethod, OptimizationConfig } from "../../types/nodes";

/**
 * The search settings the dialog limits (TM-17). Keep in sync with SEARCH_LIMITS
 * in the backend's training_checks.py, which refuses the same values with 400.
 */
type LimitedField = "cvFolds" | "nIter" | "nTrials";

interface FieldLimit {
  label: string;
  min: number;
  max: number;
  /** The method that uses the setting; undefined means every search method. */
  method?: HyperparameterOptimizationMethod;
}

export const OPTIMIZATION_LIMITS: Record<LimitedField, FieldLimit> = {
  cvFolds: { label: "CV Folds", min: 2, max: 10 },
  nIter: { label: "Iterations", min: 1, max: 200, method: "random_search" },
  nTrials: { label: "Trials", min: 1, max: 200, method: "bayesian_optimization" },
};

export type OptimizationErrors = Partial<Record<LimitedField, string>>;

const isTemplated = (value: unknown) => typeof value === "string" && value.includes("{{");

/** Errors to show under the search settings; empty when they can be saved. */
export const optimizationConfigErrors = (
  method: HyperparameterOptimizationMethod,
  config: OptimizationConfig | undefined
): OptimizationErrors => {
  const errors: OptimizationErrors = {};
  if (method === "none" || !config) return errors;
  for (const [field, limit] of Object.entries(OPTIMIZATION_LIMITS) as [LimitedField, FieldLimit][]) {
    // Only fields the method shows: settings of other methods are dropped
    // when the method changes (withoutOtherMethodsSettings).
    if (limit.method && limit.method !== method) continue;
    const value: unknown = config[field];
    // Unset uses the default; a {{template}} is only known when the node runs.
    if (value === undefined || value === null || value === "" || isTemplated(value)) continue;
    const number = Number(value);
    if (!Number.isInteger(number) || number < limit.min || number > limit.max) {
      errors[field] = `${limit.label} must be a whole number from ${limit.min} to ${limit.max}.`;
    }
  }
  return errors;
};

// The settings only one search method uses.
const METHOD_SETTINGS: Partial<Record<HyperparameterOptimizationMethod, (keyof OptimizationConfig)[]>> = {
  random_search: ["nIter"],
  grid_search: ["gridPoints"],
  bayesian_optimization: ["nTrials", "timeoutSeconds"],
};

/**
 * The search settings without those of other methods. Their inputs are hidden,
 * so a bad value left in one couldn't be seen or fixed, yet the node still
 * refuses it when it runs.
 */
export const withoutOtherMethodsSettings = (
  method: HyperparameterOptimizationMethod,
  config: OptimizationConfig
): OptimizationConfig => {
  const kept = { ...config };
  for (const [owner, keys] of Object.entries(METHOD_SETTINGS)) {
    if (owner === method) continue;
    for (const key of keys ?? []) delete kept[key];
  }
  return kept;
};
