import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import nodeRegistry from "../../registry/nodeRegistry";
import { WhatsappNodeData } from "../../types/nodes";
import { WhatsAppDialog } from "../../nodeDialogs/WhatsAppDialog";

export const WHATSAPP_NODE_TYPE = "whatsappToolNode";
const WhatsAppNode: React.FC<NodeProps<WhatsappNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(WHATSAPP_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<WhatsappNodeData>) => {
    const inputSchema = createSimpleSchema({
      text_msg: { type: "string", required: true },
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
        nodeType={WHATSAPP_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Body */}
        <NodeContent
          data={[
            {
              label: "Configuration Vars",
              value: data.app_settings_id,
            },
            {
              label: "Recipient Number",
              value: data.recipient_number,
            },
            {
              label: "Message",
              value: data.message,
            },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <WhatsAppDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={WHATSAPP_NODE_TYPE}
      />
    </>
  );
};

export default WhatsAppNode;
