import {
  tryParseJson,
  findCodeFenceBlocks,
  findBalancedJsonCandidate,
  isRecord,
} from "@/helpers/llmTextParser";

export interface WorkflowDraftNode {
  uniqueId: string;
  node_name: string;
  next_node_id?: string | null;
  function_of_node: string;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface WorkflowDraftEdge {
  from: string;
  to: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface WorkflowDraft {
  workflow: WorkflowDraftNode[];
  edges?: WorkflowDraftEdge[];
  [key: string]: unknown;
}

const isWorkflowDraftNode = (value: unknown): value is WorkflowDraftNode => {
  if (!isRecord(value)) return false;
  if (typeof value.uniqueId !== "string" || value.uniqueId.trim().length === 0) return false;
  if (typeof value.node_name !== "string" || value.node_name.trim().length === 0) return false;
  if (typeof value.function_of_node !== "string" || value.function_of_node.trim().length === 0) return false;
  // next_node_id is optional in the enhanced format (edges are used instead)
  if (value.next_node_id !== undefined && !(value.next_node_id === null || typeof value.next_node_id === "string")) return false;
  return true;
};

const normalizeWorkflowDraft = (value: unknown): WorkflowDraft | null => {
  // Supported shapes:
  // 1. { workflow: [...] }
  // 2. [ ... ] (array of workflow nodes)
  if (isRecord(value) && Array.isArray(value.workflow) && value.workflow.length > 0) {
    if (value.workflow.every(isWorkflowDraftNode)) {
      return value as WorkflowDraft;
    }
    return null;
  }

  if (Array.isArray(value) && value.length > 0 && value.every(isWorkflowDraftNode)) {
    return { workflow: value };
  }

  return null;
};

export const isWorkflowDraft = (value: unknown): value is WorkflowDraft => normalizeWorkflowDraft(value) !== null;

const findTaggedBlocks = (text: string): string[] => {
  const blocks: string[] = [];
  const re = /<WORKFLOW_JSON>\s*([\s\S]*?)\s*<\/WORKFLOW_JSON>/gi;
  let match: RegExpExecArray | null = null;
  while ((match = re.exec(text))) {
    if (match[1]) blocks.push(match[1].trim());
  }
  return blocks;
};

export interface ExtractedWorkflowDraft {
  raw: string;
  parsed: WorkflowDraft;
  isReady: boolean;
}

const WORKFLOW_READY_REGEX = /<WORKFLOW_READY\s*\/?>/i;

/** Check whether the agent signalled the workflow is finalized. */
export const hasWorkflowReadySignal = (text: string): boolean =>
  WORKFLOW_READY_REGEX.test(text);

/** Strip <WORKFLOW_JSON>, <WORKFLOW_READY/>, and code-fence blocks containing workflow drafts from display text. */
export const stripWorkflowTags = (text: string): string => {
  let cleaned = text;
  // Remove <WORKFLOW_JSON>...</WORKFLOW_JSON> blocks
  cleaned = cleaned.replace(/<WORKFLOW_JSON>\s*[\s\S]*?<\/WORKFLOW_JSON>/gi, "");
  // Remove <WORKFLOW_READY/> or <WORKFLOW_READY />
  cleaned = cleaned.replace(WORKFLOW_READY_REGEX, "");
  // Remove code-fence blocks that contain workflow draft JSON
  cleaned = cleaned.replace(/```(?:json)?\s*\{[\s\S]*?"workflow"[\s\S]*?\}\s*```/gi, "");
  return cleaned.trim();
};

// Extract the final workflow JSON from a free-form assistant reply.
export const extractWorkflowDraftFromText = (text: string): ExtractedWorkflowDraft | null => {
  const trimmed = text.trim();
  if (!trimmed) return null;

  const isReady = hasWorkflowReadySignal(trimmed);

  const prioritizedCandidates = [...findCodeFenceBlocks(trimmed), ...findTaggedBlocks(trimmed)];
  for (const candidate of prioritizedCandidates) {
    const parsed = tryParseJson(candidate);
    const normalized = normalizeWorkflowDraft(parsed);
    if (normalized) return { raw: JSON.stringify(normalized), parsed: normalized, isReady };
  }

  for (let i = 0; i < trimmed.length; i += 1) {
    if (trimmed[i] !== "{" && trimmed[i] !== "[") continue;

    const candidate = findBalancedJsonCandidate(trimmed, i);
    if (!candidate) continue;

    const parsed = tryParseJson(candidate);
    const normalized = normalizeWorkflowDraft(parsed);
    if (normalized) return { raw: JSON.stringify(normalized), parsed: normalized, isReady };
  }

  return null;
};
