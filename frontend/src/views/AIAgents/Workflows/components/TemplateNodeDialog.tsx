import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import DynamicTemplateInput from "./DynamicTemplateInput";
import { TemplateNodeData } from "../types/nodes";
import { NodeSchema } from "../types/schemas";

interface TemplateNodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: TemplateNodeData;
  onUpdate: (template: string, inputSchema: NodeSchema) => void;
}

export const TemplateNodeDialog: React.FC<TemplateNodeDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [templateData, setTemplateData] = useState<{
    template: string;
    inputSchema: NodeSchema;
  }>({
    template: data.template || "",
    inputSchema: data.inputSchema || {},
  });

  useEffect(() => {
    if (isOpen) {
      setTemplateData({
        template: data.template || "Hello, {{user_query}}!",
        inputSchema: data.inputSchema || {},
      });
    }
  }, [isOpen, data]);

  const handleTemplateInputChange = (data: {
    template: string;
    fields: string[];
    inputSchema: NodeSchema;
  }) => {
    setTemplateData({ template: data.template, inputSchema: data.inputSchema });
  };

  const handleSave = () => {
    onUpdate(templateData.template, templateData.inputSchema);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Edit Prompt Template</DialogTitle>
          <DialogDescription>
            Modify the prompt template by using dynamic inputs if necessary
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <DynamicTemplateInput
            initialTemplate={templateData.template}
            onChange={handleTemplateInputChange}
            height="250px"
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
