import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { ToolBuilderNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { ToolBuilderDialog } from "../../nodeDialogs/ToolBuilderDialog";
import { convertSchemaToParams } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";

export const TOOL_BUILDER_NODE_TYPE = "toolBuilderNode";
const ToolBuilderNode: React.FC<NodeProps<ToolBuilderNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(TOOL_BUILDER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: ToolBuilderNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<ToolBuilderNodeData> = {
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
        nodeType="toolBuilderNode"
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Node content */}
        <NodeContent
          data={[
            { label: "Description", value: data.description },
            {
              label: "Return data directly as agent output",
              value: data.returnDirect ? "Yes" : "No",
            },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <ToolBuilderDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TOOL_BUILDER_NODE_TYPE}
      />
    </>
  );
};

export default ToolBuilderNode;
