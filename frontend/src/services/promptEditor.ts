import { apiRequest } from "@/config/api";
import type {
  CreatePromptVersionPayload,
  GoldSuiteLinkPayload,
  PromptConfig,
  PromptEvalRequestPayload,
  PromptEvalResponse,
  PromptOptimizeRequestPayload,
  PromptOptimizeResponse,
  PromptVersion,
} from "@/interfaces/promptEditor.interface";

const BASE = "genagent/prompt-editor";

function contextPath(workflowId: string, nodeId: string, promptField: string) {
  return `${workflowId}/${encodeURIComponent(nodeId)}/${encodeURIComponent(promptField)}`;
}

// ---- Versions ---------------------------------------------------------------

export const listPromptVersions = (
  workflowId: string,
  nodeId: string,
  promptField: string,
) =>
  apiRequest<PromptVersion[]>(
    "GET",
    `${BASE}/versions/${contextPath(workflowId, nodeId, promptField)}`,
  );

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

export const restorePromptVersion = (versionId: string) =>
  apiRequest<PromptVersion>("POST", `${BASE}/versions/${versionId}/restore`);

export const deletePromptVersion = (versionId: string) =>
  apiRequest<void>("DELETE", `${BASE}/versions/${versionId}`);

// ---- Config / Gold Suite ----------------------------------------------------

export const getPromptConfig = (
  workflowId: string,
  nodeId: string,
  promptField: string,
) =>
  apiRequest<PromptConfig>(
    "GET",
    `${BASE}/config/${contextPath(workflowId, nodeId, promptField)}`,
  );

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
