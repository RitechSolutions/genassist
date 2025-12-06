import { Badge } from "@/components/badge";
import React, { useState, useRef } from "react";
import { Handle, HandleProps, Position } from "reactflow";
import { NodeData } from "../../types/nodes";
import { getHandlerPosition } from "../../utils/helpers";

interface HandleTooltipProps extends HandleProps {
  nodeId: string;
  compatibility?: "text" | "tools" | "llm" | "json" | "any";
  style?: React.CSSProperties;
}

const getCompatibilityColor = (compatibility?: string) => {
  switch (compatibility) {
    case "text":
      return "blue";
    case "tools":
      return "green";
    case "llm":
      return "purple";
    case "json":
      return "orange";
    case "any":
      return "gray";
    default:
      return "gray";
  }
};
const getCompatibilityDescription = (
  compatibility?: string,
  type?: string,
  nodeId?: string
) => {
  try{
  return (
    (type === "source" ? "Output" : "Input") +
      ` ${nodeId.replace("input_", "").replace("output_", "")}`
    );
  } catch (error) {
    return "";
  }
};

export const HandlersRenderer: React.FC<{
  id: string;
  data: NodeData;
}> = ({ id, data }) => {
  const rightHandler = data.handlers?.filter(
    (handler) => handler.position === "right"
  );
  const leftHandler = data.handlers?.filter(
    (handler) => handler.position === "left"
  );
  const topHandler = data.handlers?.filter(
    (handler) => handler.position === "top"
  );
  const bottomHandler = data.handlers?.filter(
    (handler) => handler.position === "bottom"
  );

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
          style={{ left: getHandlerPosition(index, bottomHandler.length) }}
        />
      ))}
    </>
  );
};

export const HandleTooltip: React.FC<HandleTooltipProps> = ({
  compatibility,
  nodeId,
  style,
  type,
  ...handleProps
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const handleRef = useRef<HTMLDivElement>(null);

  return (
    <>
      <div
        onMouseEnter={() => {
          setShowTooltip(true);
        }}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <Handle
          ref={handleRef}
          type={type}
          {...handleProps}
          style={{
            width: 14,
            height: 14,
            backgroundColor: getCompatibilityColor(compatibility),
            ...style,
          }}
        />
      </div>

      {showTooltip && (
        <div
          className="fixed flex flex-col gap-2 z-50 bg-gray-900 text-white text-xs p-2 rounded shadow-lg font-mono whitespace-pre"
          style={{
            left: handleRef.current?.offsetLeft + 20,
            top: handleRef.current?.offsetTop + 20,
            // transform:
            //   handleProps.position === Position.Left
            //     ? "translateX(-100%)"
            //     : "none",
          }}
        >
          <Badge style={{ background: getCompatibilityColor(compatibility) }}>
            {compatibility}
          </Badge>
          {getCompatibilityDescription(compatibility, type, handleProps.id)}
        </div>
      )}
    </>
  );
};
