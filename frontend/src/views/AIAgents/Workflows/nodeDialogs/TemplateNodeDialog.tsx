import React, { useState, useEffect } from "react";
import { TemplateNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";

type TemplateNodeDialogProps = BaseNodeDialogProps<
  TemplateNodeData,
  TemplateNodeData
>;

export const TemplateNodeDialog: React.FC<TemplateNodeDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [templateData, setTemplateData] = useState<{
    name: string;
    template: string;
  }>({
    name: data.name || "",
    template: data.template || "",
  });

  useEffect(() => {
    if (isOpen) {
      setTemplateData({
        name: data.name || "",
        template: data.template || "",
      });
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name: templateData.name,
      template: templateData.template,
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
        name: templateData.name,
        template: templateData.template,
      }}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <Input
            id="name"
            value={templateData.name}
            onChange={(e) =>
              setTemplateData({ ...templateData, name: e.target.value })
            }
            placeholder="e.g., Template"
            className="w-full"
          />
        </div>
        <div>
          <Label htmlFor="template">Template</Label>
          <DraggableTextArea
            id="template"
            value={templateData.template}
            onChange={(e) =>
              setTemplateData({ ...templateData, template: e.target.value })
            }
            placeholder="Enter your template here... Use {{session.message}} or drag variables from the left panel"
            className="h-32 font-mono text-sm"
            rows={8}
          />
        </div>
      </div>
    </NodeConfigPanel>
  );
};
