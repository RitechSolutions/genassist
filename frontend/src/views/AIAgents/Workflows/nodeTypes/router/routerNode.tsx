import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { RouterNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { RouterDialog } from "../../nodeDialogs/RouterDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { getLLMProvider } from "@/services/llmProviders";

export const ROUTER_NODE_TYPE = "routerNode";

function isSmartModeOn(data: RouterNodeData): boolean {
  const v = data.smartModeEnabled;
  if (v === true) return true;
  if (v === false || v === undefined || v === null) return false;
  if (typeof v === "string") return v.trim().toLowerCase() === "true";
  return false;
}

const RouterNode: React.FC<NodeProps<RouterNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(ROUTER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const smart = isSmartModeOn(data);

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

  const onUpdate = (updatedData: RouterNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const nodeContent: NodeContentRow[] = smart
    ? [
        { label: "Mode", value: "Smart (LLM)", isSelection: true },
        {
          label: "LLM Provider",
          value: providerName || "—",
        },
        {
          label: "Routing prompt",
          value: data.smartPrompt,
        },
        {
          label: "Fallback",
          value: data.fallbackRoute === "true" ? "true" : "false",
          isSelection: true,
        },
      ]
    : [
        { label: "First Value", value: data.first_value },
        {
          label: "Compare Condition",
          value: data.compare_condition,
          isSelection: true,
        },
        { label: "Second Value", value: data.second_value },
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
        nodeType={ROUTER_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <RouterDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={ROUTER_NODE_TYPE}
      />
    </>
  );
};

export default RouterNode;
