export interface MLModelTypeOption {
  value: string;
  label: string;
}

// Keep in sync with backend/app/modules/workflow/engine/nodes/ml/train_model_node.py::valid_model_types.
export const ML_MODEL_TYPES: MLModelTypeOption[] = [
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

export const ML_MODEL_TYPE_LABELS: Record<string, string> = ML_MODEL_TYPES.reduce(
  (labels, { value, label }) => ({ ...labels, [value]: label }),
  {} as Record<string, string>
);

export function getMLModelTypeLabel(type: string): string {
  return ML_MODEL_TYPE_LABELS[type] ?? type;
}

export type MLModelTypeValue =
  | "xgboost"
  | "lightgbm"
  | "catboost"
  | "random_forest"
  | "extra_trees"
  | "gradient_boosting"
  | "decision_tree"
  | "linear_regression"
  | "ridge_regression"
  | "lasso_regression"
  | "elastic_net"
  | "logistic_regression"
  | "svm"
  | "knn"
  | "neural_network";