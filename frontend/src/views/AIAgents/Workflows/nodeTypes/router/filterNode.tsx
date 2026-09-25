import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { FilterNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { FilterDialog } from "../../nodeDialogs/FilterDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { describeFilterCondition, filterOperatorIsText } from "./filterConditions";

export const FILTER_NODE_TYPE = "filterNode";

const FilterNode: React.FC<NodeProps<FilterNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(FILTER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: FilterNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const condition = describeFilterCondition(data.operator, data.value);
  const caseNote =
    filterOperatorIsText(data.operator) && data.caseSensitive ? " (case sensitive)" : "";

  const nodeContent: NodeContentRow[] = [
    { label: "Field", value: data.field },
    { label: "Continues if", value: `${condition}${caseNote}` },
    {
      label: "Otherwise",
      value: data.stopMessage?.trim()
        ? `Stops and replies: ${data.stopMessage.trim()}`
        : "Stops the branch",
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
        nodeType={FILTER_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <FilterDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={FILTER_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(FilterNode);
