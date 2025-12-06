export interface FineTuneHyperparameters {
  n_epochs: number;
  batch_size: number;
}

export interface CreateFineTuneJobRequest {
  training_file: string;
  model: string;
  validation_file: string;
  suffix: string;
  hyperparameters: FineTuneHyperparameters;
}

export type FineTuneJobStatus =
  | "validating_files"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface FineTuneJob {
  id: string;
  model: string;
  status: FineTuneJobStatus | string;
  created_at?: number | string;
  updated_at?: number | string;
  training_file?: string;
  validation_file?: string;
  fine_tuned_model?: string | null;
  openai_job_id?: string;
  suffix?: string;
  [key: string]: unknown;
}

export interface OpenAIFileItem {
  id: string;
  filename?: string;
  bytes?: number;
  purpose?: string;
  created_at?: number | string;
  status?: string;
  [key: string]: unknown;
}

export interface PaginatedResponse<T> {
  object?: string;
  data: T[];
  has_more?: boolean;
}