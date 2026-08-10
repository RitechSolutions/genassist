import React, { useEffect, useMemo, useState } from "react";
import { NodeProps, useEdges, useNodes } from "reactflow";
import { SubAgentMode, SubAgentNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { SubAgentDialog } from "../../nodeDialogs/SubAgentDialog";
import { getLLMProvider } from "@/services/llmProviders";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import {
  connectedToolNodes,
  countSubAgentEdges,
} from "../../utils/subAgentGraph";

export const SUB_AGENT_NODE_TYPE = "subAgentNode";

const MODE_LABELS: Record<SubAgentMode, string> = {
  single_turn: "Single Turn",
  task: "Task",
  chat: "Chat",
};

const SubAgentNode: React.FC<NodeProps<SubAgentNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SUB_AGENT_NODE_TYPE);
  const nodes = useNodes();
  const edges = useEdges();
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const color = getNodeColor(nodeDefinition.category);

  useEffect(() => {
    if (!data.providerId) {
      setProviderName("");
      return;
    }
    // Guard against a stale response landing after the provider changed
    let active = true;
    getLLMProvider(data.providerId).then((provider) => {
      if (active && provider) {
        setProviderName(
          `${provider.name} (${provider.llm_model_provider} - ${provider.llm_model})`
        );
      }
    });
    return () => {
      active = false;
    };
  }, [data.providerId]);

  const toolCount = useMemo(
    () =>
      connectedToolNodes(id, nodes, edges, nodeRegistry.getAllToolTypes())
        .length,
    [nodes, edges, id]
  );

  const subAgentCount = useMemo(() => countSubAgentEdges(id, edges), [edges, id]);

  const onUpdate = (updatedData: SubAgentNodeData) => {
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
      value: MODE_LABELS[data.mode] || data.mode,
    },
    {
      label: "Description",
      value: data.description,
      placeholder: "None set",
    },
    {
      label: "Tools",
      value: toolCount === 0 ? "" : `${toolCount} connected`,
      placeholder: "None connected",
    },
    {
      label: "Sub-agents",
      value: subAgentCount === 0 ? "" : `${subAgentCount} connected`,
      placeholder: "None connected",
    },
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
        nodeType="subAgentNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <SubAgentDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SUB_AGENT_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(SubAgentNode);
