import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { AggregatorNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { AggregatorDialog } from "../../nodeDialogs/AggregatorDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const AGGREGATOR_NODE_TYPE = "aggregatorNode";

const AggregatorNode: React.FC<NodeProps<AggregatorNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(AGGREGATOR_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: AggregatorNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const strategyText = data.aggregationStrategy?.replace(/_/g, " ");
  const timeoutText = data.timeoutSeconds ? `${data.timeoutSeconds}s` : "";

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
        nodeType={AGGREGATOR_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "Aggregation Strategy", value: strategyText },
            { label: "Timeout", value: timeoutText },
            { label: "Forward Template", value: data.forwardTemplate },
          ]}
        />
      </BaseNodeContainer>

      <AggregatorDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={AGGREGATOR_NODE_TYPE}
      />
    </>
  );
};

export default AggregatorNode;
