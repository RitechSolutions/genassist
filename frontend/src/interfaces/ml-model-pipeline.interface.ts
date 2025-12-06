import { Workflow } from "./workflow.interface";

export interface TrainingPipelineConfig {
  id: string;
  model_id: string;
  workflow_id: string;
  workflow?: Workflow;
  is_default: boolean;
  cron_schedule?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PipelineRun {
  id: string;
  model_id: string;
  pipeline_config_id: string;
  workflow_id: string;
  workflow?: Workflow;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  error_message?: string | null;
  artifacts?: PipelineArtifact[];
  execution_output?: Record<string, unknown>;
  execution_id?: string;
  created_at?: string;
}

export interface PipelineArtifact {
  id: string;
  pipeline_run_id: string;
  artifact_type: 'model_file' | 'metrics' | 'logs' | 'data' | 'other';
  artifact_path: string;
  artifact_name: string;
  file_size?: number;
  created_at?: string;
}

export interface PipelineRunCreatePayload {
  model_id: string;
  pipeline_config_id: string;
  workflow_id: string;
}

export interface TrainingPipelineConfigCreatePayload {
  model_id: string;
  workflow_id: string;
  is_default?: boolean;
  cron_schedule?: string | null;
}

export interface TrainingPipelineConfigUpdatePayload {
  workflow_id?: string;
  is_default?: boolean;
  cron_schedule?: string | null;
}

