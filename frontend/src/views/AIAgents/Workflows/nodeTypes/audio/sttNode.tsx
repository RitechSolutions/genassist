import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { STTNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { STTDialog } from "../../nodeDialogs/STTDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const STT_NODE_TYPE = "sttNode";

const STTNode: React.FC<NodeProps<STTNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(STT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<STTNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Model",
      value: data.model || "whisper-1",
    },
    {
      label: "Language",
      value: data.language || "Auto-detect",
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
        nodeType={STT_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <STTDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={STT_NODE_TYPE}
      />
    </>
  );
};

export default STTNode;
