import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { TrainModelNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { TrainModelDialog } from "../../nodeDialogs/training/TrainModelDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const TRAIN_MODEL_NODE_TYPE = "trainModelNode";

const TrainModelNode: React.FC<NodeProps<TrainModelNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(TRAIN_MODEL_NODE_TYPE);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  const onUpdate = (updatedData: TrainModelNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<TrainModelNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const getModelTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      xgboost: "XGBoost",
      random_forest: "Random Forest",
      linear_regression: "Linear Regression",
      logistic_regression: "Logistic Regression",
      neural_network: "Neural Network",
      other: "Other",
    };
    return labels[type] || type;
  };

  const modelTypeInfo = data.modelType ? getModelTypeLabel(data.modelType) : "";

  const numberOfFeatures = data.featureColumns ? data.featureColumns.length : 0;

  const nodeContent: NodeContentRow[] = [
    { label: "Model Type", value: modelTypeInfo },
    { label: "Target", value: data.targetColumn },
    {
      label: "Features",
      value:
        numberOfFeatures === 1
          ? "1 feature selected"
          : numberOfFeatures > 1
          ? `${numberOfFeatures} features selected`
          : "",
      placeholder: "None selected",
    },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="brain"
        title={data.name || "Train Model"}
        subtitle="Train machine learning model"
        color={color}
        nodeType={TRAIN_MODEL_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <TrainModelDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TRAIN_MODEL_NODE_TYPE}
      />
    </>
  );
};

export default TrainModelNode;
