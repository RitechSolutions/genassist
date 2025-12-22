import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { LLMModelNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { getLLMProvider } from "@/services/llmProviders";
import { LLModelDialog } from "../../nodeDialogs/LLModelDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const LL_MODEL_NODE_TYPE = "llmModelNode";

const LLModelNode: React.FC<NodeProps<LLMModelNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(LL_MODEL_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const color = getNodeColor(nodeDefinition.category);

  useEffect(() => {
    if (data.providerId) {
      getLLMProvider(data.providerId).then((provider) => {
        if (provider) {
          setProviderName(
            `${provider.name} (${provider.llm_model_provider} - ${provider.llm_model})`
          );
        }
      });
    }
  }, [data.providerId]);

  // Handle updates from the dialog
  const onUpdate = (updatedData: LLMModelNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "LLM Provider",
      value: providerName,
      placeholder: "None selected",
    },
    {
      label: "Mode",
      value: `${data.type} (${data.memory ? "with" : "without"} memory)`,
    },
    { label: "System Prompt", value: data.systemPrompt },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition.icon}
        title={data.name || nodeDefinition.label}
        subtitle={nodeDefinition.shortDescription}
        color={color}
        nodeType="llmModelNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <LLModelDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={LL_MODEL_NODE_TYPE}
      />
    </>
  );
};

export default LLModelNode;
