import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { SalesforceCaseNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import { SalesforceCaseDialog } from "../../nodeDialogs/SalesforceCaseDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";

export const SALESFORCE_CASE_NODE_TYPE = "salesforceCaseNode";
const SalesforceCaseNode: React.FC<NodeProps<SalesforceCaseNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(SALESFORCE_CASE_NODE_TYPE);
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

  const onUpdate = (updatedData: Partial<SalesforceCaseNodeData>) => {
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
    {
      label: "Labels",
      value: data.labels && data.labels.length > 0 ? data.labels.join(", ") : undefined,
      placeholder: "None",
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
        nodeType={SALESFORCE_CASE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <SalesforceCaseDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SALESFORCE_CASE_NODE_TYPE}
      />
    </>
  );
};

export default SalesforceCaseNode;
