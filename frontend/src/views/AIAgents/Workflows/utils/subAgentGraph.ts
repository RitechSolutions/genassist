/**
 * Used to reject invalid canvas wiring early with a clear message
 */

export const SUB_AGENT_SOURCE_HANDLE = "output_sub_agent";
export const SUB_AGENT_TARGET_HANDLE = "input_sub_agents";
export const MAX_DELEGATION_DEPTH = 3;
export const RESERVED_TOOL_NAMES = new Set(["finish_task", "return_to_parent"]);

export interface SubAgentGraphNode {
  id: string;
  type?: string | null;
  data?: { name?: string; mode?: string } | null;
}

export interface SubAgentGraphEdge {
  source?: string | null;
  target?: string | null;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface SubAgentConnection {
  source?: string | null;
  target?: string | null;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface ConnectionCheck {
  ok: boolean;
  reason?: string;
}

const TOOLS_TARGET_HANDLE = "input_tools";

const isUpper = (ch: string): boolean => ch !== ch.toLowerCase() && ch === ch.toUpperCase();

/** Character-for-character port of the backend ``to_snake_case`` so names collide identically */
export function toSnakeCase(value: string): string {
  const s = value ?? "";
  let final = "";
  for (let i = 0; i < s.length; i++) {
    const item = s[i];
    let nextWillUnderscore = false;
    if (i < s.length - 1) {
      const next = s[i + 1];
      nextWillUnderscore = next === "_" || next === " " || isUpper(next);
    }
    if ((item === " " || item === "_") && nextWillUnderscore) {
      continue;
    } else if (item === " " || item === "_") {
      final += "_";
    } else if (isUpper(item)) {
      final += "_" + item.toLowerCase();
    } else {
      final += item;
    }
  }
  if (final && final[0] === "_") final = final.slice(1);
  return final;
}

export function clampToolName(value: string): string {
  const folded = (value ?? "").normalize("NFKD").replace(/\p{M}+/gu, "");
  const clamped = toSnakeCase(folded).replace(/[^a-z0-9_]+/g, "_");
  return clamped.replace(/_+/g, "_").replace(/^_+|_+$/g, "");
}

/** Runtime name of the delegation tool the parent calls for this child */
export function delegationToolName(childName: string): string {
  return `request_task_${clampToolName(childName || "")}`;
}

/** Count of sub-agent children attached to this node's sub-agent port */
export function countSubAgentEdges(nodeId: string, edges: SubAgentGraphEdge[]): number {
  return edges.filter(
    (edge) => edge.target === nodeId && edge.targetHandle === SUB_AGENT_TARGET_HANDLE
  ).length;
}

export function connectedToolNodes<N extends SubAgentGraphNode>(
  nodeId: string,
  nodes: N[],
  edges: SubAgentGraphEdge[],
  toolTypes: string[]
): N[] {
  return nodes.filter(
    (node) =>
      toolTypes.includes(node.type ?? "") &&
      edges.some(
        (edge) =>
          edge.target === nodeId &&
          edge.source === node.id &&
          edge.targetHandle === TOOLS_TARGET_HANDLE
      )
  );
}

function buildDelegationMaps(edges: SubAgentGraphEdge[]): {
  childrenOf: Map<string, string[]>;
  parentsOf: Map<string, string[]>;
} {
  const childrenOf = new Map<string, string[]>();
  const parentsOf = new Map<string, string[]>();
  for (const edge of edges) {
    if (edge.targetHandle !== SUB_AGENT_TARGET_HANDLE) continue;
    const child = edge.source;
    const parent = edge.target;
    if (!child || !parent) continue;
    childrenOf.set(parent, [...(childrenOf.get(parent) ?? []), child]);
    parentsOf.set(child, [...(parentsOf.get(child) ?? []), parent]);
  }
  return { childrenOf, parentsOf };
}

// New edge = parent delegates to child
function reaches(childrenOf: Map<string, string[]>, from: string, goal: string): boolean {
  const stack = [from];
  const seen = new Set<string>();
  while (stack.length) {
    const node = stack.pop() as string;
    if (node === goal) return true;
    if (seen.has(node)) continue;
    seen.add(node);
    for (const child of childrenOf.get(node) ?? []) stack.push(child);
  }
  return false;
}

function depthOf(node: string, parentsOf: Map<string, string[]>, seen: Set<string>): number {
  const parents = parentsOf.get(node) ?? [];
  if (parents.length === 0 || seen.has(node)) return 1;
  seen.add(node);
  return 1 + Math.max(...parents.map((p) => depthOf(p, parentsOf, seen)));
}

function maxDepthAfterAdd(
  parentsOf: Map<string, string[]>,
  parent: string,
  child: string
): number {
  const augmented = new Map(parentsOf);
  augmented.set(child, [...(augmented.get(child) ?? []), parent]);
  let max = 0;
  for (const node of augmented.keys()) {
    max = Math.max(max, depthOf(node, augmented, new Set()));
  }
  return max;
}

/**
 * Validate a single new connection that touches a sub-agent port
 */
export function validateSubAgentConnection(
  connection: SubAgentConnection,
  nodes: SubAgentGraphNode[],
  edges: SubAgentGraphEdge[]
): ConnectionCheck {
  const { source, target, sourceHandle, targetHandle } = connection;
  const touchesSubAgent =
    sourceHandle === SUB_AGENT_SOURCE_HANDLE || targetHandle === SUB_AGENT_TARGET_HANDLE;
  if (!touchesSubAgent) return { ok: true };

  if (sourceHandle === SUB_AGENT_SOURCE_HANDLE && targetHandle !== SUB_AGENT_TARGET_HANDLE) {
    return { ok: false, reason: "A sub-agent only connects to an agent's sub-agent port." };
  }
  if (targetHandle === SUB_AGENT_TARGET_HANDLE && sourceHandle !== SUB_AGENT_SOURCE_HANDLE) {
    return { ok: false, reason: "Only a sub-agent can attach to the sub-agent port." };
  }
  if (!source || !target) return { ok: false, reason: "Invalid connection." };

  const child = source;
  const parent = target;
  if (child === parent) {
    return { ok: false, reason: "A sub-agent cannot attach to itself." };
  }

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const childNode = byId.get(child);
  const parentNode = byId.get(parent);

  if (childNode?.type !== "subAgentNode") {
    return { ok: false, reason: "Only a Sub-Agent node can feed a sub-agent port." };
  }
  if (parentNode?.type !== "agentNode" && parentNode?.type !== "subAgentNode") {
    return { ok: false, reason: "A sub-agent must attach to an agent or another sub-agent." };
  }

  const { childrenOf, parentsOf } = buildDelegationMaps(edges);

  if ((parentsOf.get(child)?.length ?? 0) >= 1) {
    return { ok: false, reason: "This sub-agent is already attached to a parent." };
  }
  if (reaches(childrenOf, child, parent)) {
    return { ok: false, reason: "That connection would create a delegation cycle." };
  }
  if (maxDepthAfterAdd(parentsOf, parent, child) > MAX_DELEGATION_DEPTH) {
    return { ok: false, reason: `Delegation depth cannot exceed ${MAX_DELEGATION_DEPTH}.` };
  }

  const childMode = childNode?.data?.mode ?? "single_turn";
  const parentMode = parentNode?.data?.mode ?? "single_turn";
  if (parentNode?.type === "subAgentNode" && parentMode === "task") {
    return { ok: false, reason: "A task sub-agent cannot have its own sub-agents." };
  }
  if ((childMode === "task" || childMode === "chat") && parentNode?.type === "subAgentNode") {
    return {
      ok: false,
      reason: "A task/chat sub-agent must attach to a top-level agent, not another sub-agent.",
    };
  }
  if (childMode === "task" && (childrenOf.get(child)?.length ?? 0) > 0) {
    return { ok: false, reason: "A task sub-agent cannot have its own sub-agents." };
  }

  const childName = childNode?.data?.name || child;
  const clampedName = clampToolName(childName);
  if (!clampedName) {
    return { ok: false, reason: "Sub-agent name must contain at least one letter or number." };
  }
  if (RESERVED_TOOL_NAMES.has(clampedName)) {
    return { ok: false, reason: "That sub-agent name is reserved (finish_task / return_to_parent)." };
  }
  const toolName = delegationToolName(childName);
  const siblingNames = new Set(
    (childrenOf.get(parent) ?? []).map((sib) =>
      delegationToolName(byId.get(sib)?.data?.name || sib)
    )
  );
  if (siblingNames.has(toolName)) {
    return { ok: false, reason: "Another sub-agent under this parent has the same name." };
  }

  const parentToolNames = new Set(
    edges
      .filter((edge) => edge.targetHandle === TOOLS_TARGET_HANDLE && edge.target === parent)
      .map((edge) => toSnakeCase(byId.get(edge.source ?? "")?.data?.name ?? ""))
  );
  if (parentToolNames.has(toolName)) {
    return { ok: false, reason: "A tool on this parent already uses this name." };
  }

  return { ok: true };
}
