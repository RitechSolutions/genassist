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
  { value: "lightgbm", label: "LightGBM" },
  { value: "catboost", label: "CatBoost" },
  { value: "random_forest", label: "Random Forest" },
  { value: "extra_trees", label: "Extra Trees" },
  { value: "gradient_boosting", label: "Gradient Boosting" },
  { value: "decision_tree", label: "Decision Tree" },
  { value: "linear_regression", label: "Linear Regression" },
  { value: "ridge_regression", label: "Ridge Regression" },
  { value: "lasso_regression", label: "Lasso Regression" },
  { value: "elastic_net", label: "Elastic Net" },
  { value: "logistic_regression", label: "Logistic Regression" },
  { value: "svm", label: "Support Vector Machine" },
  { value: "knn", label: "K-Nearest Neighbors" },
  { value: "neural_network", label: "Neural Network" },
];

const LABEL_BY_VALUE = new Map<string, string>(
  MODEL_TYPE_OPTIONS.map((option) => [option.value, option.label])
);

/** Human label for a stored model type, falling back to the raw value. */
export function modelTypeLabel(type: string | null | undefined): string {
  if (!type) return "—";
  return LABEL_BY_VALUE.get(type) ?? type;
}
