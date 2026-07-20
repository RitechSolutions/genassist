import React from "react";
import { MiniMap } from "reactflow";
import type { Node } from "reactflow";
import nodeRegistry from "../registry/nodeRegistry";

// Concrete colors per node category, mirroring utils/nodeColors.ts. The MiniMap
// paints each node's fill via the SVG `fill` *attribute*, which does not resolve
// Tailwind classes ("pink-600") or CSS custom properties (var(--brand-600)) — so
// the category → color map has to be spelled out with literal values here.
const CATEGORY_MINIMAP_COLORS: Record<string, string> = {
  io: "hsl(229 86% 51%)", // brand-600
  ai: "#db2777", // pink-600
  routing: "#f97316", // orange-500
  integrations: "#16a34a", // green-600
  formatting: "#9333ea", // purple-600
  tools: "#0284c7", // sky-600
  training: "#e11d48", // rose-600
  audio: "#0d9488", // teal-600
  default: "hsl(229 86% 51%)", // brand-600
};

// Color a minimap node by its registry category, falling back to the brand color
// for unknown/unregistered types.
const getMiniMapNodeColor = (node: Node): string => {
  const category =
    nodeRegistry.getNodeType(node.type ?? "")?.category ?? "default";
  return CATEGORY_MINIMAP_COLORS[category] ?? CATEGORY_MINIMAP_COLORS.default;
};

interface WorkflowMiniMapProps {
  /** When false the minimap fades out of the way (see the `visible` gate in GraphFlow). */
  visible: boolean;
}

// Explicit size (a touch smaller than React Flow's 200×150 default) so it tucks in
// neatly beside the bottom-left zoom/lock controls. MiniMap reads its SVG dimensions
// from `style.width`/`style.height`, so sizing has to go through the style prop.
const MINIMAP_SIZE = { width: 172, height: 116 };

// Small overview map tucked into the bottom-left, right next to the zoom/lock controls.
// Pannable + zoomable so it doubles as a navigation control on large workflows. It only
// shows while the user is moving around the canvas — the `visible` prop toggles the fade,
// and the container/mask theming lives in index.css (.wf-minimap) so it adapts light/dark.
const WorkflowMiniMap: React.FC<WorkflowMiniMapProps> = ({ visible }) => {
  return (
    <MiniMap
      className={`wf-minimap${visible ? " is-visible" : ""}`}
      position="bottom-left"
      style={MINIMAP_SIZE}
      pannable
      zoomable
      nodeColor={getMiniMapNodeColor}
      nodeStrokeWidth={3}
      nodeBorderRadius={3}
      ariaLabel="Workflow minimap"
    />
  );
};

export default WorkflowMiniMap;