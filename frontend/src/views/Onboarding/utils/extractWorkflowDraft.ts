export interface WorkflowDraftNode {
  uniqueId: string;
  node_name: string;
  next_node_id: string | null;
  function_of_node: string;
  [key: string]: unknown;
}

export interface WorkflowDraft {
  workflow: WorkflowDraftNode[];
  [key: string]: unknown;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const isWorkflowDraftNode = (value: unknown): value is WorkflowDraftNode => {
  if (!isRecord(value)) return false;
  if (typeof value.uniqueId !== "string" || value.uniqueId.trim().length === 0) return false;
  if (typeof value.node_name !== "string" || value.node_name.trim().length === 0) return false;
  if (typeof value.function_of_node !== "string" || value.function_of_node.trim().length === 0) return false;
  if (!(value.next_node_id === null || typeof value.next_node_id === "string")) return false;
  return true;
};

export const normalizeWorkflowDraft = (value: unknown): WorkflowDraft | null => {
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

const tryParseJson = (text: string): unknown | null => {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

const findCodeFenceBlocks = (text: string): string[] => {
  const blocks: string[] = [];
  const re = /```(?:json)?\s*([\s\S]*?)\s*```/gi;
  let match: RegExpExecArray | null = null;
  while ((match = re.exec(text))) {
    if (match[1]) blocks.push(match[1].trim());
  }
  return blocks;
};

const findTaggedBlocks = (text: string): string[] => {
  const blocks: string[] = [];
  const re = /<WORKFLOW_JSON>\s*([\s\S]*?)\s*<\/WORKFLOW_JSON>/gi;
  let match: RegExpExecArray | null = null;
  while ((match = re.exec(text))) {
    if (match[1]) blocks.push(match[1].trim());
  }
  return blocks;
};

const findBalancedJsonCandidate = (text: string, startIndex: number): string | null => {
  let braceDepth = 0;
  let bracketDepth = 0;
  let inString = false;
  let isEscaping = false;

  for (let i = startIndex; i < text.length; i += 1) {
    const ch = text[i];

    if (inString) {
      if (isEscaping) {
        isEscaping = false;
        continue;
      }
      if (ch === "\\") {
        isEscaping = true;
        continue;
      }
      if (ch === "\"") {
        inString = false;
      }
      continue;
    }

    if (ch === "\"") {
      inString = true;
      continue;
    }

    if (ch === "{") {
      braceDepth += 1;
      continue;
    }

    if (ch === "}") {
      braceDepth -= 1;
      if (braceDepth < 0) return null;
      if (braceDepth === 0 && bracketDepth === 0) {
        return text.slice(startIndex, i + 1);
      }
      continue;
    }

    if (ch === "[") {
      bracketDepth += 1;
      continue;
    }

    if (ch === "]") {
      bracketDepth -= 1;
      if (bracketDepth < 0) return null;
      if (braceDepth === 0 && bracketDepth === 0) {
        return text.slice(startIndex, i + 1);
      }
    }
  }

  return null;
};

export interface ExtractedWorkflowDraft {
  raw: string;
  parsed: WorkflowDraft;
}

// Extract the final workflow JSON from a free-form assistant reply.
export const extractWorkflowDraftFromText = (text: string): ExtractedWorkflowDraft | null => {
  const trimmed = text.trim();
  if (!trimmed) return null;

  const prioritizedCandidates = [...findCodeFenceBlocks(trimmed), ...findTaggedBlocks(trimmed)];
  for (const candidate of prioritizedCandidates) {
    const parsed = tryParseJson(candidate);
    const normalized = normalizeWorkflowDraft(parsed);
    if (normalized) return { raw: JSON.stringify(normalized), parsed: normalized };
  }

  for (let i = 0; i < trimmed.length; i += 1) {
    if (trimmed[i] !== "{" && trimmed[i] !== "[") continue;

    const candidate = findBalancedJsonCandidate(trimmed, i);
    if (!candidate) continue;

    const parsed = tryParseJson(candidate);
    const normalized = normalizeWorkflowDraft(parsed);
    if (normalized) return { raw: JSON.stringify(normalized), parsed: normalized };
  }

  return null;
};
