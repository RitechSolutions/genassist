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
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface MLModelFormData extends Omit<MLModel, 'created_at' | 'updated_at'> {
  pkl_file_id?: string | null;
}

