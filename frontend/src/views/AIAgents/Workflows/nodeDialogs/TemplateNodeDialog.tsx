import React from "react";
import { TemplateNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { useNodeDialogState } from "./useNodeDialogState";

type TemplateNodeDialogProps = BaseNodeDialogProps<
  TemplateNodeData,
  TemplateNodeData
>;

export const TemplateNodeDialog: React.FC<TemplateNodeDialogProps> = (
  props
) => {
  const { onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      template: data.template || "",
    })
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
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="e.g., Template"
            className="w-full"
          />
        </div>
        <div>
          <Label htmlFor="template">Template</Label>
          <DraggableTextArea
            id="template"
            value={values.template}
            onChange={(e) => setField("template", e.target.value)}
            placeholder="Enter your template here... Use {{session.message}} or drag variables from the left panel"
            size="code"
            className="font-mono text-sm"
          />
        </div>
      </div>
    </NodeConfigPanel>
  );
};
