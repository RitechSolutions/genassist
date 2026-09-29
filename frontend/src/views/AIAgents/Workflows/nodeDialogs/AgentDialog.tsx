import React from "react";
import { AgentNodeData, BaseLLMNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { ModelConfiguration } from "../components/ModelConfiguration";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { useNodeDialogState } from "./useNodeDialogState";

type AgentDialogProps = BaseNodeDialogProps<AgentNodeData, BaseLLMNodeData>;

export const AgentDialog: React.FC<AgentDialogProps> = (props) => {
  const { onClose, data } = props;

  const { values, setValues, merged, handleSave } = useNodeDialogState<
    BaseLLMNodeData,
    BaseLLMNodeData
  >(props, () => data);

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
      data={merged}
    >
      <ModelConfiguration
        id="agent-config"
        config={values}
        onConfigChange={setValues}
        typeSelect="agent"
      />
    </NodeConfigPanel>
  );
};
