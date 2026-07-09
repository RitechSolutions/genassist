export type BedrockJobStatus =
  | "InProgress"
  | "Completed"
  | "Failed"
  | "Stopping"
  | "Stopped";

export type BedrockDeploymentStatus =
  | "NotDeployed"
  | "Creating"
  | "Active"
  | "Failed";

export interface CreateBedrockFineTuneJobRequest {
  training_data_s3_uri: string;
  base_model_id: string;
  validation_data_s3_uri?: string;
  hyperparameters?: Record<string, unknown>;
  suffix?: string;
}

/** Response from `POST /bedrock/upload`. */
export interface BedrockUploadResult {
  s3_uri: string;
  filename: string;
  bytes: number;
}

/** Response from `POST /bedrock/fine-tuning/generate-from-conversations` when `upload_to_s3` is true. */
export interface BedrockGenerateUploadResult {
  s3_uri: string;
  bytes: number;
}

export interface BedrockFineTuneJob {
  id: string;
  job_arn?: string;
  job_name?: string;
  base_model_id: string;
  custom_model_name?: string;
  suffix?: string | null;
  hyperparameters?: Record<string, unknown> | null;
  region?: string;
  training_data_s3_uri?: string;
  validation_data_s3_uri?: string | null;
  output_s3_uri?: string | null;
  status: BedrockJobStatus | string;
  custom_model_arn?: string | null;
  deployment_status?: BedrockDeploymentStatus | string;
  deployment_arn?: string | null;
  finished_at?: number | string | null;
  last_synced_at?: number | string | null;
  trained_tokens?: number | null;
  metrics?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at?: number | string;
  updated_at?: number | string;
  [key: string]: unknown;
}
