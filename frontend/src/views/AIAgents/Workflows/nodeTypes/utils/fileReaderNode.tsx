import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { FileReaderNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { FileReaderDialog } from "../../nodeDialogs/FileReaderDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const FILE_READER_NODE_TYPE = "fileReaderNode";

const FileReaderNode: React.FC<NodeProps<FileReaderNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(FILE_READER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: Partial<FileReaderNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "File",
      value: data.fileName || "No file uploaded",
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
        nodeType={FILE_READER_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <FileReaderDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={FILE_READER_NODE_TYPE}
      />
    </>
  );
};

export default FileReaderNode;
