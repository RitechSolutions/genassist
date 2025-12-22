import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { WhatsappNodeData } from "../../types/nodes";
import { WhatsAppDialog } from "../../nodeDialogs/WhatsAppDialog";
import { NodeContentRow } from "../nodeContent";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";

export const WHATSAPP_NODE_TYPE = "whatsappToolNode";
const WhatsAppNode: React.FC<NodeProps<WhatsappNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(WHATSAPP_NODE_TYPE);
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

  const selectedAppSettingName = appSettings.find(
    (setting) => setting.id === data.app_settings_id
  )?.name;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Configuration",
      value: selectedAppSettingName,
      placeholder: "None selected",
    },
    { label: "Recipient Number", value: data.recipient_number },
    { label: "Message", value: data.message },
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
        nodeType={WHATSAPP_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

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
