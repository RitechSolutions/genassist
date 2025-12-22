import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { ZendeskTicketNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import { ZendeskTicketDialog } from "../../nodeDialogs/ZendeskTicketDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";

export const ZENDESK_TICKET_NODE_TYPE = "zendeskTicketNode";
const ZendeskTicketNode: React.FC<NodeProps<ZendeskTicketNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(ZENDESK_TICKET_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [appSettings, setAppSettings] = useState<AppSetting[]>([]);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  useEffect(() => {
    const fetchAppSettings = async () => {
      try {
        const settings = await getAllAppSettings();
        setAppSettings(settings);
      } catch (error) {
        // ignore
      }
    };

    fetchAppSettings();
  }, []);

  const onUpdate = (updatedData: Partial<ZendeskTicketNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const selectedAppSettingName = appSettings.find(
    (setting) => setting.id === data.app_settings_id
  )?.name;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Configuration",
      value: selectedAppSettingName,
      placeholder: "None selected",
    },
    { label: "Subject", value: data.subject },
    { label: "Requester", value: data.requester_name },
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
        nodeType={ZENDESK_TICKET_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

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
