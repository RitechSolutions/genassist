import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { HtmlToImageNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { HtmlToImageDialog } from "../../nodeDialogs/HtmlToImageDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const HTML_TO_IMAGE_NODE_TYPE = "htmlToImageNode";

const HtmlToImageNode: React.FC<NodeProps<HtmlToImageNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(HTML_TO_IMAGE_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: HtmlToImageNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<HtmlToImageNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Capture Mode", value: data.captureMode },
    {
      label: "Viewport",
      value: `${data.viewportWidth}x${data.viewportHeight}`,
    },
    {
      label: "Variables",
      value: extractDynamicVariablesAsRecord(JSON.stringify(data)),
      areDynamicVars: true,
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
        nodeType={HTML_TO_IMAGE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <HtmlToImageDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={HTML_TO_IMAGE_NODE_TYPE}
      />
    </>
  );
};

export default HtmlToImageNode;
