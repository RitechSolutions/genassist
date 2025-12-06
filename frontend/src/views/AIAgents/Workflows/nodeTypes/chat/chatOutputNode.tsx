import React from "react";
import { NodeProps } from "reactflow";
import { ChatOutputNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";

export const CHAT_OUTPUT_NODE_TYPE = "chatOutputNode";
const ChatOutputNode: React.FC<NodeProps<ChatOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(CHAT_OUTPUT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  return (
    <BaseNodeContainer
      id={id}
      data={data}
      selected={selected}
      iconName={nodeDefinition.icon}
      title={data.name || nodeDefinition.label}
      subtitle={nodeDefinition.shortDescription}
      color={color}
      nodeType={CHAT_OUTPUT_NODE_TYPE}
    >
      {/* Node content */}
      <div />
    </BaseNodeContainer>
  );
};

export default ChatOutputNode;
