// Scoring metrics the hyperparameter search accepts.
// Keep in sync with backend/app/modules/workflow/engine/nodes/ml/training_checks.py.

export interface ScoringOption {
  value: string;
  label: string;
}

export const AUTO_SCORING = "auto";

/** Empty or "auto" (as typed into the old free-text field) both mean the default metric. */
export function isAutoScoring(value: string | undefined): boolean {
  return !value || value.trim().toLowerCase() === AUTO_SCORING;
}

export const CLASSIFICATION_SCORING: ScoringOption[] = [
  { value: "accuracy", label: "Accuracy" },
  { value: "balanced_accuracy", label: "Balanced accuracy" },
  { value: "f1_weighted", label: "F1 (weighted)" },
  { value: "f1_macro", label: "F1 (macro)" },
  { value: "precision_weighted", label: "Precision (weighted)" },
  { value: "recall_weighted", label: "Recall (weighted)" },
  { value: "roc_auc_ovr_weighted", label: "ROC AUC" },
  { value: "neg_log_loss", label: "Log loss" },
];

export const REGRESSION_SCORING: ScoringOption[] = [
  { value: "r2", label: "R²" },
  { value: "neg_root_mean_squared_error", label: "RMSE" },
  { value: "neg_mean_absolute_error", label: "MAE" },
  { value: "neg_mean_squared_error", label: "MSE" },
  { value: "neg_mean_absolute_percentage_error", label: "MAPE" },
];

export interface ScoringGroup {
  label: string;
  options: ScoringOption[];
}

/** Metric groups to offer for the node's task type ("auto" offers both). */
export function scoringGroupsFor(taskType: string | undefined): ScoringGroup[] {
  const classification = { label: "Classification", options: CLASSIFICATION_SCORING };
  const regression = { label: "Regression", options: REGRESSION_SCORING };
  if (taskType === "classification") return [classification];
  if (taskType === "regression") return [regression];
  return [classification, regression];
}

/** Label for a saved value, or undefined when the backend doesn't support it. */
export function scoringLabel(value: string): string | undefined {
  return [...CLASSIFICATION_SCORING, ...REGRESSION_SCORING].find((o) => o.value === value)?.label;
}

// Model types that train only one task, whatever Task Type says.
// Keep in sync with backend/app/modules/workflow/engine/nodes/ml/ml_utils.py
// (_REGRESSION_ONLY_MODEL_TYPES / _CLASSIFICATION_ONLY_MODEL_TYPES).
const REGRESSION_ONLY_MODEL_TYPES = new Set([
  "linear_regression",
  "ridge_regression",
  "lasso_regression",
  "elastic_net",
]);
const CLASSIFICATION_ONLY_MODEL_TYPES = new Set(["logistic_regression"]);

/** The one task a model type supports, or undefined when it supports both. */
export function onlyTaskTypeFor(modelType: string | undefined): "regression" | "classification" | undefined {
  if (modelType && REGRESSION_ONLY_MODEL_TYPES.has(modelType)) return "regression";
  if (modelType && CLASSIFICATION_ONLY_MODEL_TYPES.has(modelType)) return "classification";
  return undefined;
}

/** The task the search will score for, so the dropdown only offers metrics that fit. */
export function scoringTaskTypeFor(modelType: string | undefined, taskType: string | undefined) {
  if (modelType && REGRESSION_ONLY_MODEL_TYPES.has(modelType)) return "regression";
  if (modelType && CLASSIFICATION_ONLY_MODEL_TYPES.has(modelType)) return "classification";
  return taskType;
}
