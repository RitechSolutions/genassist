import { MLModel } from "@/interfaces/ml-model.interface";

export type MLModelType = MLModel["model_type"];

/**
 * Single source of truth for the model-type vocabulary. The create/edit dialog,
 * the list filter and every label read from here so a new algorithm only has to
 * be added in one place.
 */
export const MODEL_TYPE_OPTIONS: ReadonlyArray<{
  value: MLModelType;
  label: string;
}> = [
  { value: "xgboost", label: "XGBoost" },
  { value: "random_forest", label: "Random Forest" },
  { value: "linear_regression", label: "Linear Regression" },
  { value: "logistic_regression", label: "Logistic Regression" },
  { value: "other", label: "Other" },
];

const LABEL_BY_VALUE = new Map<string, string>(
  MODEL_TYPE_OPTIONS.map((option) => [option.value, option.label])
);

/** Human label for a stored model type, falling back to the raw value. */
export function modelTypeLabel(type: string | null | undefined): string {
  if (!type) return "—";
  return LABEL_BY_VALUE.get(type) ?? type;
}
