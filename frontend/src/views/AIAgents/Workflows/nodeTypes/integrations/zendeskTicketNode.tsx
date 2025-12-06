import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { ZendeskTicketNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { ZendeskTicketDialog } from "../../nodeDialogs/ZendeskTicketDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const ZENDESK_TICKET_NODE_TYPE = "zendeskTicketNode";
const ZendeskTicketNode: React.FC<NodeProps<ZendeskTicketNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(ZENDESK_TICKET_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<ZendeskTicketNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
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
        nodeType={ZENDESK_TICKET_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "Configuration Vars", value: data.app_settings_id },
            { label: "Subject", value: data.subject },
            { label: "Description", value: data.description },
            { label: "Requester Name", value: data.requester_name },
            { label: "Requester Email", value: data.requester_email },
            { label: "Tags", value: data.tags?.join(", ") },
          ]}
        />
      </BaseNodeContainer>

      <ZendeskTicketDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={ZENDESK_TICKET_NODE_TYPE}
      />
    </>
  );
};

export default ZendeskTicketNode;
