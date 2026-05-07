import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { TTSNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { TTSDialog } from "../../nodeDialogs/TTSDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const TTS_NODE_TYPE = "ttsNode";

const TTSNode: React.FC<NodeProps<TTSNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(TTS_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<TTSNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Text",
      value: data.text || "Not configured",
    },
    {
      label: "Voice",
      value: data.voice || "nova",
    },
    {
      label: "Model",
      value: data.model || "tts-1",
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
        nodeType={TTS_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <TTSDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TTS_NODE_TYPE}
      />
    </>
  );
};

export default TTSNode;
