import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { StateIONodeData } from "../../types/nodes";
import { StateIONodeDialog } from "../../nodeDialogs/StateIONodeDialog";

export const STATE_IO_NODE_TYPE = "stateIONode";

const StateIONode: React.FC<NodeProps<StateIONodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(STATE_IO_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<StateIONodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate: StateIONodeData = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const stateVarsCount = Object.keys(data.stateVariables || {}).length;

  const nodeContent: NodeContentRow[] = [
    {
      label: "State variables",
      value:
        stateVarsCount === 0
          ? "No explicit state variables configured"
          : `${stateVarsCount} configured`,
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
        nodeType={STATE_IO_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <StateIONodeDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={STATE_IO_NODE_TYPE}
      />
    </>
  );
};

export default StateIONode;

