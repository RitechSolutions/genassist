import React, { useState, useRef } from "react";
import { Button } from "@/components/button";
import { X, ChevronLeft, History } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/card";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { getNodeColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";

interface NodePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddNode: (nodeType: string) => void;
  showWorkflowPanel?: boolean;
  onToggleWorkflowPanel?: () => void;
}

const NodePanel: React.FC<NodePanelProps> = ({
  isOpen,
  onClose,
  onAddNode,
  showWorkflowPanel = false,
  onToggleWorkflowPanel,
}) => {
  const nodeCategories = nodeRegistry.getAllCategories();
  const [draggingNodeType, setDraggingNodeType] = useState<string | null>(null);
  const dragPreviewContainerRef = useRef<HTMLDivElement>(null);

  // Handle drag start
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";

    setDraggingNodeType(nodeType);

    if (dragPreviewContainerRef.current) {
      const dragPreview = dragPreviewContainerRef.current.querySelector(
        `[data-node-type="${nodeType}"]`
      ) as HTMLElement;

      if (dragPreview) {
        // Clone the element for the drag operation
        const dragImage = dragPreview.cloneNode(true) as HTMLElement;
        dragImage.style.position = "absolute";
        document.body.appendChild(dragImage);

        // Clean up after a short delay
        setTimeout(() => {
          if (document.body.contains(dragImage)) {
            document.body.removeChild(dragImage);
          }
        }, 100);
      }
    }
  };

  // Handle drag end to reset visual state
  const onDragEnd = () => {
    setDraggingNodeType(null);
  };

  const categoryLabel = {
    io: "I/O",
    ai: "AI",
    routing: "Routing",
    integrations: "Integrations",
    formatting: "Formatting",
    tools: "Tools",
    training: "Training",
  };

  return (
    <>
      <div
        ref={dragPreviewContainerRef}
        className="fixed pointer-events-none"
        style={{ visibility: "hidden" }}
      ></div>

      <div className={`fixed top-4 z-10 flex flex-row gap-2 transition-[right] duration-300 ${
        (() => {
          if (isOpen && showWorkflowPanel) {
            return "right-[calc(20rem+16rem+1rem)]";
          } else if (isOpen) {
            return "right-[calc(16rem+1rem)]";
          } else if (showWorkflowPanel) {
            return "right-[calc(20rem+1rem)]";
          } else {
            return "right-4";
          }
        })()
      }`}>
        {onToggleWorkflowPanel && (
          <Button
            onClick={onToggleWorkflowPanel}
            size="icon"
            variant="ghost"
            className="rounded-full h-10 w-10 shadow-md bg-white hover:bg-gray-50"
          >
            {showWorkflowPanel ? (
              <X className="h-4 w-4" />
            ) : (
              <History className="h-4 w-4" />
            )}
            <span className="sr-only">{showWorkflowPanel ? "Close Workflow Panel" : "Open Workflow Panel"}</span>
          </Button>
        )}
        
        <Button
          onClick={onClose}
          size="icon"
          variant="ghost"
          className="rounded-full h-10 w-10 shadow-md bg-white hover:bg-gray-50"
        >
          {isOpen ? (
            <X className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
          <span className="sr-only">{isOpen ? "Close Node Panel" : "Open Node Panel"}</span>
        </Button>
      </div>

      <div
        className={`absolute top-0 right-0 h-full w-64 bg-white shadow-lg transition-transform duration-300 border-l ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex flex-col h-full">
          <div className="p-4 border-b">
            <div className="flex items-center justify-between">
              <h3 className="text-md font-semibold">Available Nodes</h3>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {nodeCategories.length === 0 ? (
              <div className="text-sm text-gray-500">
                Loading node categories...
              </div>
            ) : (
              nodeCategories.map((category) => {
                const nodesInCategory =
                  nodeRegistry.getNodeTypesByCategory(category);
                if (nodesInCategory.length === 0) return null;

                return (
                  <div key={category} className="mb-4">
                    <h4 className="text-sm font-medium capitalize mb-2">
                      {categoryLabel[category]
                        ? categoryLabel[category]
                        : category}
                    </h4>
                    <div className="space-y-3">
                      {nodesInCategory.map((nodeType) => {
                        const isDragging = draggingNodeType === nodeType.type;
                        const color = getNodeColor(category);

                        return (
                          <Card
                            key={nodeType.type}
                            className={`cursor-pointer transition-all duration-200 select-none ${
                              isDragging
                                ? "opacity-50 scale-95 border-2 border-dashed border-blue-400 bg-blue-50"
                                : "hover:bg-gray-50 hover:shadow-md"
                            }`}
                            onClick={() => onAddNode(nodeType.type)}
                            draggable={true}
                            onDragStart={(event) =>
                              onDragStart(event, nodeType.type)
                            }
                            onDragEnd={onDragEnd}
                          >
                            <CardHeader className="p-3 pb-1 flex flex-row items-center gap-2">
                              {renderIcon(nodeType.icon, `h-4 w-4 ${color}`)}
                              <CardTitle className="text-sm font-medium">
                                {nodeType.label}
                              </CardTitle>
                            </CardHeader>
                            <CardContent className="p-3 pt-1">
                              <CardDescription className="text-xs">
                                {nodeType.description}
                              </CardDescription>
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default NodePanel;
