import React, { useState, useEffect } from "react";
import { BaseLLMNodeData, LLMModelNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { ModelConfiguration } from "../components/ModelConfiguration";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";

type LLModelDialogProps = BaseNodeDialogProps<
  LLMModelNodeData,
  BaseLLMNodeData
>;

export const LLModelDialog: React.FC<LLModelDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [config, setConfig] = useState<BaseLLMNodeData>(data);

  // Reset state when the dialog is opened to reflect the current node data
  useEffect(() => {
    if (isOpen) {
      setConfig(data);
    }
  }, [isOpen, data]);

  // Handle saving the changes
  const handleSave = () => {
    onUpdate({
      ...data,
      ...config,
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
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        ...config,
      }}
    >
      <ModelConfiguration
        id="agent-config"
        config={config}
        onConfigChange={setConfig}
        typeSelect="model"
      />
    </NodeConfigPanel>
  );
};
