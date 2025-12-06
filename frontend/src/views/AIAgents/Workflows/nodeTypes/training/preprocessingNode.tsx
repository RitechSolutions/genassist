import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { PreprocessingNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { PreprocessingDialog } from "../../nodeDialogs/training/PreprocessingDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const PREPROCESSING_NODE_TYPE = "preprocessingNode";

const PreprocessingNode: React.FC<NodeProps<PreprocessingNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(PREPROCESSING_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  const onUpdate = (updatedData: PreprocessingNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<PreprocessingNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const codePreview = data.pythonCode
    ? data.pythonCode.length > 100
      ? `${data.pythonCode.substring(0, 100)}...`
      : data.pythonCode
    : "No preprocessing code set";

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="settings"
        title={data.name || "Data Preprocessing"}
        subtitle="Transform and clean training data"
        color={color}
        nodeType={PREPROCESSING_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "File URL", value: data.fileUrl },
            { label: "Python Code", value: codePreview },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <PreprocessingDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={PREPROCESSING_NODE_TYPE}
      />
    </>
  );
};

export default PreprocessingNode;
