import type { Edge, Node } from "reactflow";
import type { NodeExecutionResult } from "../context/WorkflowExecutionContext";
import type { TrainDataSourceNodeData } from "../types/nodes";

/**
 * Works out which file a training node's Analyze / step preview should read.
 *
 * Kept free of React and the node registry so it can be unit-tested.
 */

export const SOURCE_DATA_PATH = "{{source.data_path}}";
const TRAIN_DATA_SOURCE_NODE_TYPE = "trainDataSourceNode";
const TRAIN_DATA_SOURCE_LABEL = "Train Data Source";

export const hasUnfilledPlaceholder = (url: string): boolean => /{{[^}]*}}/.test(url);

/** The Train Data Source settings that decide which data it produces. */
const trainingSourceSettingsKey = (
  nodeType: string | undefined,
  data: unknown
): string | undefined => {
  if (nodeType !== TRAIN_DATA_SOURCE_NODE_TYPE) return undefined;
  const d = (data ?? {}) as Partial<TrainDataSourceNodeData>;
  return JSON.stringify([
    d.sourceType ?? "",
    d.dataSourceId ?? "",
    d.query ?? "",
    d.csvFileId ?? "",
    d.csvFilePath ?? "",
    d.csvFileUrl ?? "",
    d.sheetName ?? "",
  ]);
};

type GraphNode = Pick<Node, "id" | "type" | "data">;
type GraphEdge = Pick<Edge, "source" | "target">;

/**
 * The settings of every Train Data Source a node's output is built from (the
 * node itself and everything upstream of it). Stored with each recorded output,
 * so an output made before any of those sources changed - even one behind a
 * Preprocessing node - is recognised as coming from an old file. Undefined when
 * no Train Data Source feeds the node. `self` overrides the node's own data,
 * e.g. with a dialog's unsaved settings at Test Node time.
 */
export const upstreamSourcesKey = (
  nodeId: string,
  nodes: GraphNode[],
  edges: GraphEdge[],
  self?: GraphNode
): string | undefined => {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  if (self) byId.set(nodeId, self);
  const seen = new Set<string>();
  const stack = [nodeId];
  while (stack.length > 0) {
    const id = stack.pop() as string;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const edge of edges) if (edge.target === id) stack.push(edge.source);
  }
  const sources = [...seen]
    .map((id) => byId.get(id))
    .filter((n): n is GraphNode => n?.type === TRAIN_DATA_SOURCE_NODE_TYPE)
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((n) => [n.id, trainingSourceSettingsKey(n.type, n.data)]);
  return sources.length > 0 ? JSON.stringify(sources) : undefined;
};

export type ResolvedInputFile =
  | { ok: true; fileUrl: string; file?: { id?: string; name?: string } }
  | { ok: false; message: string };

export interface ResolveInputFileArgs {
  /** The node's File URL setting, e.g. "{{source.data_path}}". */
  fileUrl: string;
  nodeId?: string;
  nodes: Node[];
  edges: Edge[];
  /** The newest real output of a node, from a Test Node or a whole run. */
  getLatestOutput: (nodeId: string) => NodeExecutionResult | undefined;
  /** Fills any other {{...}} variables from the data available to the node. */
  fillVariables: (url: string) => string;
}

const isCsvFile = (name: string): boolean => /\.csv$/i.test(name.split(/[?#]/)[0]);

const nodeLabel = (node: Node): string => {
  const name = (node.data as { name?: unknown } | undefined)?.name;
  if (typeof name === "string" && name.trim()) return name.trim();
  return node.type === TRAIN_DATA_SOURCE_NODE_TYPE ? TRAIN_DATA_SOURCE_LABEL : "previous";
};

// {{source.data_path}} is the file the node directly upstream produces.
const resolveSourceDataPath = ({
  nodeId,
  nodes,
  edges,
  getLatestOutput,
}: ResolveInputFileArgs): ResolvedInputFile => {
  // Several edges from the same node (e.g. different handles) are one input.
  const upstreamIds = nodeId
    ? [...new Set(edges.filter((edge) => edge.target === nodeId).map((edge) => edge.source))]
    : [];
  const upstream = upstreamIds
    .map((id) => nodes.find((n) => n.id === id))
    .filter((n): n is Node => !!n);
  if (upstream.length === 0) {
    return {
      ok: false,
      message: "Connect the node that provides the data to this node first.",
    };
  }
  if (upstream.length > 1) {
    return {
      ok: false,
      message:
        "This node has more than one input, so it can't tell which file {{source.data_path}} means. Enter the file path instead.",
    };
  }

  const source = upstream[0];
  const isTrainingSource = source.type === TRAIN_DATA_SOURCE_NODE_TYPE;

  // An uploaded CSV can be read straight from the source's current settings,
  // so Analyze works before the source has run and follows a swapped file.
  // Only the path is sent: with a file id, analyze-csv reads a downloaded temp
  // copy, which its python_code (step preview) branch can't open.
  if (isTrainingSource) {
    const d = source.data as TrainDataSourceNodeData;
    const selected = d.csvFilePath || d.csvFileUrl;
    if (d.sourceType === "csv" && selected && isCsvFile(d.csvFileName || selected)) {
      return { ok: true, fileUrl: selected };
    }
  }

  // Otherwise (a database query, an Excel/Parquet/JSON upload, or a node
  // that transforms the data) only a run knows the file.
  const latest = getLatestOutput(source.id);
  const dataPath = latest?.output?.data_path;
  const label = nodeLabel(source);
  if (!latest || typeof dataPath !== "string" || !dataPath.trim()) {
    return { ok: false, message: `Run the ${label} node first, then try again.` };
  }
  // An output is only current when the Train Data Sources it was built from
  // still have the settings they had then.
  const currentKey = upstreamSourcesKey(source.id, nodes, edges);
  if (currentKey !== undefined && latest.settingsKey !== currentKey) {
    // Outputs recorded before settings were tracked can't be checked.
    if (latest.settingsKey === undefined) {
      return {
        ok: false,
        message: `Run the ${label} node again to refresh its output, then try again.`,
      };
    }
    return {
      ok: false,
      message: isTrainingSource
        ? `The ${label} settings changed since it last ran. Run the ${label} node again, then try again.`
        : `The training data changed since the ${label} node last ran. Run it again, then try again.`,
    };
  }
  return { ok: true, fileUrl: dataPath };
};

/**
 * Resolve a training node's File URL to a real file. Never returns a value
 * that still has a {{...}} placeholder in it - the caller shows `message`
 * instead of sending the request.
 */
export const resolveTrainingInputFile = (args: ResolveInputFileArgs): ResolvedInputFile => {
  const url = args.fileUrl.trim();
  if (!url) return { ok: false, message: "Please provide a file URL to analyze" };
  if (url === SOURCE_DATA_PATH) return resolveSourceDataPath(args);

  const filled = hasUnfilledPlaceholder(url) ? args.fillVariables(url) : url;
  if (hasUnfilledPlaceholder(filled)) {
    const unfilled = filled.match(/{{[^}]*}}/g)?.join(", ");
    return {
      ok: false,
      message: `${unfilled} has no value yet. Run the nodes before this one first, then try again.`,
    };
  }
  return { ok: true, fileUrl: filled };
};

/** Pick the newer of two recorded outputs of the same node. */
export const newerOutput = (
  a: NodeExecutionResult | undefined,
  b: NodeExecutionResult | undefined
): NodeExecutionResult | undefined => {
  if (!a) return b;
  if (!b) return a;
  return b.timestamp > a.timestamp ? b : a;
};
