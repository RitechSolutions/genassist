import { apiRequest, getApiUrl } from "@/config/api";
import {
  WorkflowTrigger,
  WorkflowTriggerDelivery,
  WorkflowTriggerProvisionPayload,
  WorkflowTriggerProvisionResponse,
  WorkflowTriggerRun,
  WorkflowTriggerRunStatus,
  WorkflowTriggerRunSummary,
  WorkflowTriggerSecret,
  WorkflowTriggerTestPayload,
  WorkflowTriggerUpdatePayload,
} from "@/interfaces/workflow-trigger.interface";

const BASE = "genagent/workflow-triggers";

/** Create the endpoint for a trigger node, or fetch the existing one (idempotent). */
export const provisionWorkflowTrigger = async (
  payload: WorkflowTriggerProvisionPayload
): Promise<WorkflowTriggerProvisionResponse> => {
  const base_url = payload.base_url ?? (await getApiUrl());
  const response = await apiRequest<WorkflowTriggerProvisionResponse>(
    "POST",
    `${BASE}/provision`,
    { ...payload, base_url } as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to provision the webhook endpoint");
  return response;
};

export const getWorkflowTriggersByAgent = async (
  agentId: string
): Promise<WorkflowTrigger[]> => {
  const data = await apiRequest<WorkflowTrigger[]>("GET", `${BASE}/by-agent/${agentId}`);
  return data || [];
};

export const getWorkflowTrigger = async (
  triggerId: string
): Promise<WorkflowTrigger | null> => {
  const data = await apiRequest<WorkflowTrigger>("GET", `${BASE}/${triggerId}`);
  return data ?? null;
};

export const updateWorkflowTrigger = async (
  triggerId: string,
  payload: WorkflowTriggerUpdatePayload
): Promise<WorkflowTrigger> => {
  const response = await apiRequest<WorkflowTrigger>(
    "PUT",
    `${BASE}/${triggerId}`,
    payload as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to update the webhook endpoint");
  return response;
};

export const deleteWorkflowTrigger = async (triggerId: string): Promise<void> => {
  await apiRequest("DELETE", `${BASE}/${triggerId}`);
};

export const rotateWorkflowTriggerSecret = async (
  triggerId: string
): Promise<WorkflowTriggerSecret> => {
  const response = await apiRequest<WorkflowTriggerSecret>(
    "POST",
    `${BASE}/${triggerId}/rotate-secret`
  );
  if (!response) throw new Error("Failed to rotate the secret");
  return response;
};

export const revealWorkflowTriggerSecret = async (
  triggerId: string
): Promise<WorkflowTriggerSecret> => {
  const response = await apiRequest<WorkflowTriggerSecret>(
    "GET",
    `${BASE}/${triggerId}/reveal-secret`
  );
  if (!response) throw new Error("Failed to reveal the secret");
  return response;
};

export const getWorkflowTriggerRuns = async (
  triggerId: string,
  options?: { status?: WorkflowTriggerRunStatus; limit?: number; offset?: number }
): Promise<WorkflowTriggerRunSummary[]> => {
  const params = new URLSearchParams();
  if (options?.status) params.set("run_status", options.status);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await apiRequest<WorkflowTriggerRunSummary[]>(
    "GET",
    `${BASE}/${triggerId}/runs${query}`
  );
  return data || [];
};

export const getWorkflowTriggerRun = async (
  triggerId: string,
  runId: string
): Promise<WorkflowTriggerRun | null> => {
  const data = await apiRequest<WorkflowTriggerRun>(
    "GET",
    `${BASE}/${triggerId}/runs/${runId}`
  );
  return data ?? null;
};

/** Queue a real run with a sample delivery (skips auth, rate limit and idempotency). */
export const testWorkflowTrigger = async (
  triggerId: string,
  payload: WorkflowTriggerTestPayload
): Promise<WorkflowTriggerDelivery> => {
  const response = await apiRequest<WorkflowTriggerDelivery>(
    "POST",
    `${BASE}/${triggerId}/test`,
    payload as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to send the test delivery");
  return response;
};
