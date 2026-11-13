import { Badge } from "@/components/badge";
import { GenAssistMark } from "@/components/AssistantEmptyState";
import React, { useState, useRef, useMemo, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { Handle, HandleProps, Position, useEdges, useReactFlow } from "reactflow";
import { NodeCompatibility, NodeData } from "../../types/nodes";
import { getHandlerPosition } from "../../utils/helpers";
import { useNodeActions } from "../../context/NodeActionsContext";
import { AddStepWithAiDialog } from "./AddStepWithAiDialog";

// Outputs that carry data onward can have a step added after them with AI; tool,
// model and sub-agent attachments are wired differently and are left alone.
const AI_ADDABLE_COMPATIBILITY = new Set<string>(["any", "text"]);
// Leaving the handle keeps the tooltip up just long enough to reach its button.
const TOOLTIP_LINGER_MS = 180;

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
  const [dialogOpen, setDialogOpen] = useState(false);
  const handleRef = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nodeActions = useNodeActions();
  const { getNode } = useReactFlow();
  const edges = useEdges();
  const handleId = String(handleProps.id ?? "output");
  // An output that already leads somewhere has its next step; the offer is for empty ones.
  const alreadyConnected = edges.some(
    (edge) => edge.source === nodeId && String(edge.sourceHandle ?? "output") === handleId
  );
  const canAddWithAi =
    type === "source" &&
    !!nodeActions &&
    !alreadyConnected &&
    AI_ADDABLE_COMPATIBILITY.has(String(compatibility ?? "any"));
  const handleLabel = label || String(handleProps.id ?? "").replace(/^output_?/, "").replace(/_/g, " ") || "output";

  const cancelHide = useCallback(() => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  }, []);
  const scheduleHide = useCallback(() => {
    cancelHide();
    hideTimer.current = setTimeout(() => setTooltipPos(null), canAddWithAi ? TOOLTIP_LINGER_MS : 0);
  }, [cancelHide, canAddWithAi]);
  useEffect(() => cancelHide, [cancelHide]);

  const nodeName = () => {
    const data = getNode(nodeId)?.data as { name?: unknown } | undefined;
    return typeof data?.name === "string" && data.name ? data.name : "this step";
  };

  return (
    <>
      <div
        onMouseEnter={() => {
          cancelHide();
          const rect = handleRef.current?.getBoundingClientRect();
          if (rect) setTooltipPos({ left: rect.right + 8, top: rect.bottom + 8 });
        }}
        onMouseLeave={scheduleHide}
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
            className={`fixed z-50 flex flex-col gap-2 rounded-lg bg-gray-900 p-2 font-mono text-xs text-white shadow-lg whitespace-pre ${
              canAddWithAi ? "pointer-events-auto" : "pointer-events-none"
            }`}
            style={tooltipPos}
            onMouseEnter={cancelHide}
            onMouseLeave={scheduleHide}
          >
            <Badge style={{ background: getCompatibilityColor(compatibility) }}>
              {compatibility}
            </Badge>
            {getCompatibilityDescription(compatibility, type, handleProps.id, label)}
            {canAddWithAi && (
              <button
                type="button"
                className="nodrag nopan mt-0.5 inline-flex items-center gap-1.5 rounded-md bg-white/10 px-2 py-1 font-sans text-[11px] font-medium text-white transition-colors hover:bg-[hsl(var(--brand-600))]"
                onMouseDown={(event) => event.stopPropagation()}
                onClick={(event) => {
                  event.stopPropagation();
                  cancelHide();
                  setTooltipPos(null);
                  setDialogOpen(true);
                }}
              >
                {/* The tooltip is always dark, so the mark follows its white text, not the page theme. */}
                <GenAssistMark className="h-3.5 w-3.5 text-white dark:text-white" />
                Ask GenAgent
              </button>
            )}
          </div>,
          document.body
        )}
      {canAddWithAi && dialogOpen && (
        <AddStepWithAiDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          nodeName={nodeName()}
          handleLabel={handleLabel}
          onSubmit={(instruction) =>
            nodeActions?.addStepWithAi(nodeId, handleId, handleLabel, instruction)
          }
        />
      )}
    </>
  );
};

export const HandleTooltip = React.memo(HandleTooltipComponent);
