import React, { useState, useRef, useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/tabs";
import { HelpCircle, Search } from "lucide-react";
import { Input } from "@/components/input";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { getNodeColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";

interface NodePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onAddNode: (nodeType: string) => void;
}

const NodePanel: React.FC<NodePanelProps> = ({
  isOpen,
  onClose,
  onAddNode,
}) => {
  const nodeCategories = nodeRegistry.getAllCategories();
  const [draggingNodeType, setDraggingNodeType] = useState<string | null>(null);
  const dragPreviewContainerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<string>("available");
  const [searchQuery, setSearchQuery] = useState<string>("");

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

  // Filter nodes based on search query
  const filteredNodesByCategory = useMemo(() => {
    if (!searchQuery.trim()) {
      return null; // Return null when no search, will render all categories normally
    }

    const query = searchQuery.toLowerCase();
    const filtered: { [key: string]: any[] } = {};

    nodeCategories.forEach((category) => {
      const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
      const matchingNodes = nodesInCategory.filter(
        (node) =>
          node.label.toLowerCase().includes(query) ||
          node.description.toLowerCase().includes(query)
      );

      if (matchingNodes.length > 0) {
        filtered[category] = matchingNodes;
      }
    });

    return filtered;
  }, [searchQuery, nodeCategories]);

  // Render node categories
  const renderNodeCategories = () => {
    if (nodeCategories.length === 0) {
      return (
        <div className="text-sm text-muted-foreground p-4">
          Loading node categories...
        </div>
      );
    }

    // If searching, use filtered results
    if (searchQuery.trim() && filteredNodesByCategory) {
      const categories = Object.keys(filteredNodesByCategory);
      
      if (categories.length === 0) {
        return (
          <div className="text-sm text-muted-foreground p-4 text-center">
            No nodes found matching "{searchQuery}"
          </div>
        );
      }

      return categories.map((category) => {
        const nodesInCategory = filteredNodesByCategory[category];
        return renderCategorySection(category, nodesInCategory);
      });
    }

    // Otherwise, render all categories
    return nodeCategories.map((category) => {
      const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
      if (nodesInCategory.length === 0) return null;
      return renderCategorySection(category, nodesInCategory);
    });
  };

  // Render a single category section
  const renderCategorySection = (category: string, nodesInCategory: any[]) => {
    return (
      <div key={category} className="px-4 py-2">
        <div className="flex items-center py-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase">
            {categoryLabel[category] ? categoryLabel[category] : category}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {nodesInCategory.map((nodeType) => {
            const isDragging = draggingNodeType === nodeType.type;
            const color = getNodeColor(category);

            return (
              <div
                key={nodeType.type}
                className={`bg-background border border-border rounded-lg p-4 cursor-pointer transition-all duration-200 select-none ${
                  isDragging
                    ? "opacity-50 scale-95 border-2 border-dashed border-blue-400 bg-blue-50"
                    : "hover:bg-muted/50 hover:shadow-sm"
                }`}
                onClick={() => onAddNode(nodeType.type)}
                draggable={true}
                onDragStart={(event) => onDragStart(event, nodeType.type)}
                onDragEnd={onDragEnd}
              >
                <div className="flex gap-2 items-start">
                  <div className="shrink-0 w-5 h-5">
                    {renderIcon(nodeType.icon, `h-5 w-5 ${color}`)}
                  </div>
                  <div className="flex-1 flex flex-col gap-1 min-w-0">
                    <div className="flex gap-2 items-center w-full">
                      <p className="flex-1 text-sm font-semibold text-accent-foreground min-w-0">
                        {nodeType.label}
                      </p>
                      <HelpCircle className="shrink-0 h-4 w-4 text-muted-foreground" />
                    </div>
                    <p className="text-sm text-muted-foreground w-full">
                      {nodeType.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <>
      <div
        ref={dragPreviewContainerRef}
        className="fixed pointer-events-none"
        style={{ visibility: "hidden" }}
      ></div>

      <div
        className={`fixed top-2 right-2 h-[calc(100vh-1rem)] w-80 bg-primary-foreground shadow-lg rounded-xl transition-transform duration-300 border ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Tabs Header */}
          <div className="p-4">
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="w-full"
            >
              <TabsList className="w-full h-10 bg-muted p-1 rounded-md">
                <TabsTrigger
                  value="available"
                  className="flex-1 text-sm font-medium rounded-lg"
                >
                  Available Nodes
                </TabsTrigger>
                <TabsTrigger
                  value="conversational"
                  className="flex-1 text-sm font-medium rounded-sm"
                >
                  Conversational
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Tabs Content */}
          <div className="flex-1 overflow-y-auto bg-background rounded-xl">
            {activeTab === "available" && (
              <div className="w-full">
                {/* Search Field */}
                <div className="px-4 pt-4 pb-2 sticky top-0 bg-background z-10">
                  <div className="relative flex items-center">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    <Input
                      type="text"
                      placeholder="Search nodes..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 h-9 text-sm w-full"
                    />
                  </div>
                </div>
                {renderNodeCategories()}
              </div>
            )}
            {activeTab === "conversational" && (
              <div className="p-4">
                <p className="text-sm text-muted-foreground">
                  Conversational nodes coming soon...
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default NodePanel;
