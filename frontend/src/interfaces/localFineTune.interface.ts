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
  [key: string]: unknown;
}

export interface CreateLocalFineTuneJobRequest {
  training_file: string;
  file_token: string;
  model: string;
  tool_training_mode?: string;
  cleanup_files?: boolean;
  hyperparameters: LocalFineTuneHyperparameters;
}

export type LocalFineTuneJobStatus =
  | "validating_files"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

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
