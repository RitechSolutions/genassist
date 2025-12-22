import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { PreprocessingNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { PreprocessingDialog } from "../../nodeDialogs/training/PreprocessingDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";

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

  const nodeContent: NodeContentRow[] = [
    { label: "Python Script", value: data.pythonCode, isCode: true },
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
        iconName="settings"
        title={data.name || "Data Preprocessing"}
        subtitle="Transform and clean training data"
        color={color}
        nodeType={PREPROCESSING_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

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
