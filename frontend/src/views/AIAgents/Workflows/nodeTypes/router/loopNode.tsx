import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { LoopNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { LoopDialog } from "../../nodeDialogs/LoopDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { describeFilterCondition } from "./filterConditions";
import { LOOP_NODE_TYPE } from "../../utils/loopGraph";
import { DEFAULT_LOOP_MODE, defaultMaxIterations, LOOP_MODE_LABELS } from "./loopConfig";

const LoopNode: React.FC<NodeProps<LoopNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(LOOP_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: LoopNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const mode = data.mode ?? DEFAULT_LOOP_MODE;
  const hasStop = Boolean(data.stopField?.trim());
  const stop = hasStop
    ? `${data.stopField} ${describeFilterCondition(data.stopOperator, data.stopValue).toLowerCase()}`
    : "";

  const nodeContent: NodeContentRow[] = [
    { label: "Mode", value: LOOP_MODE_LABELS[mode], isSelection: true },
    ...(mode === "forEach"
      ? [
          {
            label: "Items",
            value:
              (data.batchSize ?? 1) > 1
                ? `${data.items ?? ""} (in batches of ${data.batchSize})`
                : data.items,
          },
        ]
      : []),
    {
      label: mode === "forEach" ? "Stops early when" : "Repeats until",
      value: stop || (mode === "forEach" ? "Never (runs every item)" : "The maximum is reached"),
    },
    {
      label: "Maximum iterations",
      value: String(data.maxIterations || defaultMaxIterations(mode)),
    },
    ...(data.delaySeconds
      ? [
          {
            label: "Wait between passes",
            value: `${data.delaySeconds}s${data.delayBackoff ? ", doubling" : ""}`,
          },
        ]
      : []),
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
        nodeType={LOOP_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <LoopDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={LOOP_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(LoopNode);
