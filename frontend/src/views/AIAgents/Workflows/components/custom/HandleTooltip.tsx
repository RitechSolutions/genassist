import { Badge } from "@/components/badge";
import React, { useState, useRef, useMemo } from "react";
import { Handle, HandleProps, Position } from "reactflow";
import { NodeData } from "../../types/nodes";
import { getHandlerPosition } from "../../utils/helpers";

interface HandleTooltipProps extends HandleProps {
  nodeId: string;
  compatibility?: "text" | "tools" | "llm" | "json" | "any";
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
  nodeId?: string
) => {
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

export const HandlersRenderer = React.memo(HandlersRendererComponent);

const HandleTooltipComponent: React.FC<HandleTooltipProps> = ({
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
            width: "calc(var(--handler-diameter) * 1px)",
            height: "calc(var(--handler-diameter) * 1px)",
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

export const HandleTooltip = React.memo(HandleTooltipComponent);
