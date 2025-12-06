export interface MLModel {
  id: string;
  name: string;
  description: string;
  model_type: 'xgboost' | 'random_forest' | 'linear_regression' | 'logistic_regression' | 'other';
  pkl_file?: string | null;
  features: string[];
  target_variable: string;
  inference_params?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface MLModelFormData extends Omit<MLModel, 'created_at' | 'updated_at'> {}

