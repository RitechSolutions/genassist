import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { TrainModelNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { TrainModelDialog } from "../../nodeDialogs/training/TrainModelDialog";
import nodeRegistry from "../../registry/nodeRegistry";

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

  const modelTypeInfo = data.modelType
    ? getModelTypeLabel(data.modelType)
    : "Not selected";
  const targetColumnInfo = data.targetColumn || "Not specified";
  const featureColumnsInfo =
    data.featureColumns && data.featureColumns.length > 0
      ? `${data.featureColumns.length} feature(s)`
      : "No features selected";
  const validationSplitInfo = data.validationSplit
    ? `${Math.round(data.validationSplit * 100)}% validation`
    : "No split defined";
  const parametersInfo =
    data.modelParameters && Object.keys(data.modelParameters).length > 0
      ? `${Object.keys(data.modelParameters).length} parameter(s)`
      : "No parameters";

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
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "File URL", value: data.fileUrl },
            { label: "Model Type", value: modelTypeInfo },
            { label: "Target Column", value: targetColumnInfo },
            { label: "Features", value: featureColumnsInfo },
            { label: "Validation Split", value: validationSplitInfo },
            { label: "Parameters", value: parametersInfo },
          ]}
        />
      </BaseNodeContainer>

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
