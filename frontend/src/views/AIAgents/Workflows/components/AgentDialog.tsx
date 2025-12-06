import React, { useState, useEffect } from "react";
import { AgentNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ModelConfig, ModelConfiguration } from "./ModelConfiguration";

interface AgentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: AgentNodeData;
  onUpdate: (data: AgentNodeData) => void;
}

export const AgentDialog: React.FC<AgentDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [config, setConfig] = useState<ModelConfig>({
    providerId: data.providerId,
    agentType: data.agentType,
    memory: data.memory,
  });

  // Reset state when the dialog is opened to reflect the current node data
  useEffect(() => {
    if (isOpen) {
      setConfig({
        providerId: data.providerId,
        agentType: data.agentType,
        memory: data.memory,
      });
    }
  }, [isOpen, data]);

  // Handle saving the changes
  const handleSave = () => {
    onUpdate({
      ...data,
      ...config,
      name: "Agent",
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Agent</DialogTitle>
          <DialogDescription>
            Configure the core AI agent settings, including the model provider,
            agent type, and memory.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <ModelConfiguration
            id={data.id}
            config={config}
            onConfigChange={setConfig}
            typeSelect={true}
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
