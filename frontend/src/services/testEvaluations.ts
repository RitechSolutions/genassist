import { apiRequest } from "@/config/api";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";

const BASE = "genagent/eval";

export type CreateTestEvaluationPayload = Omit<
  TestEvaluationConfig,
  "id" | "run_ids" | "created_at" | "updated_at"
>;

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
