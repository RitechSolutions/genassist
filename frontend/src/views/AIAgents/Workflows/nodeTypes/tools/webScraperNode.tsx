import React from "react";
import { NodeProps } from "reactflow";
import { WebScraperNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
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

  const nodeContent: NodeContentRow[] = [
    { label: "URL", value: data.url },
    { label: "Format", value: data.format },
    { label: "Render JS", value: data.renderJs ? "On" : "Off" },
    {
      label: "Variables",
      value: extractDynamicVariablesAsRecord(JSON.stringify(data)),
      areDynamicVars: true,
    },
  ];

  return (
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
    />
  );
};

export default WebScraperNode;
