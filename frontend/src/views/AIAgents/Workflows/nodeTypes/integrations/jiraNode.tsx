import { NodeProps } from "reactflow";
import { JiraNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { useState } from "react";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import nodeRegistry from "../../registry/nodeRegistry";
import { JiraDialog } from "../../nodeDialogs/JiraDialog";

export const JIRA_NODE_TYPE = "jiraNode";

const JiraNode: React.FC<NodeProps<JiraNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(JIRA_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  const onUpdate = (updatedData: JiraNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<JiraNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
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
        nodeType={JIRA_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "Configuration Vars", value: data.app_settings_id },
            { label: "Space Key", value: data.spaceKey },
            { label: "Task Name", value: data.taskName },
            { label: "Task Description", value: data.taskDescription },
          ]}
        />
      </BaseNodeContainer>

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
