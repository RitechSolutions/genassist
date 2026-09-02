import React from "react";
import { ToolBuilderNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { ToolDefinitionSection } from "../components/ToolDefinitionSection";
import { useNodeDialogState } from "./useNodeDialogState";

type ToolBuilderDialogProps = BaseNodeDialogProps<
  ToolBuilderNodeData,
  ToolBuilderNodeData
>;

export const ToolBuilderDialog: React.FC<ToolBuilderDialogProps> = (props) => {
  const { onClose, data } = props;

  const { values, setValues, merged, handleSave } = useNodeDialogState(
    props,
    () => ({ ...data })
  );

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
      data={merged}
      showJsonState={false}
      className="max-w-4xl"
    >
      <ToolDefinitionSection
        toolDefinition={values}
        onToolDefinitionChange={setValues}
      />
    </NodeConfigPanel>
  );
};
