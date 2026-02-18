import React from "react";
import {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuShortcut,
} from "@/components/context-menu";
import nodeRegistry from "@/views/AIAgents/Workflows/registry/nodeRegistry";
import { getNodeColor } from "@/views/AIAgents/Workflows/utils/nodeColors";
import { renderIcon } from "@/views/AIAgents/Workflows/utils/iconUtils";
import { Plus, Undo, Redo } from "lucide-react";

interface CanvasContextMenuProps {
  children: React.ReactNode;
  onAddNode: (nodeType: string, position: { x: number; y: number }) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  clickPosition: { x: number; y: number } | null;
}

const categoryLabels: Record<string, string> = {
  io: "I/O",
  ai: "AI",
  routing: "Routing",
  integrations: "Integrations",
  formatting: "Formatting",
  tools: "Tools",
  training: "Training",
};

const CanvasContextMenu: React.FC<CanvasContextMenuProps> = ({
  children,
  onAddNode,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  clickPosition,
}) => {
  const nodeCategories = nodeRegistry.getAllCategories();

  const handleAddNode = (nodeType: string) => {
    if (clickPosition) {
      onAddNode(nodeType, clickPosition);
    }
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        {children}
      </ContextMenuTrigger>
      <ContextMenuContent className="w-64">
        {/* Add Node Submenu */}
        <ContextMenuSub>
          <ContextMenuSubTrigger>
            <Plus className="mr-2 h-4 w-4" />
            Add Node
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-64 max-h-96 overflow-y-auto">
            {nodeCategories.map((category) => {
              const nodesInCategory = nodeRegistry.getNodeTypesByCategory(category);
              if (nodesInCategory.length === 0) return null;

              const categoryLabel = categoryLabels[category] || category;

              return (
                <ContextMenuSub key={category}>
                  <ContextMenuSubTrigger>
                    {categoryLabel}
                  </ContextMenuSubTrigger>
                  <ContextMenuSubContent className="w-64 max-h-96 overflow-y-auto">
                    {nodesInCategory.map((nodeType) => {
                      const color = getNodeColor(category);
                      return (
                        <ContextMenuItem
                          key={nodeType.type}
                          onClick={() => handleAddNode(nodeType.type)}
                          className="flex items-center gap-2"
                        >
                          <div className="shrink-0 w-4 h-4">
                            {renderIcon(nodeType.icon, `h-4 w-4 ${color}`)}
                          </div>
                          <span className="flex-1">{nodeType.label}</span>
                        </ContextMenuItem>
                      );
                    })}
                  </ContextMenuSubContent>
                </ContextMenuSub>
              );
            })}
          </ContextMenuSubContent>
        </ContextMenuSub>

        <ContextMenuSeparator />

        {/* Undo */}
        <ContextMenuItem
          onClick={onUndo}
          disabled={!canUndo}
          className="flex items-center"
        >
          <Undo className="mr-2 h-4 w-4" />
          Undo
          <ContextMenuShortcut>⌘Z</ContextMenuShortcut>
        </ContextMenuItem>

        {/* Redo */}
        <ContextMenuItem
          onClick={onRedo}
          disabled={!canRedo}
          className="flex items-center"
        >
          <Redo className="mr-2 h-4 w-4" />
          Redo
          <ContextMenuShortcut>⌘⇧Z</ContextMenuShortcut>
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
};

export default CanvasContextMenu;
