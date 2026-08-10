import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { WebScraperNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { WebScraperDialog } from "../../nodeDialogs/WebScraperDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const WEB_SCRAPER_NODE_TYPE = "webScraperNode";

const WebScraperNode: React.FC<NodeProps<WebScraperNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(WEB_SCRAPER_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: WebScraperNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<WebScraperNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "URL", value: data.url },
    { label: "Format", value: data.format },
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
        nodeType={WEB_SCRAPER_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <WebScraperDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={WEB_SCRAPER_NODE_TYPE}
      />
    </>
  );
};

export default WebScraperNode;
