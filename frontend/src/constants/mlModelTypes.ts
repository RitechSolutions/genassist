export interface MLModelTypeOption {
  value: string;
  label: string;
}

// Keep in sync with backend/app/schemas/ml_model.py::ModelType
export const ML_MODEL_TYPES: MLModelTypeOption[] = [
  { value: "xgboost", label: "XGBoost" },
  { value: "random_forest", label: "Random Forest" },
  { value: "linear_regression", label: "Linear Regression" },
  { value: "logistic_regression", label: "Logistic Regression" },
  { value: "other", label: "Other" },
];

export const ML_MODEL_TYPE_LABELS: Record<string, string> = ML_MODEL_TYPES.reduce(
  (labels, { value, label }) => ({ ...labels, [value]: label }),
  {} as Record<string, string>
);

export function getMLModelTypeLabel(type: string): string {
  return ML_MODEL_TYPE_LABELS[type] ?? type;
}

export type MLModelTypeValue =
  | "xgboost"
  | "random_forest"
  | "linear_regression"
  | "logistic_regression"
  | "other";
