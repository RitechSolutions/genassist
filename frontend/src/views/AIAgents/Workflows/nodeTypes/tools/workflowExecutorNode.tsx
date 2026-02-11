import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { WorkflowExecutorNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { WorkflowExecutorDialog } from "../../nodeDialogs/WorkflowExecutorDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const WORKFLOW_EXECUTOR_NODE_TYPE = "workflowExecutorNode";
const WorkflowExecutorNode: React.FC<NodeProps<WorkflowExecutorNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(WORKFLOW_EXECUTOR_NODE_TYPE);
  const color = getNodeColor(nodeDefinition?.category || "tools");
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: WorkflowExecutorNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<WorkflowExecutorNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Workflow", value: data.workflowName || "Not selected" },
    {
      label: "Variables",
      value: extractDynamicVariablesAsRecord(JSON.stringify(data.inputParameters || {})),
      areDynamicVars: true,
    },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition?.icon || "Workflow"}
        title={data.name || nodeDefinition?.label || "Workflow Executor"}
        subtitle={nodeDefinition?.shortDescription}
        color={color}
        nodeType="workflowExecutorNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <WorkflowExecutorDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={WORKFLOW_EXECUTOR_NODE_TYPE}
      />
    </>
  );
};

export default WorkflowExecutorNode;
