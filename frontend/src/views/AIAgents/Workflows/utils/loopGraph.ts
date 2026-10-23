/**
 * Loop wiring rules for the canvas, mirroring backend engine/loops.py.
 *
 * A Loop node owns a body: the nodes reachable from its "output_loop" handle. The last body node
 * connects back into the Loop's "input_loop" handle; that back-edge is the only cycle a workflow
 * may contain. Whatever runs after the loop hangs off "output_done".
 *
 * Pure (no React) so it can be unit-tested and reused by connect, reconnect and layout code.
 */

export const LOOP_NODE_TYPE = "loopNode";
export const LOOP_BODY_HANDLE = "output_loop";
export const LOOP_DONE_HANDLE = "output_done";
export const LOOP_BACK_HANDLE = "input_loop";

/** Pausing for user input cannot be resumed mid-loop, so these may not sit in a body. */
const NOT_ALLOWED_IN_LOOP = new Set(["humanInTheLoopNode"]);

/**
 * A body node can also pause through what is attached to it: a task/chat sub-agent hands the
 * conversation to the user, and a tool's sub-flow can reach a node that pauses.
 */
const SUB_AGENT_NODE_TYPE = "subAgentNode";
const INTERACTIVE_SUB_AGENT_MODES = new Set(["task", "chat"]);

const SUB_AGENT_SOURCE_HANDLE = "output_sub_agent";
/** Target handles through which a tool or a sub-agent is attached to an agent. */
const ATTACHMENT_HANDLES = new Set(["input_tools", "input_sub_agents"]);

export interface LoopGraphNode {
  id: string;
  type?: string;
  data?: { name?: string; mode?: string };
}

export interface LoopGraphEdge {
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface LoopConnection {
  source: string | null;
  target: string | null;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface LoopConnectionCheck {
  ok: boolean;
  reason?: string;
}

/** Whether an edge returns from a loop body into its Loop node. */
export const isLoopBackEdge = (edge: { targetHandle?: string | null }): boolean =>
  edge.targetHandle === LOOP_BACK_HANDLE;

/** Edges without the loop back-edges, i.e. an acyclic graph that layouts can order. */
export const withoutLoopBackEdges = <E extends { targetHandle?: string | null }>(edges: E[]): E[] =>
  edges.filter((edge) => !isLoopBackEdge(edge));

const handleTargets = (loopId: string, handle: string, edges: LoopGraphEdge[]): string[] =>
  edges
    .filter((edge) => edge.source === loopId && edge.sourceHandle === handle)
    .map((edge) => edge.target);

/** Nodes the flow reaches from `starts` without following a back-edge or entering `blocked`. */
const reachableFrom = (
  starts: string[],
  edges: LoopGraphEdge[],
  blocked: ReadonlySet<string> = new Set()
): Set<string> => {
  const outgoing = new Map<string, string[]>();
  for (const edge of edges) {
    if (isLoopBackEdge(edge) || edge.sourceHandle === SUB_AGENT_SOURCE_HANDLE) continue;
    const list = outgoing.get(edge.source);
    if (list) list.push(edge.target);
    else outgoing.set(edge.source, [edge.target]);
  }
  const seen = new Set<string>();
  const stack = starts.filter((id) => !blocked.has(id));
  while (stack.length) {
    const id = stack.pop()!;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const next of outgoing.get(id) ?? []) {
      if (!blocked.has(next) && !seen.has(next)) stack.push(next);
    }
  }
  return seen;
};

/** Every node that runs once per pass of this Loop (nested loops included). */
export const loopBody = (loopId: string, edges: LoopGraphEdge[]): Set<string> =>
  reachableFrom(handleTargets(loopId, LOOP_BODY_HANDLE, edges), edges, new Set([loopId]));

/**
 * A node that can pause the run during a pass, with the body node it is reached from (itself when
 * it sits in the body). Covers the body and everything its nodes run on demand: the tools and
 * sub-agents attached to them, and the tools' sub-flows.
 */
const pausingNodeInBody = (
  loopId: string,
  body: ReadonlySet<string>,
  byId: ReadonlyMap<string, LoopGraphNode>,
  edges: LoopGraphEdge[]
): { id: string; bodyNode: string } | null => {
  const owner = new Map<string, string>();
  const stack = [...body].sort().reverse().map((id) => ({ id, bodyNode: id }));
  while (stack.length) {
    const { id, bodyNode } = stack.pop()!;
    if (owner.has(id) || id === loopId) continue;
    owner.set(id, bodyNode);

    const node = byId.get(id);
    const interactive =
      node?.type === SUB_AGENT_NODE_TYPE && INTERACTIVE_SUB_AGENT_MODES.has(node.data?.mode ?? "");
    if (NOT_ALLOWED_IN_LOOP.has(node?.type ?? "") || interactive) return { id, bodyNode };

    for (const edge of edges) {
      const attaches = ATTACHMENT_HANDLES.has(edge.targetHandle ?? "");
      if (edge.target === id && attaches) stack.push({ id: edge.source, bodyNode });
      // Follow a tool's sub-flow, but not the edge that attaches it to an agent.
      if (edge.source === id && !body.has(id) && !attaches && !isLoopBackEdge(edge)) {
        stack.push({ id: edge.target, bodyNode });
      }
    }
  }
  return null;
};

/** The first wiring problem among the workflow's loops, or null when they are all runnable. */
export const loopTopologyError = (nodes: LoopGraphNode[], edges: LoopGraphEdge[]): string | null => {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const nameOf = (id: string) => byId.get(id)?.data?.name || id;

  for (const loop of nodes) {
    if (loop.type !== LOOP_NODE_TYPE) continue;
    const body = loopBody(loop.id, edges);

    for (const edge of edges) {
      if (edge.target === loop.id && isLoopBackEdge(edge) && !body.has(edge.source)) {
        return `Only a node that runs inside "${nameOf(loop.id)}" can connect to its Loop back input.`;
      }
    }
    const pausing = pausingNodeInBody(loop.id, body, byId, edges);
    if (pausing && pausing.id === pausing.bodyNode) {
      return `"${nameOf(pausing.id)}" pauses the workflow for user input, which is not supported inside a loop.`;
    }
    if (pausing) {
      return `"${nameOf(pausing.id)}" pauses the workflow for user input, which is not supported inside a loop, and "${nameOf(pausing.bodyNode)}" in the body of "${nameOf(loop.id)}" uses it.`;
    }
    const after = reachableFrom(handleTargets(loop.id, LOOP_DONE_HANDLE, edges), edges, new Set([loop.id]));
    for (const id of body) {
      if (after.has(id)) {
        return `"${nameOf(id)}" would run both inside "${nameOf(loop.id)}" and after it. Connect what follows the loop from Done only.`;
      }
    }
  }
  return null;
};

/**
 * Validate a new connection against the loop rules:
 *  - a connection may only close a cycle through a Loop's "Loop back" input;
 *  - it must not leave a loop wired in a way the engine cannot run.
 * Problems that already existed before the connection are not blamed on it.
 */
export const validateLoopConnection = (
  connection: LoopConnection,
  nodes: LoopGraphNode[],
  edges: LoopGraphEdge[]
): LoopConnectionCheck => {
  const { source, target, sourceHandle, targetHandle } = connection;
  if (!source || !target) return { ok: true };

  // Delegation edges are never part of the flow, so they cannot close a cycle; their own rules
  // are in subAgentGraph.ts. They can still attach a sub-agent that pauses to a loop body.
  const isDelegation = sourceHandle === SUB_AGENT_SOURCE_HANDLE;
  const isBackEdge = targetHandle === LOOP_BACK_HANDLE;
  if (!isBackEdge && !isDelegation && reachableFrom([target], edges).has(source)) {
    return {
      ok: false,
      reason: "That connection would create a cycle. To repeat steps, use a Loop node and connect back to its Loop back input.",
    };
  }

  const next = [...edges, { source, target, sourceHandle, targetHandle }];
  const problem = loopTopologyError(nodes, next);
  if (problem && problem !== loopTopologyError(nodes, edges)) {
    return { ok: false, reason: problem };
  }
  return { ok: true };
};

/** What a Loop publishes to its body on every pass (shown in the variable picker). */
export const LOOP_ITERATION_SAMPLE: Record<string, unknown> = {
  item: "current item",
  index: 0,
  iteration: 1,
  total: 3,
  is_first: true,
  is_last: false,
  previous: "result of the previous pass",
  input: "what the loop received",
  result: "result of this pass (once it has run)",
};

/** What a Loop publishes on its Done output once it has finished. */
export const LOOP_RESULT_SAMPLE: Record<string, unknown> = {
  results: ["result of each pass"],
  last: "result of the last pass",
  count: 3,
  iterations: 3,
  total: 3,
  total_items: 3,
  skipped: 0,
  failed: 0,
  errors: [],
  stopped_reason: "completed",
};

const SINGLE_VARIABLE = /^\s*\{\{\s*([^{}]+?)\s*\}\}\s*$/;

/** Read `a.b[0].c` out of nested data; undefined when any step is missing. */
const readPath = (data: unknown, path: string): unknown => {
  const keys = path.split(/[.[\]]/).filter(Boolean);
  let current: unknown = data;
  for (const key of keys) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
};

/**
 * What `item` looks like inside a loop, for the variable picker: when Items is a single variable
 * that points at a list in the data the Loop can read, the first element (or the first batch).
 * Undefined when that cannot be told at design time.
 */
export const loopItemSample = (
  itemsExpression: string | undefined,
  available: unknown,
  batchSize = 1
): unknown => {
  const variable = itemsExpression?.match(SINGLE_VARIABLE)?.[1];
  if (!variable) return undefined;
  let value = readPath(available, variable);
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return undefined;
    }
  }
  if (!Array.isArray(value) || value.length === 0) return undefined;
  return batchSize > 1 ? value.slice(0, batchSize) : value[0];
};
