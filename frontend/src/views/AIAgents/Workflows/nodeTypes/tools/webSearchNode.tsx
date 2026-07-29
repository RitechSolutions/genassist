import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { WebSearchNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { WebSearchDialog } from "../../nodeDialogs/WebSearchDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const WEB_SEARCH_NODE_TYPE = "webSearchNode";

const WebSearchNode: React.FC<NodeProps<WebSearchNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(WEB_SEARCH_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: WebSearchNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<WebSearchNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Query", value: data.query },
    { label: "Depth", value: data.searchDepth },
    { label: "Max Results", value: String(data.maxResults) },
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
        nodeType={WEB_SEARCH_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <WebSearchDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={WEB_SEARCH_NODE_TYPE}
      />
    </>
  );
};

export default WebSearchNode;
