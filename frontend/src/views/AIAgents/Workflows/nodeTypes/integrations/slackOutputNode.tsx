import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColor } from "../../utils/nodeColors";
import { SlackOutputNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { SlackOutputDialog } from "../../nodeDialogs/SlackOutputDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const SLACK_OUTPUT_NODE_TYPE = "slackMessageNode";

const SlackOutputNode: React.FC<NodeProps<SlackOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SLACK_OUTPUT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<SlackOutputNodeData>) => {
    const inputSchema = createSimpleSchema({
      text: { type: "string", required: true },
    });

    const outputSchema = createSimpleSchema({
      status: { type: "number", required: true },
      data: { type: "any", required: true },
    });

    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
        inputSchema,
        outputSchema,
      });
    }
  };

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
        nodeType={SLACK_OUTPUT_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Body */}
        <NodeContent
          data={[
            { label: "Configuration Vars", value: data.app_settings_id },
            { label: "Channel ID", value: data.channel },
            { label: "Message", value: data.message },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <SlackOutputDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SLACK_OUTPUT_NODE_TYPE}
      />
    </>
  );
};

export default SlackOutputNode;
