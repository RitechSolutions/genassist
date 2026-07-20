import { apiRequest } from "@/config/api";
import {
  PaginatedEvaluations,
  StartedEvaluationRun,
  TestEvaluationConfig,
  WorkflowEvaluationSummary,
} from "@/interfaces/testEvaluation.interface";

export type {
  PaginatedEvaluations,
  StartedEvaluationRun,
  WorkflowEvaluationSummary,
} from "@/interfaces/testEvaluation.interface";

const BASE = "genagent/eval";

export type CreateTestEvaluationPayload = Omit<
  TestEvaluationConfig,
  "id" | "run_ids" | "created_at" | "updated_at"
>;

// Kept as a compatibility wrapper for GET /evaluations until that endpoint is
// formally deprecated, even though the UI no longer calls it directly.
export const listTestEvaluations = () =>
  apiRequest<TestEvaluationConfig[]>("GET", `${BASE}/evaluations`);

export const getTestEvaluationById = (id: string) =>
  apiRequest<TestEvaluationConfig>("GET", `${BASE}/evaluations/${id}`);

export const createTestEvaluation = (payload: CreateTestEvaluationPayload) =>
  apiRequest<TestEvaluationConfig>(
    "POST",
    `${BASE}/evaluations`,
    payload as unknown as Record<string, unknown>,
  );

export type UpdateTestEvaluationPayload = Partial<CreateTestEvaluationPayload>;

export const updateTestEvaluation = (
  id: string,
  payload: UpdateTestEvaluationPayload,
) =>
  apiRequest<TestEvaluationConfig>(
    "PATCH",
    `${BASE}/evaluations/${id}`,
    payload as unknown as Record<string, unknown>,
  );

export const deleteTestEvaluation = (id: string) =>
  apiRequest<void>("DELETE", `${BASE}/evaluations/${id}`);

export const appendRunToEvaluation = (evaluationId: string, runId: string) =>
  apiRequest<TestEvaluationConfig>(
    "POST",
    `${BASE}/evaluations/${evaluationId}/runs/${runId}`,
  );

export const runWorkflowEvaluations = (workflowId: string) =>
  apiRequest<StartedEvaluationRun[]>(
    "POST",
    `${BASE}/workflows/${workflowId}/evaluations/run`,
  );

export const getWorkflowEvaluationSummaries = () =>
  apiRequest<WorkflowEvaluationSummary[]>(
    "GET",
    `${BASE}/workflows/evaluation-summaries`,
  );

export const getWorkflowEvaluationsPage = (
  workflowId: string,
  params: { page: number; pageSize: number; search?: string },
) => {
  const query = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  });
  if (params.search?.trim()) query.set("search", params.search.trim());
  return apiRequest<PaginatedEvaluations>(
    "GET",
    `${BASE}/workflows/${workflowId}/evaluations?${query.toString()}`,
  );
};
