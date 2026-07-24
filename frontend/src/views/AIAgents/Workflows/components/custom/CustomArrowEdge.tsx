import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
  useStore,
} from "reactflow";

interface CustomArrowEdgeProps {
  id: string;
  source: string;
  target: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition?: any;
  targetPosition?: any;
  style?: React.CSSProperties;
  markerEnd?: string;
  data?: any;
}

const offset = 3;

const getOffsets = (position: Position) => {
  const offsets = {
    [Position.Top]: { x: 0, y: -offset },
    [Position.Right]: { x: offset, y: 0 },
    [Position.Bottom]: { x: 0, y: offset },
    [Position.Left]: { x: -offset, y: 0 },
  };
  return offsets[position] || { x: 0, y: 0 };
};

const CustomArrowEdge: React.FC<CustomArrowEdgeProps> = ({
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}) => {
  // Subscribe to the endpoint nodes so the edge re-renders when a node is
  // (de)activated, moved or resized. `nodeInternals` carries the measured
  // dimensions and absolute position needed to locate a node's center.
  const sourceNode = useStore((s) => s.nodeInternals.get(source));
  const targetNode = useStore((s) => s.nodeInternals.get(target));

  const isSourceDeactivated = !!sourceNode?.data?.deactivated;
  const isTargetDeactivated = !!targetNode?.data?.deactivated;

  const centerOf = (node?: typeof sourceNode) => {
    const pos = node?.positionAbsolute ?? node?.position;
    if (!node || !pos) return null;
    return {
      x: pos.x + (node.width ?? 0) / 2,
      y: pos.y + (node.height ?? 0) / 2,
    };
  };

  const { x: sourceXOffset, y: sourceYOffset } = getOffsets(sourcePosition);
  const { x: targetXOffset, y: targetYOffset } = getOffsets(targetPosition);

  let adjustedSourceX = sourceX + sourceXOffset;
  let adjustedSourceY = sourceY + sourceYOffset;
  let adjustedTargetX = targetX + targetXOffset;
  let adjustedTargetY = targetY + targetYOffset;

  // When an endpoint sits on a deactivated node, pin that endpoint to the node's
  // center. The two edges around a bypassed node (the one coming in and the one
  // going out) then meet at the same center point, so together they read as a
  // single line passing straight through the middle of the node.
  if (isSourceDeactivated) {
    const c = centerOf(sourceNode);
    if (c) {
      adjustedSourceX = c.x;
      adjustedSourceY = c.y;
    }
  }
  if (isTargetDeactivated) {
    const c = centerOf(targetNode);
    if (c) {
      adjustedTargetX = c.x;
      adjustedTargetY = c.y;
    }
  }

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: adjustedSourceX,
    sourceY: adjustedSourceY,
    sourcePosition,
    targetX: adjustedTargetX,
    targetY: adjustedTargetY,
    targetPosition,
  });

  // Only the segment arriving at a real (active) node keeps the arrowhead. The
  // segment feeding INTO a deactivated node hides it, so a bypassed node shows a
  // single arrow into the next active node instead of two.
  const resolvedMarkerEnd = isTargetDeactivated ? undefined : markerEnd;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={resolvedMarkerEnd}
        style={{
          ...style,
          strokeWidth: 2,
          stroke: "hsl(var(--brand-600))",
          strokeDasharray: "7,7",
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 12,
            pointerEvents: "all",
          }}
          className="nodrag nopan"
        >
          {data?.label && (
            <div className="bg-card px-2 py-1 rounded border shadow-sm text-xs">
              {data.label}
            </div>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default React.memo(CustomArrowEdge);
