import React, { useEffect, useState, useCallback } from "react";
import { NodeProps, useNodes, useEdges } from "reactflow";
import { AgentNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { AgentDialog } from "../../nodeDialogs/AgentDialog";
import { getLLMProvider } from "@/services/llmProviders";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

interface ToolNodeData {
  name?: string;
  description?: string;
}
export const AGENT_NODE_TYPE = "agentNode";

const AgentNode: React.FC<NodeProps<AgentNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(AGENT_NODE_TYPE);
  const nodes = useNodes();
  const edges = useEdges();
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const [availableTools, setAvailableTools] = useState<
    Array<{
      id: string;
      name: string;
      description: string;
      category: string;
    }>
  >([]);
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

  // Get available tools from connected nodes
  useEffect(() => {
    const connectedToolNodes = nodes.filter(
      (node) =>
        nodeRegistry.getAllToolTypes().includes(node.type) &&
        edges.some(
          (edge) =>
            edge.target === id &&
            edge.source === node.id &&
            edge.targetHandle === "input_tools"
        )
    );

    const tools = connectedToolNodes.map((node) => {
      const nodeData = node.data as ToolNodeData;
      return {
        id: node.id,
        name: nodeData?.name || "Unnamed Tool",
        description: nodeData?.description || "No description available",
        category: node.type, // Use node.type instead of node.category
      };
    });

    setAvailableTools(tools);
  }, [nodes, edges, id]);

  // Get available tools from connected nodes
  const getAvailableTools = useCallback(() => {
    return availableTools;
  }, [availableTools]);

  // Handle updates from the dialog
  const onUpdate = (updatedData: AgentNodeData) => {
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
      label: "Agent Type",
      value: `${data.type} (${data.memory ? "with" : "without"} memory)`,
    },
    {
      label: "Tools",
      value:
        availableTools.length === 0 ? "" : `${availableTools.length} connected`,
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
        nodeType="agentNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <AgentDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={AGENT_NODE_TYPE}
      />
    </>
  );
};

export default AgentNode;
