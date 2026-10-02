import type { WorkflowScheduleRunStatus } from "./workflow-schedule.interface";

export type WorkflowTriggerMethod = "POST" | "GET";
export type WorkflowTriggerAuthMode = "bearer" | "hmac";
export type WorkflowTriggerRunStatus = WorkflowScheduleRunStatus;

/** One Webhook Trigger node endpoint (a `webhooks` row of type workflow_trigger). */
export interface WorkflowTrigger {
  id: string;
  agent_id: string;
  node_id: string;
  url: string;
  method: WorkflowTriggerMethod;
  auth_mode: WorkflowTriggerAuthMode;
  rate_limit_per_minute: number;
  is_active: boolean;
  last_run_status?: WorkflowTriggerRunStatus | null;
  last_run_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowTriggerProvisionPayload {
  agent_id: string;
  node_id: string;
  base_url?: string;
}

export interface WorkflowTriggerProvisionResponse extends WorkflowTrigger {
  /** Plaintext secret; only present when the endpoint was just created. */
  secret?: string | null;
  created: boolean;
}

export interface WorkflowTriggerUpdatePayload {
  method?: WorkflowTriggerMethod;
  auth_mode?: WorkflowTriggerAuthMode;
  rate_limit_per_minute?: number;
  is_active?: boolean;
}

export interface WorkflowTriggerSecret {
  secret: string;
  auth_mode: WorkflowTriggerAuthMode;
}

export interface WorkflowTriggerTestPayload {
  payload?: unknown;
  query?: Record<string, unknown>;
  headers?: Record<string, string>;
}

export interface WorkflowTriggerDelivery {
  run_id: string;
  status: WorkflowTriggerRunStatus;
  thread_id?: string | null;
  duplicate: boolean;
}

export interface WorkflowTriggerRunSummary {
  id: string;
  webhook_id: string;
  workflow_id?: string | null;
  thread_id?: string | null;
  status: WorkflowTriggerRunStatus;
  idempotency_key?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at?: string;
}

export interface WorkflowTriggerRun extends WorkflowTriggerRunSummary {
  agent_id: string;
  node_id: string;
  input_data?: Record<string, unknown> | null;
  execution_output?: Record<string, unknown> | null;
  execution_id?: string | null;
  updated_at?: string;
}
