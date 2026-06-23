import React from "react";
import { NodeProps } from "reactflow";
import { FinalizeConversationNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";

export const FINALIZE_CONVERSATION_NODE_TYPE = "finalizeConversationNode";

const FinalizeConversationNode: React.FC<
  NodeProps<FinalizeConversationNodeData>
> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(
    FINALIZE_CONVERSATION_NODE_TYPE
  );
  const color = getNodeColor(nodeDefinition?.category || "io");

  return (
    <BaseNodeContainer
      id={id}
      data={data}
      selected={selected}
      iconName={nodeDefinition?.icon || "MessageCircle"}
      title={data.name || nodeDefinition?.label || "End Conversation"}
      subtitle={
        nodeDefinition?.shortDescription || "Finalize the active conversation"
      }
      color={color}
      nodeType={FINALIZE_CONVERSATION_NODE_TYPE}
    >
      {/* Node content */}
      <div />
    </BaseNodeContainer>
  );
};

export default FinalizeConversationNode;
