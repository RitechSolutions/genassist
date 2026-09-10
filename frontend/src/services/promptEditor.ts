import { apiRequest } from "@/config/api";
import type {
  CreatePromptVersionPayload,
  GoldSuiteLinkPayload,
  PromptConfig,
  PromptEvalRequestPayload,
  PromptEvalResponse,
  PromptHistory,
  PromptOptimizeRequestPayload,
  PromptOptimizeResponse,
  PromptVersion,
} from "@/interfaces/promptEditor.interface";

const BASE = "genagent/prompt-editor";

function contextPath(workflowId: string, nodeId: string, promptField: string) {
  return `${workflowId}/${encodeURIComponent(nodeId)}/${encodeURIComponent(promptField)}`;
}

// ---- History ----------------------------------------------------------------

export const getPromptHistory = (
  workflowId: string,
  nodeId: string,
  promptField: string,
) =>
  apiRequest<PromptHistory>(
    "GET",
    `${BASE}/history/${contextPath(workflowId, nodeId, promptField)}`,
  );

// ---- Versions ---------------------------------------------------------------

export const createPromptVersion = (
  workflowId: string,
  nodeId: string,
  promptField: string,
  payload: CreatePromptVersionPayload,
) =>
  apiRequest<PromptVersion>(
    "POST",
    `${BASE}/versions/${contextPath(workflowId, nodeId, promptField)}`,
    payload as unknown as Record<string, unknown>,
  );

export const deletePromptVersion = async (versionId: string): Promise<void> => {
  // apiRequest: 403 returns null (forbidden), 204 returns "" (no content)
  const result = await apiRequest<void>("DELETE", `${BASE}/versions/${versionId}`);
  if (result === null) throw new Error("Not allowed to delete this prompt version");
};

// ---- Config / Gold Suite ----------------------------------------------------

export const linkGoldSuite = (
  workflowId: string,
  nodeId: string,
  promptField: string,
  payload: GoldSuiteLinkPayload,
) =>
  apiRequest<PromptConfig>(
    "PUT",
    `${BASE}/config/${contextPath(workflowId, nodeId, promptField)}/gold-suite`,
    payload as unknown as Record<string, unknown>,
  );

// ---- Evaluate & Optimize ----------------------------------------------------

export const evaluatePrompt = (
  workflowId: string,
  nodeId: string,
  promptField: string,
  payload: PromptEvalRequestPayload,
) =>
  apiRequest<PromptEvalResponse>(
    "POST",
    `${BASE}/evaluate/${contextPath(workflowId, nodeId, promptField)}`,
    payload as unknown as Record<string, unknown>,
  );

export const optimizePrompt = (
  workflowId: string,
  nodeId: string,
  promptField: string,
  payload: PromptOptimizeRequestPayload,
) =>
  apiRequest<PromptOptimizeResponse>(
    "POST",
    `${BASE}/optimize/${contextPath(workflowId, nodeId, promptField)}`,
    payload as unknown as Record<string, unknown>,
  );
