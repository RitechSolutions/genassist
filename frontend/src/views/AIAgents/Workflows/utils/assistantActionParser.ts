import { Node, Edge, MarkerType } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import nodeRegistry from "../registry/nodeRegistry";

// ── Types ──

export interface AddNodeAction {
  type: "add_node";
  nodeType: string;
  label?: string;
  config?: Record<string, unknown>;
  connectTo?: string;
  /** Resolve connect_to by matching a node's label instead of its ID (used when chaining newly added nodes) */
  connectToLabel?: string;
  /** When set, also creates an edge from the new node's output to this node's input */
  thenConnectTo?: string;
  /** Resolve then_connect_to by matching a node's label instead of its ID */
  thenConnectToLabel?: string;
  /** When set, wraps the new node in a toolBuilderNode and connects both to this agent node id */
  asToolFor?: string;
}

export interface UpdateNodeAction {
  type: "update_node";
  nodeId: string;
  updates: Record<string, unknown>;
}

export interface RemoveNodeAction {
  type: "remove_node";
  nodeId: string;
}

export interface RemoveEdgeAction {
  type: "remove_edge";
  fromNodeId: string;
  toNodeId: string;
}

export type ParsedAction = AddNodeAction | UpdateNodeAction | RemoveNodeAction | RemoveEdgeAction;

export interface ParseResult {
  cleanText: string;
  actions: ParsedAction[];
}

export interface AssistantMessage {
  id: string;
  speaker: "agent" | "customer";
  text: string;
  actions?: ParsedAction[];
}

// ── Canvas Context Serializer ──

export function serializeCanvasContext(nodes: Node[], edges: Edge[]): string {
  const nodeLines = nodes.map((n) => {
    const label = (n.data?.name as string) || (n.data?.label as string) || n.type || "unknown";
    return `- ${n.type}(id="${n.id}", label="${label}")`;
  });

  const edgeLines = edges.map((e) => {
    const src = e.sourceHandle ? `${e.source}:${e.sourceHandle}` : e.source;
    const tgt = e.targetHandle ? `${e.target}:${e.targetHandle}` : e.target;
    return `${src}→${tgt}`;
  });

  return [
    "[CANVAS_CONTEXT]",
    "Nodes:",
    ...nodeLines,
    `Edges: ${edgeLines.join(", ") || "none"}`,
    "[/CANVAS_CONTEXT]",
  ].join("\n");
}

// ── Action Parser ──

const ADD_NODE_REGEX = /<ADD_NODE>([\s\S]*?)<\/ADD_NODE>/g;
const UPDATE_NODE_REGEX = /<UPDATE_NODE>([\s\S]*?)<\/UPDATE_NODE>/g;
const REMOVE_NODE_REGEX = /<REMOVE_NODE>([\s\S]*?)<\/REMOVE_NODE>/g;
const REMOVE_EDGE_REGEX = /<REMOVE_EDGE>([\s\S]*?)<\/REMOVE_EDGE>/g;

export function parseAgentActions(text: string): ParseResult {
  const actions: ParsedAction[] = [];
  let cleanText = text;

  // Parse ADD_NODE
  let match: RegExpExecArray | null;
  ADD_NODE_REGEX.lastIndex = 0;
  while ((match = ADD_NODE_REGEX.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.node_type) {
        actions.push({
          type: "add_node",
          nodeType: parsed.node_type,
          label: parsed.label,
          config: parsed.config,
          connectTo: parsed.connect_to,
          connectToLabel: parsed.connect_to_label,
          thenConnectTo: parsed.then_connect_to,
          thenConnectToLabel: parsed.then_connect_to_label,
          asToolFor: parsed.as_tool_for,
        });
      }
    } catch {
      // skip
    }
    cleanText = cleanText.replace(match[0], "");
  }

  // Parse UPDATE_NODE
  UPDATE_NODE_REGEX.lastIndex = 0;
  while ((match = UPDATE_NODE_REGEX.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.node_id && parsed.updates) {
        actions.push({
          type: "update_node",
          nodeId: parsed.node_id,
          updates: parsed.updates,
        });
      }
    } catch {
      // skip
    }
    cleanText = cleanText.replace(match[0], "");
  }

  // Parse REMOVE_NODE
  REMOVE_NODE_REGEX.lastIndex = 0;
  while ((match = REMOVE_NODE_REGEX.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.node_id) {
        actions.push({
          type: "remove_node",
          nodeId: parsed.node_id,
        });
      }
    } catch {
      // skip
    }
    cleanText = cleanText.replace(match[0], "");
  }

  // Parse REMOVE_EDGE
  REMOVE_EDGE_REGEX.lastIndex = 0;
  while ((match = REMOVE_EDGE_REGEX.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.from_node_id && parsed.to_node_id) {
        actions.push({
          type: "remove_edge",
          fromNodeId: parsed.from_node_id,
          toNodeId: parsed.to_node_id,
        });
      }
    } catch {
      // skip
    }
    cleanText = cleanText.replace(match[0], "");
  }

  return { cleanText: cleanText.trim(), actions };
}

// ── Action Label (for UI badges) ──

export function getActionLabel(action: ParsedAction): string {
  switch (action.type) {
    case "add_node":
      return `Added ${action.label || action.nodeType}`;
    case "update_node":
      return `Updated node`;
    case "remove_node":
      return `Removed node`;
    case "remove_edge":
      return `Removed connection`;
  }
}

// ── Position Calculator ──

export function calculateNodePosition(
  connectToId: string | undefined,
  existingNodes: Node[],
): { x: number; y: number } {
  const X_GAP = 350;
  const Y_GAP = 200;

  if (connectToId) {
    const sourceNode = existingNodes.find((n) => n.id === connectToId);
    if (sourceNode) {
      const targetX = (sourceNode.position?.x ?? 0) + X_GAP;
      const targetY = sourceNode.position?.y ?? 0;

      const hasOverlap = existingNodes.some(
        (n) =>
          Math.abs((n.position?.x ?? 0) - targetX) < 200 &&
          Math.abs((n.position?.y ?? 0) - targetY) < 150,
      );

      return {
        x: targetX,
        y: hasOverlap ? targetY + Y_GAP : targetY,
      };
    }
  }

  if (existingNodes.length > 0) {
    const rightmost = existingNodes.reduce((max, n) =>
      (n.position?.x ?? 0) > (max.position?.x ?? 0) ? n : max,
    );
    return {
      x: (rightmost.position?.x ?? 0) + X_GAP,
      y: rightmost.position?.y ?? 200,
    };
  }

  return { x: 250, y: 200 };
}

// ── Node + Edge Creator ──

const EDGE_STYLE = {
  strokeWidth: 2,
  stroke: "hsl(var(--brand-600))",
  strokeDasharray: "7,7",
} as const;

const EDGE_MARKER = {
  type: MarkerType.ArrowClosed,
  width: 16,
  height: 16,
  color: "hsl(var(--brand-600))",
} as const;

function makeEdge(
  source: string,
  target: string,
  sourceHandle: string,
  targetHandle: string,
): Edge {
  return {
    id: `reactflow__edge-${source}${sourceHandle}-${target}${targetHandle}`,
    source,
    target,
    sourceHandle,
    targetHandle,
    type: "default",
    markerEnd: EDGE_MARKER,
    style: EDGE_STYLE,
  };
}

export function createNodeFromAction(
  action: AddNodeAction,
  existingNodes: Node[],
): { nodes: Node[]; edges: Edge[] } {
  const nodeDef = nodeRegistry.getNodeType(action.nodeType);
  if (!nodeDef) return { nodes: [], edges: [] };

  // Resolve label-based references against existing nodes
  const resolveId = (id?: string, label?: string): string | undefined => {
    if (id) return id;
    if (label) {
      const match = existingNodes.find(
        (n) =>
          (n.data?.name as string)?.toLowerCase() === label.toLowerCase() ||
          (n.data?.label as string)?.toLowerCase() === label.toLowerCase(),
      );
      return match?.id;
    }
    return undefined;
  };

  const resolvedConnectTo = resolveId(action.connectTo, action.connectToLabel);
  const resolvedThenConnectTo = resolveId(action.thenConnectTo, action.thenConnectToLabel);

  const id = uuidv4();
  const anchorId = action.asToolFor ?? resolvedConnectTo;
  const position = calculateNodePosition(anchorId, existingNodes);

  const overrideData: Record<string, unknown> = {};
  if (action.label) overrideData.name = action.label;
  if (action.config) Object.assign(overrideData, action.config);

  const node = nodeRegistry.createNode(action.nodeType, id, position, overrideData);
  if (!node) return { nodes: [], edges: [] };

  // ── Tool pattern: wrap in toolBuilderNode ──
  if (action.asToolFor) {
    const tbId = uuidv4();
    const tbPosition = {
      x: position.x - 175,
      y: position.y - 200,
    };
    const tbNode = nodeRegistry.createNode("toolBuilderNode", tbId, tbPosition, {
      name: action.label ? `${action.label} Tool` : `${action.nodeType} Tool`,
    });
    if (!tbNode) return { nodes: [node], edges: [] };

    return {
      nodes: [tbNode, node],
      edges: [
        makeEdge(tbId, action.asToolFor, "output_tool", "input_tools"),
        makeEdge(tbId, id, "starter_processor", "input"),
      ],
    };
  }

  // ── Standard connect_to pattern ──
  const edges: Edge[] = [];
  if (resolvedConnectTo) {
    const sourceNode = existingNodes.find((n) => n.id === resolvedConnectTo);
    if (sourceNode) {
      edges.push(makeEdge(resolvedConnectTo, id, "output", "input"));
    }
  }

  // ── Optional chained output edge ──
  if (resolvedThenConnectTo) {
    edges.push(makeEdge(id, resolvedThenConnectTo, "output", "input"));
  }

  return { nodes: [node], edges };
}
