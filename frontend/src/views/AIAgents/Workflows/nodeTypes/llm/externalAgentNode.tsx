import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { ExternalAgentNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { ExternalAgentDialog } from "../../nodeDialogs/ExternalAgentDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const EXTERNAL_AGENT_NODE_TYPE = "externalAgentNode";

const ExternalAgentNode: React.FC<NodeProps<ExternalAgentNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(EXTERNAL_AGENT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: ExternalAgentNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const authLabel: Record<string, string> = {
    none: "No auth",
    bearer: "Bearer token",
    api_key: "API key",
    basic: "Basic auth",
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Endpoint", value: data.endpoint },
    { label: "Method", value: data.method },
    { label: "Auth", value: authLabel[data.authType] ?? data.authType },
    { label: "Message field", value: data.messageField },
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
        nodeType={EXTERNAL_AGENT_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <ExternalAgentDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={EXTERNAL_AGENT_NODE_TYPE}
      />
    </>
  );
};

export default ExternalAgentNode;