import { Badge } from "@/components/badge";
import React, { useState, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { Handle, HandleProps, Position } from "reactflow";
import { NodeCompatibility, NodeData } from "../../types/nodes";
import { getHandlerPosition } from "../../utils/helpers";

interface HandleTooltipProps extends HandleProps {
  nodeId: string;
  compatibility?: NodeCompatibility;
  label?: string;
  style?: React.CSSProperties;
}

const getCompatibilityColor = (compatibility?: string) => {
  return "hsl(var(--brand-600))";
  // switch (compatibility) {
  //   case "text":
  //     return "blue";
  //   case "tools":
  //     return "green";
  //   case "llm":
  //     return "purple";
  //   case "json":
  //     return "orange";
  //   case "any":
  //     return "gray";
  //   default:
  //     return "gray";
  // }
};
const getCompatibilityDescription = (
  compatibility?: string,
  type?: string,
  nodeId?: string,
  label?: string
) => {
  if (label) return `${type === "source" ? "Output" : "Input"} ${label}`;
  try {
    return (
      (type === "source" ? "Output" : "Input") +
      ` ${nodeId.replace("input_", "").replace("output_", "")}`
    );
  } catch (error) {
    return "";
  }
};

const HandlersRendererComponent: React.FC<{
  id: string;
  data: NodeData;
}> = ({ id, data }) => {
  const { rightHandler, leftHandler, topHandler, bottomHandler } = useMemo(() => {
    const handlers = data.handlers ?? [];
    return {
      rightHandler: handlers.filter((handler) => handler.position === "right"),
      leftHandler: handlers.filter((handler) => handler.position === "left"),
      topHandler: handlers.filter((handler) => handler.position === "top"),
      bottomHandler: handlers.filter((handler) => handler.position === "bottom"),
    };
  }, [data.handlers]);

  return (
    <>
      {rightHandler?.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.position as Position}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          label={handler.label}
          style={{ top: getHandlerPosition(index, rightHandler.length) }}
        />
      ))}
      {leftHandler?.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          id={handler.id}
          position={handler.position as Position}
          nodeId={id}
          compatibility={handler.compatibility}
          label={handler.label}
          style={{ top: getHandlerPosition(index, leftHandler.length) }}
        />
      ))}
      {topHandler?.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.position as Position}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          label={handler.label}
          style={{ left: getHandlerPosition(index, topHandler.length) }}
        />
      ))}
      {bottomHandler?.map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.position as Position}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          label={handler.label}
          style={{ left: getHandlerPosition(index, bottomHandler.length) }}
        />
      ))}
    </>
  );
};

export const HandlersRenderer = React.memo(HandlersRendererComponent);

const HandleTooltipComponent: React.FC<HandleTooltipProps> = ({
  compatibility,
  label,
  nodeId,
  style,
  type,
  ...handleProps
}) => {
  // Screen position of the tooltip while the handle is hovered (null = hidden).
  const [tooltipPos, setTooltipPos] = useState<{ left: number; top: number } | null>(null);
  const handleRef = useRef<HTMLDivElement>(null);

  return (
    <>
      <div
        onMouseEnter={() => {
          const rect = handleRef.current?.getBoundingClientRect();
          if (rect) setTooltipPos({ left: rect.right + 8, top: rect.bottom + 8 });
        }}
        onMouseLeave={() => setTooltipPos(null)}
      >
        <Handle
          ref={handleRef}
          type={type}
          {...handleProps}
          style={{
            width: "calc(var(--handler-diameter) * 1px)",
            height: "calc(var(--handler-diameter) * 1px)",
            backgroundColor: getCompatibilityColor(compatibility),
            ...style,
          }}
        />
      </div>

      {/* Portalled to <body>: rendered inside the node, the tooltip was trapped in that node's
          stacking context (React Flow gives each node a transform + z-index), so neighbouring
          nodes painted over it. */}
      {tooltipPos &&
        createPortal(
          <div
            className="pointer-events-none fixed z-50 flex flex-col gap-2 rounded bg-gray-900 p-2 font-mono text-xs text-white shadow-lg whitespace-pre"
            style={tooltipPos}
          >
            <Badge style={{ background: getCompatibilityColor(compatibility) }}>
              {compatibility}
            </Badge>
            {getCompatibilityDescription(compatibility, type, handleProps.id, label)}
          </div>,
          document.body
        )}
    </>
  );
};

export const HandleTooltip = React.memo(HandleTooltipComponent);
