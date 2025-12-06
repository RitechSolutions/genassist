import React, { useEffect, useState } from "react";
import { ToolBuilderNodeData, ToolBaseNodeData } from "../types/nodes";
import { Save } from "lucide-react";
import { ToolDefinitionSection } from "./ToolDefinitionSection";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { NodeSchema } from "../types/schemas";

interface ToolBuilderDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: ToolBuilderNodeData;
  onUpdate: (data: ToolBuilderNodeData) => void;
  availableParams?: NodeSchema;
}

export const ToolBuilderDialog: React.FC<ToolBuilderDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
  availableParams,
}) => {
  const [toolDefinition, setToolDefinition] = useState<ToolBaseNodeData>({
    name: data.name || "Tool Builder",
    description: data.description || "Custom tool for parameter forwarding",
    inputSchema: data.inputSchema || {},
  });

  useEffect(() => {
    setToolDefinition({
      name: data.name || "Tool Builder",
      description: data.description || "Custom tool for parameter forwarding",
      inputSchema: data.inputSchema || {},
    });
  }, [isOpen]);

  // Handle save
  const handleSave = () => {
    onUpdate({
      ...data,
      name: toolDefinition.name,
      description: toolDefinition.description,
      inputSchema: toolDefinition.inputSchema,
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Tool Builder</DialogTitle>
          <DialogDescription>
            Configure the tool name, description, and parameters
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <ToolDefinitionSection
            toolDefinition={toolDefinition}
            onToolDefinitionChange={setToolDefinition}
          />
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}; 