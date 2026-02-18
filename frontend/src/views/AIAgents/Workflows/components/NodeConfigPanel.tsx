import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/sheet";
import { cn } from "@/lib/utils";

import { JsonViewer, NodeMetadata } from "./custom/JsonViewer";
import { GenericTestDialog } from "./GenericTestDialog";
import { Button } from "@/components/button";
import { Play, GripVertical, Lock, LockOpen, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NodeData } from "../types/nodes";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { Node, Edge, useNodes } from "reactflow";
import { Checkbox } from "@/components/checkbox";
import { Label } from "@/components/label";
import nodeRegistry from "../registry/nodeRegistry";
import { isEqual } from "lodash";
import {
  AlertDialog,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "@/components/alert-dialog";
import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";

const DEFAULT_SHEET_WIDTH_PX = 896;
const MIN_SHEET_WIDTH_PX = 480;

function getMaxSheetWidthPx(): number {
  if (typeof window === "undefined") return 1600;
  return Math.round(window.innerWidth * 0.95);
}
function clampWidth(w: number): number {
  const max = getMaxSheetWidthPx();
  return Math.max(MIN_SHEET_WIDTH_PX, Math.min(max, Math.round(w)));
}

interface WorkflowNodesPanelProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  footer: React.ReactNode;
  className?: string;
  // New props for the JSON state section
  showJsonState?: boolean;
  jsonStateTitle?: string;
  jsonStateData?: Record<string, unknown> | string | null;
  jsonStateType?: "predecessor-outputs" | "input-schemas" | "test-results";
  // Node ID for calculating predecessor state
  nodeId?: string;
  // New props for testing functionality
  nodeType?: string;
  data?: NodeData;
  showHelp?: boolean;
  // Workflow context props
  nodes?: Node[];
  edges?: Edge[];

  // Unwrap field props
  showUnwrap?: boolean;
  onUnwrapChange?: (unwrap: boolean) => void;

  // Save callback (passed via {...props} from dialogs)
  onUpdate?: (data: NodeData) => void;
}

export const NodeConfigPanel: React.FC<WorkflowNodesPanelProps> = ({
  isOpen,
  onClose,
  children,
  footer,
  className,
  // New props for the JSON state section
  showJsonState = true,
  jsonStateTitle = "Node State",
  jsonStateData = null,
  jsonStateType = "predecessor-outputs",
  nodeId,
  // New props for testing functionality
  nodeType,
  data,
  showHelp = false,
  // Unwrap field props
  showUnwrap = false,
  onUnwrapChange,
  onUpdate,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(nodeType);

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [initialNodeName, setInitialNodeName] = useState<string | undefined>(
    undefined
  );
  const [sheetWidth, setSheetWidth] = useState<number | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [isJsonPanelVisible, setIsJsonPanelVisible] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);

  const { getAvailableDataForNode, hasNodeBeenExecuted, nodes: workflowNodes } =
    useWorkflowExecution();

  // --- Unsaved changes detection ---
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false);
  const [internalOpen, setInternalOpen] = useState(isOpen);

  // Get persisted node data from the ReactFlow store
  const reactFlowNodes = useNodes();
  const persistedNodeData = useMemo(() => {
    if (!nodeId) return undefined;
    const node = reactFlowNodes.find((n) => n.id === nodeId);
    return node?.data as NodeData | undefined;
  }, [reactFlowNodes, nodeId]);

  // Check if current panel data differs from persisted node data
  const isDirty = useMemo(() => {
    if (!persistedNodeData || !data) return false;
    try {
      const persistedClean = JSON.parse(JSON.stringify(persistedNodeData));
      const currentClean = JSON.parse(JSON.stringify(data));
      return !isEqual(persistedClean, currentClean);
    } catch {
      return false;
    }
  }, [persistedNodeData, data]);

  // Sync internalOpen from isOpen (Cancel/Save buttons close immediately)
  useEffect(() => {
    if (isOpen) {
      setShowUnsavedDialog(false);
    }
    setInternalOpen(isOpen);
  }, [isOpen]);

  // Intercept Sheet's own close triggers (Escape, X button) — only place we guard
  const handleSheetOpenChange = useCallback(
    (open: boolean) => {
      if (!open) {
        if (isPinned || isTestDialogOpen) return; // Don't close while pinned or testing
        if (isDirty && onUpdate) {
          setShowUnsavedDialog(true);
          return; // Block close, show confirmation
        }
        setInternalOpen(false);
        onClose();
      }
    },
    [isPinned, isTestDialogOpen, isDirty, onUpdate, onClose]
  );

  // Confirmation dialog handlers
  const handleConfirmSave = useCallback(() => {
    if (onUpdate && data) {
      onUpdate(data as NodeData);
    }
    setShowUnsavedDialog(false);
    setInternalOpen(false);
    onClose();
  }, [onUpdate, data, onClose]);

  const handleConfirmDiscard = useCallback(() => {
    setShowUnsavedDialog(false);
    setInternalOpen(false);
    onClose();
  }, [onClose]);

  // Build node metadata for JsonViewer to display node names instead of IDs
  const nodeMetadata: NodeMetadata = React.useMemo(() => {
    const metadata: NodeMetadata = {};
    workflowNodes.forEach((node) => {
      metadata[node.id] = {
        name: node.data?.name || node.type || "Unknown",
        type: node.type || "unknown",
      };
    });
    return metadata;
  }, [workflowNodes]);

  // Capture the node name when the dialog opens
  useEffect(() => {
    if (isOpen) {
      setInitialNodeName(data?.name);
    }
  }, [isOpen]);

  const handleTest = () => {

    setIsTestDialogOpen(true);
  };

  // Determine what data to show in the JSON state section
  const getJsonStateDisplayData = () => {
    if (jsonStateData) {
      // Use custom data if provided
      return {
        title: jsonStateTitle,
        data: jsonStateData,
        type: jsonStateType,
      };
    }

    if (nodeId && showJsonState) {
      // Use calculated available data from workflow execution context
      const availableData = getAvailableDataForNode(nodeId);
      return {
        title: "Available Data",
        data: availableData,
        type: "predecessor-outputs" as const,
      };
    }

    return null;
  };

  const jsonStateDisplay = getJsonStateDisplayData();

  const handleDragStart = (
    e: React.DragEvent,
    path: string,
    value: unknown
  ) => {
    // Set multiple data formats for better compatibility
    e.dataTransfer.setData("application/json", JSON.stringify({ path, value }));
    e.dataTransfer.setData("text/plain", path);
    e.dataTransfer.setData("text/html", `<span>${path}</span>`);

    // Set the drag effect
    e.dataTransfer.effectAllowed = "copy";
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
  e.preventDefault();
  e.stopPropagation();

  const doc = (e.currentTarget.ownerDocument ?? document);
  const el = contentRef.current;

  const startX = e.clientX;
  const startWidth =
    sheetWidth ??
    (el ? el.getBoundingClientRect().width : DEFAULT_SHEET_WIDTH_PX);

  const onMouseMove = (moveEvent: MouseEvent) => {
    const delta = startX - moveEvent.clientX;
    setSheetWidth(clampWidth(startWidth + delta));
  };

  const cleanup = () => {
    doc.removeEventListener("mousemove", onMouseMove);
    doc.removeEventListener("mouseup", cleanup);
    doc.body.style.cursor = "";
    doc.body.style.userSelect = "";
  };

  doc.body.style.cursor = "col-resize";
  doc.body.style.userSelect = "none";
  doc.addEventListener("mousemove", onMouseMove);
  doc.addEventListener("mouseup", cleanup);
}, [sheetWidth, clampWidth]);

  const nodeName = initialNodeName || nodeDefinition?.label || "node";

  // Prevent body scroll when panel is open
  React.useEffect(() => {
    if (isOpen) {
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';

      return () => {
        document.body.style.overflow = previousOverflow;
      };
    }
  }, [isOpen]);

  // When viewport shrinks, clamp sheet width so
  // the resize handle stays on screen and the sheet can be resized again
  useEffect(() => {
    if (!isOpen) return;
    const handleWindowResize = () => {
      const maxW = getMaxSheetWidthPx();
      setSheetWidth((prev) => {
        if (prev == null) return prev;
        return prev > maxW ? maxW : prev;
      });
    };
    window.addEventListener("resize", handleWindowResize);
    handleWindowResize();
    return () => window.removeEventListener("resize", handleWindowResize);
  }, [isOpen]);

  return (
    <>
      <Sheet open={internalOpen} onOpenChange={handleSheetOpenChange} modal={false}>
        <SheetContent
          ref={contentRef}
          hideOverlay={true}
          hideDefaultClose={true}
          className={cn(
            "sm:max-w-4xl w-full flex flex-col p-0 top-2 right-2 h-[calc(100vh-1rem)] rounded-2xl border-2 shadow-2xl data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-right-full overflow-visible",
            className
          )}
          style={{
            zIndex: 1002,
            ...(sheetWidth != null && {
              width: sheetWidth,
              maxWidth: "none",
            }),
          }}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onClick={handleClick}
        >
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize panel"
            className="absolute left-0 top-0 bottom-0 w-2 cursor-col-resize touch-none z-20 flex items-center justify-center group hover:bg-primary/10 rounded-l-2xl transition-colors"
            onMouseDown={handleResizeStart}
          >
            <div className="opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <GripVertical className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>
          <div className="absolute inset-0 flex flex-col overflow-hidden rounded-2xl pointer-events-none [&>*]:pointer-events-auto">
          <SheetHeader className="p-6 pb-4 border-b shrink-0">
            <div className="flex items-center justify-between mr-4">
              <div>
                <SheetTitle className="text-xl font-semibold">{`Configure ${nodeName}`}</SheetTitle>
                <SheetDescription className="break-words">
                  {nodeDefinition?.configSubtitle}
                </SheetDescription>
              </div>
              <div className="flex items-center gap-3">
                {/* Unwrap checkbox - only show if showUnwrap is true */}
                {showUnwrap && data && (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="unwrap"
                      checked={data.unwrap || false}
                      onCheckedChange={(checked) =>
                        onUnwrapChange?.(checked as boolean)
                      }
                    />
                    <Label htmlFor="unwrap" className="text-xs">
                      Unwrap
                    </Label>
                  </div>
                )}
                {/* Test button - only show if nodeType and data are provided */}
                {nodeType && data && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 text-xs"
                    onClick={handleTest}
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Test Node
                  </Button>
                )}
              </div>
            </div>
          </SheetHeader>

          <div className="flex flex-1 gap-6 overflow-hidden px-6 pl-8">
            {/* Left side - JSON State section */}
            {jsonStateDisplay && isJsonPanelVisible && (
              <div className="min-w-80 flex-1 border-r border-gray-200 pr-6 flex flex-col py-6">
                <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-gray-200">
                  <p className="text-xs text-gray-500">
                    Drag variables to input fields
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => setIsJsonPanelVisible(false)}
                    title="Hide variables panel"
                    aria-label="Hide variables panel"
                  >
                    <PanelLeftClose className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>

                <div className="flex-1 bg-white rounded-lg border border-gray-200 overflow-y-auto overflow-x-auto min-h-0 max-h-[calc(85vh-200px)]">
                  <div className="p-3 bg-white min-w-max">
                    {jsonStateDisplay.data ? (
                      <JsonViewer
                        data={jsonStateDisplay.data as Record<string, unknown>}
                        onDragStart={handleDragStart}
                        nodeMetadata={nodeMetadata}
                      />
                    ) : (
                      <div className="text-sm text-center font-extrabold text-red-500">
                        Connect this node to workflow to see available data
                      </div>
                    )}
                  </div>
                </div>

                {showHelp && (
                  <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-start gap-2">
                      <div className="text-blue-600 mt-0.5">
                        <svg
                          className="h-4 w-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </div>
                      <div className="text-xs text-blue-800">
                        <p className="font-medium mb-1">💡 How to use:</p>
                        <ul className="space-y-0.5">
                          <li>
                            • <strong>Drag</strong> any key badge to input
                            fields
                          </li>
                          <li>
                            • <strong>Click</strong> badges to copy reference
                            paths
                          </li>
                          <li>
                            • <strong>Expand</strong> objects to see nested
                            values
                          </li>
                          <li>
                            • <strong>All levels</strong> are draggable
                            (objects, arrays, values)
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
            {jsonStateDisplay && !isJsonPanelVisible && (
              <div className="w-10 flex-shrink-0 border-r border-gray-200 flex flex-col items-center py-4">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setIsJsonPanelVisible(true)}
                  title="Show variables panel"
                  aria-label="Show variables panel"
                >
                  <PanelLeftOpen className="h-4 w-4 text-muted-foreground" />
                </Button>
              </div>
            )}

            {/* Right side - Main content */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden py-6 min-w-0 pl-4 pr-2">
              <div className="flex flex-col space-y-4 min-w-0 w-full">
                {children}
              </div>
            </div>
          </div>

          {/* Sticky Footer with Action Buttons */}
          <div className="shrink-0 border-t bg-background px-6 py-4 flex justify-end gap-3">
            {footer}
          </div>
          </div>
          {/* Lock toggle */}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute left-0 bottom-5 z-30 h-8 w-8 -translate-x-1/2 rounded-full bg-white/50 shadow-md backdrop-blur-sm transition-colors hover:bg-white/70 hover:text-accent-foreground"
            onClick={() => setIsPinned((p) => !p)}
            title={isPinned ? "Unlock – panel can close when clicking outside" : "Lock – keep panel open while navigating"}
            aria-label={isPinned ? "Unlock panel" : "Lock panel"}
          >
            {isPinned ? (
              <Lock className="h-4 w-4" />
            ) : (
              <LockOpen className="h-4 w-4" />
            )}
          </Button>
        </SheetContent>
      </Sheet>

      {/* Generic Test Dialog - automatically included when nodeType and data are provided */}
      {nodeType && data && (
        <GenericTestDialog
          isOpen={isTestDialogOpen}
          onClose={() => setIsTestDialogOpen(false)}
          nodeType={nodeType}
          nodeData={data}
          nodeId={nodeId}
          nodeName={nodeName}
        />
      )}

      {/* Unsaved changes confirmation dialog */}
      <AlertDialog
        open={showUnsavedDialog}
        onOpenChange={(open) => {
          if (!open) handleConfirmDiscard();
        }}
      >
        <AlertDialogPortal>
          <AlertDialogOverlay style={{ zIndex: 1999 }} />
          <AlertDialogPrimitive.Content
            className="fixed left-[50%] top-[50%] grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg"
            style={{ zIndex: 2000 }}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>You have unsaved changes!</AlertDialogTitle>
              <AlertDialogDescription>
                Would you like to save or discard them?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={handleConfirmDiscard}>
                Discard
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmSave}
                className="bg-blue-600 hover:bg-blue-700 focus:ring-blue-600"
              >
                Save
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogPrimitive.Content>
        </AlertDialogPortal>
      </AlertDialog>
    </>
  );
};
