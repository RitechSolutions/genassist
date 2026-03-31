import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { GuardrailProvenanceNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { GuardrailProvenanceDialog } from "../../nodeDialogs/GuardrailProvenanceDialog";

export const GUARDRAIL_PROVENANCE_NODE_TYPE = "guardrailProvenanceNode";

const GuardrailProvenanceNode: React.FC<
  NodeProps<GuardrailProvenanceNodeData>
> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(
    GUARDRAIL_PROVENANCE_NODE_TYPE,
  );
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<GuardrailProvenanceNodeData>) => {
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
      label: "Context field",
      value: data.context_field || "context",
    },
    {
      label: "Min score",
      value: (data.min_score ?? 0.5).toString(),
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
        nodeType={GUARDRAIL_PROVENANCE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <GuardrailProvenanceDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={GUARDRAIL_PROVENANCE_NODE_TYPE}
      />
    </>
  );
};

export default GuardrailProvenanceNode;

