import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { HumanInTheLoopNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { HumanInTheLoopDialog } from "../../nodeDialogs/HumanInTheLoopDialog";
import { NodeContentRow } from "../nodeContent";

export const HUMAN_IN_THE_LOOP_NODE_TYPE = "humanInTheLoopNode";

const HumanInTheLoopNode: React.FC<NodeProps<HumanInTheLoopNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(HUMAN_IN_THE_LOOP_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const color = getNodeColor(nodeDefinition?.category || "io");

  const onUpdate = (updatedData: HumanInTheLoopNodeData) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        ...updatedData,
      });
    }
  };

  const fieldsSummary =
    data.form_fields && data.form_fields.length > 0
      ? data.form_fields.map((f) => `${f.label}${f.required ? "*" : ""}`).join(", ")
      : undefined;

  const nodeContent: NodeContentRow[] = [
    {
      label: "Message",
      value: data.message,
      placeholder: "No message set",
    },
    {
      label: "Fields",
      value: fieldsSummary,
      placeholder: "No fields configured",
    },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName={nodeDefinition?.icon || "ClipboardList"}
        title={data.name || nodeDefinition?.label || "Human In The Loop"}
        subtitle={nodeDefinition?.shortDescription}
        color={color}
        nodeType={HUMAN_IN_THE_LOOP_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <HumanInTheLoopDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={HUMAN_IN_THE_LOOP_NODE_TYPE}
      />
    </>
  );
};

export default HumanInTheLoopNode;
