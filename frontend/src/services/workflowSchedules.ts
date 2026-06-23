import { apiRequest } from "@/config/api";
import {
  WorkflowSchedule,
  WorkflowScheduleCreatePayload,
  WorkflowScheduleUpdatePayload,
  WorkflowScheduleRun,
  WorkflowScheduleRunStatus,
} from "@/interfaces/workflow-schedule.interface";

const BASE = "genagent/workflow-schedules";

export const getWorkflowSchedules = async (
  isActive?: boolean
): Promise<WorkflowSchedule[]> => {
  const query =
    isActive === undefined ? "" : `?is_active=${String(isActive)}`;
  const data = await apiRequest<WorkflowSchedule[]>("GET", `${BASE}${query}`);
  return data || [];
};

export const getWorkflowSchedule = async (
  scheduleId: string
): Promise<WorkflowSchedule | null> => {
  const data = await apiRequest<WorkflowSchedule>("GET", `${BASE}/${scheduleId}`);
  return data ?? null;
};

export const createWorkflowSchedule = async (
  payload: WorkflowScheduleCreatePayload
): Promise<WorkflowSchedule> => {
  const response = await apiRequest<WorkflowSchedule>(
    "POST",
    BASE,
    payload as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to create workflow schedule");
  return response;
};

export const updateWorkflowSchedule = async (
  scheduleId: string,
  payload: WorkflowScheduleUpdatePayload
): Promise<WorkflowSchedule> => {
  const response = await apiRequest<WorkflowSchedule>(
    "PUT",
    `${BASE}/${scheduleId}`,
    payload as unknown as Record<string, unknown>
  );
  if (!response) throw new Error("Failed to update workflow schedule");
  return response;
};

export const deleteWorkflowSchedule = async (
  scheduleId: string
): Promise<void> => {
  await apiRequest("DELETE", `${BASE}/${scheduleId}`);
};

export const getWorkflowScheduleRuns = async (
  scheduleId: string,
  options?: { status?: WorkflowScheduleRunStatus; limit?: number; offset?: number }
): Promise<WorkflowScheduleRun[]> => {
  const params = new URLSearchParams();
  if (options?.status) params.set("run_status", options.status);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  const query = params.toString() ? `?${params.toString()}` : "";
  const data = await apiRequest<WorkflowScheduleRun[]>(
    "GET",
    `${BASE}/${scheduleId}/runs${query}`
  );
  return data || [];
};

export const runWorkflowScheduleNow = async (
  scheduleId: string
): Promise<WorkflowScheduleRun> => {
  const response = await apiRequest<WorkflowScheduleRun>(
    "POST",
    `${BASE}/${scheduleId}/run-now`
  );
  if (!response) throw new Error("Failed to trigger workflow schedule run");
  return response;
};