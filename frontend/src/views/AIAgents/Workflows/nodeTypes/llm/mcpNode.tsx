import React, { useState } from "react";
import { NodeProps } from "reactflow";
import { MCPNodeData } from "../../types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { MCPDialog } from "../../nodeDialogs/MCPDialog";
import BaseNodeContainer from "../BaseNodeContainer";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";

export const MCP_NODE_TYPE = "mcpNode";

const MCPNode: React.FC<NodeProps<MCPNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(MCP_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const onUpdate = (updatedData: MCPNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<MCPNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Get connection info for display
  const getConnectionInfo = () => {
    if (data.connectionType === "stdio" && "command" in data.connectionConfig) {
      return {
        type: "STDIO",
        value: data.connectionConfig.command + (data.connectionConfig.args ? ` ${data.connectionConfig.args.join(" ")}` : ""),
      };
    } else if ((data.connectionType === "http" || data.connectionType === "sse") && "url" in data.connectionConfig) {
      return {
        type: data.connectionType.toUpperCase(),
        value: data.connectionConfig.url,
      };
    }
    return {
      type: "Not configured",
      value: "",
    };
  };

  const connectionInfo = getConnectionInfo();

  const nodeContent: NodeContentRow[] = [
    { label: "Description", value: data.description },
    {
      label: "Connection Type",
      value: connectionInfo.type,
      placeholder: "Not configured",
    },
    {
      label: connectionInfo.type === "STDIO" ? "Command" : "Server URL",
      value: connectionInfo.value,
      placeholder: "Not configured",
    },
    {
      label: "Whitelisted Tools",
      value:
        data.whitelistedTools.length === 0
          ? ""
          : `${data.whitelistedTools.length} tool${data.whitelistedTools.length === 1 ? "" : "s"}`,
      placeholder: "None selected",
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
        nodeType="mcpNode"
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <MCPDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={MCP_NODE_TYPE}
      />
    </>
  );
};

export default MCPNode;

