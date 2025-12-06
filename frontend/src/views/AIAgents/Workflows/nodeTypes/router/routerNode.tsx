import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { RouterNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { RouterDialog } from "../../nodeDialogs/RouterDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const ROUTER_NODE_TYPE = "routerNode";

const RouterNode: React.FC<NodeProps<RouterNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(ROUTER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: RouterNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const conditionText = data.compare_condition?.replace(/_/g, " ");

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
        nodeType={ROUTER_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "First Value", value: data.first_value },
            { label: "Compare Condition", value: conditionText },
            { label: "Second Value", value: data.second_value },
          ]}
        />
      </BaseNodeContainer>

      <RouterDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={ROUTER_NODE_TYPE}
      />
    </>
  );
};

export default RouterNode;
