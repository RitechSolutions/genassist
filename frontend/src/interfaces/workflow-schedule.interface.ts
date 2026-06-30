export type WorkflowScheduleRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type ThreadIdMode = "per_run" | "fixed";

export interface WorkflowSchedule {
  id: string;
  name: string;
  agent_id: string;
  cron_schedule: string;
  is_active: boolean;
  input_data?: Record<string, unknown> | null;
  thread_id_mode: ThreadIdMode;
  fixed_thread_id?: string | null;
  last_run_at?: string | null;
  last_run_status?: WorkflowScheduleRunStatus | null;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowScheduleCreatePayload {
  name: string;
  agent_id: string;
  cron_schedule: string;
  is_active: boolean;
  input_data?: Record<string, unknown> | null;
  thread_id_mode: ThreadIdMode;
  fixed_thread_id?: string | null;
}

export type WorkflowScheduleUpdatePayload = Partial<WorkflowScheduleCreatePayload>;

export interface WorkflowScheduleRun {
  id: string;
  schedule_id: string;
  agent_id: string;
  workflow_id?: string | null;
  thread_id?: string | null;
  status: WorkflowScheduleRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  execution_output?: Record<string, unknown> | null;
  execution_id?: string | null;
  created_at?: string;
  updated_at?: string;
}