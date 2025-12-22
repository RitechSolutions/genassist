import { NodeProps } from "reactflow";
import { JiraNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { useEffect, useState } from "react";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { JiraDialog } from "../../nodeDialogs/JiraDialog";
import { NodeContentRow } from "../nodeContent";
import { AppSetting } from "@/interfaces/app-setting.interface";
import { getAllAppSettings } from "@/services/appSettings";

export const JIRA_NODE_TYPE = "jiraNode";

const JiraNode: React.FC<NodeProps<JiraNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(JIRA_NODE_TYPE);
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

  const onUpdate = (updatedData: JiraNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<JiraNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
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
    { label: "Space Key", value: data.spaceKey },
    { label: "Task Name", value: data.taskName },
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
        nodeType={JIRA_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <JiraDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={JIRA_NODE_TYPE}
      />
    </>
  );
};

export default JiraNode;
