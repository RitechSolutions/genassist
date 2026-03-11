import { Node, Edge, MarkerType } from "reactflow";
import { v4 as uuidv4 } from "uuid";
import nodeRegistry from "../registry/nodeRegistry";

// ── Types ──

export interface ParsedAction {
  type: "add_node";
  nodeType: string;
  label?: string;
  config?: Record<string, unknown>;
  connectTo?: string;
}

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

export function parseAgentActions(text: string): ParseResult {
  const actions: ParsedAction[] = [];
  let cleanText = text;

  let match: RegExpExecArray | null;
  // Reset regex state
  ADD_NODE_REGEX.lastIndex = 0;

  while ((match = ADD_NODE_REGEX.exec(text)) !== null) {
    const rawContent = match[1].trim();
    try {
      const parsed = JSON.parse(rawContent);
      if (parsed.node_type) {
        actions.push({
          type: "add_node",
          nodeType: parsed.node_type,
          label: parsed.label,
          config: parsed.config,
          connectTo: parsed.connect_to,
        });
      }
    } catch {
      // Not valid JSON — skip this block
    }
    cleanText = cleanText.replace(match[0], "");
  }

  return { cleanText: cleanText.trim(), actions };
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

      // Check for overlap and shift down if needed
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

  // No connectTo or source not found — place right of the rightmost node
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

export function createNodeFromAction(
  action: ParsedAction,
  existingNodes: Node[],
): { node: Node | null; edge: Edge | null } {
  const nodeDef = nodeRegistry.getNodeType(action.nodeType);
  if (!nodeDef) return { node: null, edge: null };

  const id = uuidv4();
  const position = calculateNodePosition(action.connectTo, existingNodes);

  const overrideData: Record<string, unknown> = {};
  if (action.label) overrideData.name = action.label;
  if (action.config) Object.assign(overrideData, action.config);

  const node = nodeRegistry.createNode(action.nodeType, id, position, overrideData);
  if (!node) return { node: null, edge: null };

  let edge: Edge | null = null;
  if (action.connectTo) {
    const sourceNode = existingNodes.find((n) => n.id === action.connectTo);
    if (sourceNode) {
      edge = {
        id: `reactflow__edge-${action.connectTo}-${id}`,
        source: action.connectTo,
        target: id,
        sourceHandle: "output",
        targetHandle: "input",
        type: "default",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: "hsl(var(--brand-600))",
        },
        style: {
          strokeWidth: 2,
          stroke: "hsl(var(--brand-600))",
          strokeDasharray: "7,7",
        },
      };
    }
  }

  return { node, edge };
}
