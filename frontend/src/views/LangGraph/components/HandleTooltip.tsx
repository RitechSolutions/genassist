import { Badge } from "@/components/badge";
import React, { useState, useRef, useEffect } from "react";
import { Handle, Position, HandleProps } from "reactflow";

interface HandleTooltipProps extends HandleProps {
  nodeId: string;
  compatibility?: 'text' | 'tools' | 'llm' | 'json' | 'any';
  style?: React.CSSProperties;
}

const getCompatibilityColor = (compatibility?: string) => {
  switch (compatibility) {
    case 'text':
      return 'blue';
    case 'tools':
      return 'green';
    case 'llm':
      return 'purple';
    case 'json':
      return 'orange';
    case 'any':
      return 'gray';
    default:
      return 'gray';
  }
};
const getCompatibilityDescription = (compatibility?: string, type?: string, nodeId?: string) => {
  switch (compatibility) {
    case 'text':
      return ( type === 'source' ? 'Output Text' : 'Input Text') + ` ${nodeId.replace('input_', '').replace('output', '')}`;
    case 'tools':
      return ( type === 'source' ? 'Output Tools' : 'Input Tools') + ` ${nodeId.replace('input_', '').replace('output', '')}`;
    case 'llm':
      return 'LLM';
    case 'json':
      return ( type === 'source' ? 'Output JSON' : 'Input JSON') + ` ${nodeId.replace('input_', '').replace('output', '')}`;
    case 'any':
      return 'Any';
    default:
      return 'Any';
  }
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
        <Handle ref={handleRef} type={type} {...handleProps} style={{ width: 14, height: 14, backgroundColor: getCompatibilityColor(compatibility),...style}} />
      </div>

      {showTooltip && (
        <div
          className="fixed flex flex-col gap-2 z-50 bg-gray-900 text-white text-xs p-2 rounded shadow-lg font-mono whitespace-pre"
          style={{
            left: handleRef.current?.offsetLeft+20,
            top: handleRef.current?.offsetTop + 20,
            // transform:
            //   handleProps.position === Position.Left
            //     ? "translateX(-100%)"
            //     : "none",
          }}
        >
          <Badge style={{background:getCompatibilityColor(compatibility)}}>{compatibility}</Badge>
          {getCompatibilityDescription(compatibility, type, handleProps.id)}
        </div>
      )}
    </>
  );
};
