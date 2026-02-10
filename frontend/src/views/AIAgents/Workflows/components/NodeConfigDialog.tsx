import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

import { JsonViewer, NodeMetadata } from "./custom/JsonViewer";
import { GenericTestDialog } from "./GenericTestDialog";
import { Button } from "@/components/button";
import { Play } from "lucide-react";
import { NodeData } from "../types/nodes";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { Node, Edge } from "reactflow";
import { Checkbox } from "@/components/checkbox";
import { Label } from "@/components/label";
import nodeRegistry from "../registry/nodeRegistry";

interface WorkflowNodesDialogProps {
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
}

export const NodeConfigDialog: React.FC<WorkflowNodesDialogProps> = ({
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
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(nodeType);

  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [initialNodeName, setInitialNodeName] = useState<string | undefined>(
    undefined
  );
  const { getAvailableDataForNode, hasNodeBeenExecuted, nodes: workflowNodes } =
    useWorkflowExecution();

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

  // Debug logging for props
  React.useEffect(() => {}, [nodeId, nodeType, data, isOpen]);

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

  const nodeName = initialNodeName || nodeDefinition?.label || "node";

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent
          className={cn(
            "max-w-6xl max-h-[85vh] w-full overflow-hidden",
            className
          )}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onClick={handleClick}
        >
          <DialogHeader>
            <div className="flex items-center justify-between mr-4">
              <div>
                <DialogTitle>{`Configure ${nodeName}`}</DialogTitle>
                <DialogDescription className="break-words">
                  {nodeDefinition?.configSubtitle}
                </DialogDescription>
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
          </DialogHeader>

          <div className="flex flex-1 gap-6 overflow-hidden">
            {/* Left side - JSON State section */}
            {jsonStateDisplay && (
              <div className="w-80 border-r border-gray-200 pr-6 flex flex-col flex-shrink-0">
                <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-200">
                  <div>
                    {/* <h3 className="font-semibold text-gray-900 text-base">
                      {jsonStateDisplay.title}
                    </h3> */}
                    <p className="text-xs text-gray-500">
                      Drag variables to input fields
                    </p>
                  </div>
                </div>

                <div className="flex-1 bg-white rounded-lg border border-gray-200 overflow-y-auto overflow-x-hidden min-h-0 max-h-[calc(85vh-200px)]">
                  <div className="p-3 bg-white">
                    {jsonStateDisplay.data ? (
                      <JsonViewer
                        data={jsonStateDisplay.data as Record<string, unknown>}
                        onDragStart={handleDragStart}
                        nodeMetadata={nodeMetadata}
                      />
                    ) : (
                      <div className="text-gray-500 text-sm text-center font-extrabold text-red-500">
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

            {/* Right side - Main content */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-1 max-h-[calc(85vh-180px)] min-w-0">
              <div className="flex flex-col space-y-4 min-w-0 w-full">
                {children}
              </div>
            </div>
          </div>

          <DialogFooter className="mt-4">{footer}</DialogFooter>
        </DialogContent>
      </Dialog>

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
    </>
  );
};
