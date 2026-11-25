export interface MLModel {
  id: string;
  name: string;
  description: string;
  model_type:
    | 'xgboost'
    | 'lightgbm'
    | 'catboost'
    | 'random_forest'
    | 'extra_trees'
    | 'gradient_boosting'
    | 'decision_tree'
    | 'linear_regression'
    | 'ridge_regression'
    | 'lasso_regression'
    | 'elastic_net'
    | 'logistic_regression'
    | 'svm'
    | 'knn'
    | 'neural_network';
  pkl_file?: string | null;
  pkl_file_id?: string | null;
  features: string[];
  target_variable: string;
  // Per-model inference configuration: ratioBaselineColumn is an additional
  // caller input, while featureDefaults contains deliberate fallback values
  // for missing model features. useTrainingFills lets the values saved at
  // training time (e.g. the median) fill any other missing input.
  inference_params?: {
    ratioBaselineColumn?: string;
    featureDefaults?: Record<string, string | number | boolean>;
    useTrainingFills?: boolean;
  } | null;
  // Validation metrics for the training run represented by this registry row.
  training_metrics?: Record<string, number | null> | null;
  // Notes from the model-file check on a create or update; never stored.
  registration_notices?: string[];
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface MLModelFormData extends Omit<MLModel, 'created_at' | 'updated_at' | 'training_metrics' | 'registration_notices'> {
  pkl_file_id?: string | null;
}
