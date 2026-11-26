import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { GuardrailNodeData } from "../../types/nodes";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { GuardrailDialog } from "../../nodeDialogs/GuardrailDialog";

export const GUARDRAIL_NODE_TYPE = "guardrailNode";

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

const describeChecks = (data: GuardrailNodeData): string => {
  const harmTypes = Object.values(data.harmful_content ?? {}).filter(
    (level) => level !== "off"
  ).length;
  const topics = data.denied_topics?.length ?? 0;
  const words = data.blocked_words?.length ?? 0;
  const parts = [
    data.prompt_attack && data.prompt_attack !== "off" ? "Prompt attack" : "",
    harmTypes ? plural(harmTypes, "harm type") : "",
    topics ? plural(topics, "topic") : "",
    words ? plural(words, "word") : "",
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "None";
};

const GuardrailNode: React.FC<NodeProps<GuardrailNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(GUARDRAIL_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<GuardrailNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Text", value: data.text },
    { label: "Checks", value: describeChecks(data) },
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
        nodeType={GUARDRAIL_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <GuardrailDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={GUARDRAIL_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(GuardrailNode);
