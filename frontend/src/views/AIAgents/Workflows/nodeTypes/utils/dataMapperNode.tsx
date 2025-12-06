import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { DataMapperDialog } from "../../nodeDialogs/DataMapperDialog";
import { DataMapperNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import nodeRegistry from "../../registry/nodeRegistry";

export const DATA_MAPPER_NODE_TYPE = "dataMapperNode";
const DataMapperNode: React.FC<NodeProps<DataMapperNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(DATA_MAPPER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  // Get code preview (first few lines)
  const getCodePreview = () => {
    if (!data.pythonScript) return "";
    const lines = data.pythonScript?.split("\n");
    if (lines?.length <= 3) return data.pythonScript;
    return lines?.slice(0, 3).join("\n") + "\n...";
  };

  const onUpdate = (updatedData: Partial<DataMapperNodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
    console.log("Data", data);
  };

  const getMappingPreview = () => {
    const scriptPreview =
      data.pythonScript.length > 50
        ? data.pythonScript.substring(0, 50) + "..."
        : data.pythonScript;
    return `Transform data using Python script: ${scriptPreview}`;
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
        nodeType={DATA_MAPPER_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Node content */}
        <NodeContent
          data={[
            {
              label: "Python Script",
              value: getCodePreview(),
              isMono: true,
              hasMultipleLines: true,
            },
            // {
            //   label: "Mapping Preview",
            //   value: getMappingPreview(),
            //   hasMultipleLines: false,
            // },
          ]}
        />
      </BaseNodeContainer>

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
