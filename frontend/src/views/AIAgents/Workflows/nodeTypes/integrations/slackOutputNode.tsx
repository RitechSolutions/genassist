import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { createSimpleSchema } from "../../types/schemas";
import { getNodeColor } from "../../utils/nodeColors";
import { SlackOutputNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import { SlackOutputDialog } from "../../nodeDialogs/SlackOutputDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";

export const SLACK_OUTPUT_NODE_TYPE = "slackMessageNode";

const SlackOutputNode: React.FC<NodeProps<SlackOutputNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SLACK_OUTPUT_NODE_TYPE);
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

  const selectedAppSettingName = appSettings.find(
    (setting) => setting.id === data.app_settings_id
  )?.name;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Configuration",
      value: selectedAppSettingName,
      placeholder: "None selected",
    },
    { label: "Channel ID", value: data.channel },
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
        nodeType={SLACK_OUTPUT_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

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
