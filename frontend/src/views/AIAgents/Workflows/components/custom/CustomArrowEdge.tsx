import React from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
} from "reactflow";

interface CustomArrowEdgeProps {
  id: string;
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
  id,
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
  const { x: sourceXOffset, y: sourceYOffset } = getOffsets(sourcePosition);
  const { x: targetXOffset, y: targetYOffset } = getOffsets(targetPosition);

  const adjustedSourceX = sourceX + sourceXOffset;
  const adjustedSourceY = sourceY + sourceYOffset;
  const adjustedTargetX = targetX + targetXOffset;
  const adjustedTargetY = targetY + targetYOffset;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: adjustedSourceX,
    sourceY: adjustedSourceY,
    sourcePosition,
    targetX: adjustedTargetX,
    targetY: adjustedTargetY,
    targetPosition,
  });
  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
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
            <div className="bg-white px-2 py-1 rounded border shadow-sm text-xs">
              {data.label}
            </div>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default CustomArrowEdge;
