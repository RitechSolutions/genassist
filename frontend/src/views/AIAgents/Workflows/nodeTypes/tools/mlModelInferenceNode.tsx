import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { MLModelInferenceNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { MLModelInferenceDialog } from "../../nodeDialogs/MLModelInferenceDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const ML_MODEL_INFERENCE_NODE_TYPE = "mlModelInferenceNode";

const MLModelInferenceNode: React.FC<NodeProps<MLModelInferenceNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(ML_MODEL_INFERENCE_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  const onUpdate = (updatedData: MLModelInferenceNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<MLModelInferenceNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Count only inference parameters as draggable inputs
  const totalInputs = Object.keys(data.inferenceInputs || {}).length;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Model",
      value: data.modelName,
      placeholder: "None selected",
    },
    {
      label: "Target",
      value: "",
    },
    {
      label: "Features",
      value: "",
    },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="brain"
        title={data.modelName || data.name || "ML Model"}
        subtitle="Run ML model inference"
        color={color}
        nodeType="mlModelInferenceNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <MLModelInferenceDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={ML_MODEL_INFERENCE_NODE_TYPE}
      />
    </>
  );
};

export default MLModelInferenceNode;
