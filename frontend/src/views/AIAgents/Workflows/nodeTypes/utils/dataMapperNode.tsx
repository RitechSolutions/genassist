import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { DataMapperDialog } from "../../nodeDialogs/DataMapperDialog";
import { DataMapperNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";

export const DATA_MAPPER_NODE_TYPE = "dataMapperNode";
const DataMapperNode: React.FC<NodeProps<DataMapperNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(DATA_MAPPER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<DataMapperNodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Python Script",
      value: data.pythonScript,
      isCode: true,
    },
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
        nodeType={DATA_MAPPER_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <DataMapperDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={DATA_MAPPER_NODE_TYPE}
      />
    </>
  );
};

export default DataMapperNode;
