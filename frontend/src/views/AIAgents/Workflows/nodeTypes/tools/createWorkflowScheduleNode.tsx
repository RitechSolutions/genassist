import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { CreateWorkflowScheduleNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { CreateWorkflowScheduleDialog } from "../../nodeDialogs/CreateWorkflowScheduleDialog";
import { getAgentConfigsList } from "@/services/api";
import { AgentListItem } from "@/interfaces/ai-agent.interface";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const CREATE_WORKFLOW_SCHEDULE_NODE_TYPE = "createWorkflowScheduleNode";

const CreateWorkflowScheduleNode: React.FC<
  NodeProps<CreateWorkflowScheduleNodeData>
> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(
    CREATE_WORKFLOW_SCHEDULE_NODE_TYPE
  );
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [agents, setAgents] = useState<AgentListItem[]>([]);

  const color = getNodeColor(nodeDefinition.category);

  useEffect(() => {
    const loadAgents = async () => {
      try {
        const res = await getAgentConfigsList(1, 100);
        setAgents(res.items);
      } catch {
        // ignore
      }
    };
    loadAgents();
  }, []);

  const onUpdate = (updatedData: CreateWorkflowScheduleNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const agentName =
    agents.find((a) => a.id === data.agentId)?.name || data.agentId || "";

  const nodeContent: NodeContentRow[] = [
    { label: "Workflow", value: agentName, placeholder: "None selected" },
    { label: "Schedule", value: data.cronSchedule },
    { label: "Active", value: data.isActive === false ? "No" : "Yes" },
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
        nodeType={CREATE_WORKFLOW_SCHEDULE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <CreateWorkflowScheduleDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={CREATE_WORKFLOW_SCHEDULE_NODE_TYPE}
      />
    </>
  );
};

export default CreateWorkflowScheduleNode;
