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

const SUB_AGENT_SOURCE_HANDLE = "output_sub_agent";

export interface LoopGraphNode {
  id: string;
  type?: string;
  data?: { name?: string };
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
    for (const id of body) {
      if (NOT_ALLOWED_IN_LOOP.has(byId.get(id)?.type ?? "")) {
        return `"${nameOf(id)}" pauses the workflow for user input, which is not supported inside a loop.`;
      }
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
  // Delegation edges have their own rules (see subAgentGraph.ts).
  if (sourceHandle === SUB_AGENT_SOURCE_HANDLE) return { ok: true };

  const isBackEdge = targetHandle === LOOP_BACK_HANDLE;
  if (!isBackEdge && reachableFrom([target], edges).has(source)) {
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
