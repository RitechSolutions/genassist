export interface LocalFineTuneHyperparameters {
  num_train_epochs?: number;
  per_device_train_batch_size?: number;
  gradient_accumulation_steps?: number;
  learning_rate?: number;
  lora_r?: number;
  lora_alpha?: number;
  max_seq_length?: number;
  logging_steps?: number;
  save_steps?: number;
  eval_steps?: number;
  warmup_steps?: number;
  fp16?: boolean;
  bf16?: boolean;
  [key: string]: unknown;
}

export interface LocalFineTuneSupportedModel {
  id: string;
  name: string;
}

export interface CreateLocalFineTuneJobRequest {
  training_file: string;
  file_token: string;
  model_id: string;
  suffix?: string | null;
  tool_training_mode?: string;
  remote_files: boolean;
  cleanup_files?: boolean;
  hyperparameters: LocalFineTuneHyperparameters;
}

export type LocalFineTuneJobStatus =
  | "validating_files"
  | "queued"
  | "running"
  | "saving_model"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface LocalFineTuneJobEvent {
  job_id: string;
  level: string;
  message: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}

export interface LocalFineTuneJobError {
  message?: string;
  code?: string;
}

export interface LocalFineTuneJob {
  id: string;
  status: LocalFineTuneJobStatus | string;
  created_at?: string;
  model: string;
  training_file?: string;
  validation_file?: string | null;
  hyperparameters?: LocalFineTuneHyperparameters & Record<string, unknown>;
  suffix?: string | null;
  finished_at?: string | null;
  fine_tuned_model?: string | null;
  error?: LocalFineTuneJobError | null;
  [key: string]: unknown;
}

export type LocalFineTuneDeploymentStatus = "starting" | "running" | "failed" | "stopped";

export interface CreateDeploymentRequest {
  deployment_id: string;
  job_id: string;
  gpu_id?: number | null;
  max_model_len?: number | null;
  gpu_memory_utilization?: number;
  dtype?: string;
}

export interface LocalFineTuneDeployment {
  id: string;
  status: LocalFineTuneDeploymentStatus | string;
  model_path: string;
  port: number;
  gpu_id?: number | null;
  api_url: string;
  created_at?: string;
  process_id?: number | null;
  error_message?: string | null;
  max_model_len?: number | null;
}

export interface LocalFineTuneDeploymentHealth {
  deployment_id: string;
  status: "healthy" | "unhealthy" | string;
  api_url: string;
  details: string;
}

export interface DeploymentStopResponse {
  id: string;
  status: string;
  message: string;
}
