import { apiRequest } from "@/config/api";
import {
  EvaluationBundle,
  EvaluationBundleSet,
  EvaluationImportPreview,
  EvaluationImportResult,
  EvaluationSetImportPreview,
  EvaluationSetImportResult,
} from "@/interfaces/evalBundle.interface";
import {
  EvaluationToolCatalog,
  PaginatedEvaluations,
  StartedEvaluationRun,
  TestEvaluationConfig,
  TestToolRuleResult,
  WorkflowEvaluationSummary,
} from "@/interfaces/testEvaluation.interface";
import { TestRun } from "@/interfaces/testSuite.interface";

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

export const runTestEvaluation = (
  evaluationId: string,
  targetWorkflowId?: string,
) =>
  apiRequest<TestRun>(
    "POST",
    `${BASE}/evaluations/${evaluationId}/run`,
    targetWorkflowId ? { target_workflow_id: targetWorkflowId } : {},
  );

export const runWorkflowEvaluations = (
  workflowId: string,
  targetWorkflowId?: string,
) =>
  apiRequest<StartedEvaluationRun[]>(
    "POST",
    `${BASE}/workflows/${workflowId}/evaluations/run`,
    targetWorkflowId ? { target_workflow_id: targetWorkflowId } : undefined,
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

export const getEvaluationToolCatalog = (workflowId: string) =>
  apiRequest<EvaluationToolCatalog>(
    "GET",
    `${BASE}/workflows/${workflowId}/evaluation-tool-catalog`,
  );

export const getToolRuleResults = (runId: string) =>
  apiRequest<TestToolRuleResult[]>(
    "GET",
    `${BASE}/runs/${runId}/tool-rule-results`,
  );

export const exportTestEvaluation = (id: string) =>
  apiRequest<EvaluationBundle>("GET", `${BASE}/evaluations/${id}/export`);

export interface EvaluationImportPayload {
  bundle: EvaluationBundle;
  target_workflow_id: string;
  existing_suite_id?: string;
  resolutions?: Record<string, string>;
  drop_unresolved_rules?: boolean;
}

export const previewEvaluationImport = (
  payload: Pick<EvaluationImportPayload, "bundle" | "target_workflow_id">,
) =>
  apiRequest<EvaluationImportPreview>(
    "POST",
    `${BASE}/evaluations/import/preview`,
    payload as unknown as Record<string, unknown>,
  );

export const importEvaluation = (payload: EvaluationImportPayload) =>
  apiRequest<EvaluationImportResult>(
    "POST",
    `${BASE}/evaluations/import`,
    payload as unknown as Record<string, unknown>,
  );

export const exportWorkflowEvaluations = (workflowId: string) =>
  apiRequest<EvaluationBundleSet>(
    "GET",
    `${BASE}/workflows/${workflowId}/evaluations/export`,
  );

export interface EvaluationSetImportPayload {
  bundle_set: EvaluationBundleSet;
  target_workflow_id: string;
  include?: number[];
  resolutions?: Record<string, string>;
  drop_unresolved_rules?: boolean;
  skip_existing?: boolean;
}

export const previewEvaluationSetImport = (
  payload: Pick<EvaluationSetImportPayload, "bundle_set" | "target_workflow_id">,
) =>
  apiRequest<EvaluationSetImportPreview>(
    "POST",
    `${BASE}/evaluations/import-set/preview`,
    payload as unknown as Record<string, unknown>,
  );

export const importEvaluationSet = (payload: EvaluationSetImportPayload) =>
  apiRequest<EvaluationSetImportResult>(
    "POST",
    `${BASE}/evaluations/import-set`,
    payload as unknown as Record<string, unknown>,
  );
