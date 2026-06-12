import React, { useEffect, useState } from "react";
import { NodeProps, useNodes, useEdges } from "reactflow";
import { VoiceAgentNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { VoiceAgentDialog } from "../../nodeDialogs/VoiceAgentDialog";
import { getAudioProvider } from "@/services/audioProviders";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const VOICE_AGENT_NODE_TYPE = "voiceAgentNode";

const VoiceAgentNode: React.FC<NodeProps<VoiceAgentNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(VOICE_AGENT_NODE_TYPE);
  const nodes = useNodes();
  const edges = useEdges();
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [providerName, setProviderName] = useState("");
  const [connectedToolsCount, setConnectedToolsCount] = useState(0);
  const color = getNodeColor(nodeDefinition.category);

  useEffect(() => {
    if (data.voiceProviderId) {
      getAudioProvider(data.voiceProviderId).then((provider) => {
        if (provider) {
          setProviderName(`${provider.name} (${provider.provider_type})`);
        }
      });
    } else {
      setProviderName("");
    }
  }, [data.voiceProviderId]);

  // Count tools connected via the input_tools handle
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
    setConnectedToolsCount(connectedToolNodes.length);
  }, [nodes, edges, id]);

  // Handle updates from the dialog
  const onUpdate = (updatedData: VoiceAgentNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Voice Provider",
      value: providerName,
      placeholder: "None selected",
    },
    {
      label: "Live Model",
      value: `${data.model || "gemini-3.1-flash-live-preview"} (${
        data.voice || "Kore"
      })`,
    },
    {
      label: "Memory",
      value: data.memory ? "Enabled" : "Disabled",
    },
    {
      label: "Tools",
      value:
        connectedToolsCount === 0 ? "" : `${connectedToolsCount} connected`,
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
        nodeType="voiceAgentNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <VoiceAgentDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={VOICE_AGENT_NODE_TYPE}
      />
    </>
  );
};

export default VoiceAgentNode;
