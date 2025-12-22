import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { APIToolNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { APIToolDialog } from "../../nodeDialogs/APIToolDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const API_TOOL_NODE_TYPE = "apiToolNode";
const APIToolNode: React.FC<NodeProps<APIToolNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(API_TOOL_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: APIToolNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<APIToolNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Endpoint", value: data.endpoint },
    { label: "Method", value: data.method },
    {
      label: "Variables",
      value: extractDynamicVariablesAsRecord(JSON.stringify(data)),
      areDynamicVars: true,
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
        nodeType="apiToolNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <APIToolDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={API_TOOL_NODE_TYPE}
      />
    </>
  );
};

export default APIToolNode;
