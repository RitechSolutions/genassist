import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { GuardrailNliNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { GuardrailNliDialog } from "../../nodeDialogs/GuardrailNliDialog";

export const GUARDRAIL_NLI_NODE_TYPE = "guardrailNliNode";

const GuardrailNliNode: React.FC<NodeProps<GuardrailNliNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(GUARDRAIL_NLI_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<GuardrailNliNodeData>) => {
    if (data.updateNodeData) {
      const dataToUpdate = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Answer field",
      value: data.answer_field || "answer",
    },
    {
      label: "Evidence field",
      value: data.evidence_field || "context",
    },
    {
      label: "Min entail score",
      value: (data.min_entail_score ?? 0.5).toString(),
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
        nodeType={GUARDRAIL_NLI_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <GuardrailNliDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={GUARDRAIL_NLI_NODE_TYPE}
      />
    </>
  );
};

export default GuardrailNliNode;

