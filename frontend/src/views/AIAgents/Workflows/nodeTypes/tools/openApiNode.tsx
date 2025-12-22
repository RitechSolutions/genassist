import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { OpenApiNodeData } from "../../types/nodes";
import nodeRegistry from "../../registry/nodeRegistry";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getNodeColor } from "../../utils/nodeColors";
import { getAllLLMProviders } from "@/services/llmProviders";
import { NodeContentRow } from "../nodeContent";
import BaseNodeContainer from "../BaseNodeContainer";
import { OpenApiDialog } from "../../nodeDialogs/OpenApiDialog";

export const OPEN_API_NODE_TYPE = "openApiNode";

const OpenApiNode: React.FC<NodeProps<OpenApiNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(OPEN_API_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    []
  );

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const providers = await getAllLLMProviders();
        setAvailableProviders(providers.filter((p) => p.is_active === 1));
      } catch (err) {
        // ignore
      }
    };

    loadProviders();
  }, []);

  const onUpdate = (updatedData: OpenApiNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<OpenApiNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const selectedProvider = availableProviders.find(
    (p) => p.id === data.providerId
  );

  const nodeContent: NodeContentRow[] = [
    {
      label: "LLM Provider",
      value: selectedProvider?.name,
      placeholder: "None selected",
    },
    {
      label: "Specification File",
      value: data.originalFileName,
      placeholder: "None uploaded",
    },
    { label: "Query", value: data.query },
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
        nodeType={OPEN_API_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <OpenApiDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={OPEN_API_NODE_TYPE}
      />
    </>
  );
};

export default OpenApiNode;
