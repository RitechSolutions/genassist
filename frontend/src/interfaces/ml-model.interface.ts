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
  // Extra inputs an inference caller must supply beyond `features` -
  // currently just the baseline column for a model trained on a ratio
  // target, since its raw value is needed to reconstruct the real-unit
  // prediction even though it was never one of the model's actual
  // training features.
  inference_params?: { ratioBaselineColumn?: string } | null;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface MLModelFormData extends Omit<MLModel, 'created_at' | 'updated_at'> {
  pkl_file_id?: string | null;
}

