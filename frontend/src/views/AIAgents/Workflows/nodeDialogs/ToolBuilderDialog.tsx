import React, { useState, useEffect } from "react";
import { ToolBuilderNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { ToolDefinitionSection } from "../components/ToolDefinitionSection";

type ToolBuilderDialogProps = BaseNodeDialogProps<
  ToolBuilderNodeData,
  ToolBuilderNodeData
>;

export const ToolBuilderDialog: React.FC<ToolBuilderDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [toolDefinition, setToolDefinition] = useState<ToolBuilderNodeData>({
    name: data.name || "Tool Builder",
    description: data.description || "Custom tool for parameter forwarding",
    inputSchema: data.inputSchema || {},
    returnDirect: data.returnDirect || false,
  });

  useEffect(() => {
    setToolDefinition({
      ...data,
    });
  }, [isOpen, data]);

  // Handle save
  const handleSave = () => {
    onUpdate({
      ...data,
      ...toolDefinition,
    });
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        ...toolDefinition,
      }}
      showJsonState={false}
      className="max-w-4xl"
    >
      <ToolDefinitionSection
        toolDefinition={toolDefinition}
        onToolDefinitionChange={setToolDefinition}
      />
    </NodeConfigPanel>
  );
};
