import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { ReadMailsNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import { getAllDataSources } from "@/services/dataSources";
import { DataSource } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { ReadMailsDialog } from "../../nodeDialogs/readMailsDialog";
import nodeRegistry from "../../registry/nodeRegistry";

export const READ_MAILS_NODE_TYPE = "readMailsNode";

const ReadMailsNode: React.FC<NodeProps<ReadMailsNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(READ_MAILS_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const color = getNodeColor(nodeDefinition.category);

  // Query for Gmail data sources
  const { data: connectors = [] } = useQuery({
    queryKey: ["dataSources"],
    queryFn: getAllDataSources,
    select: (data: DataSource[]) =>
      data.filter((p) => p.is_active === 1 && p.source_type === "gmail"),
  });

  const selectedConnector = connectors.find(
    (c) => c.id.toString() === data.dataSourceId
  );

  // Auto-select first available connector if none selected
  useEffect(() => {
    if (connectors) {
      if (data.dataSourceId === undefined && connectors.length > 0) {
        if (data.updateNodeData) {
          data.updateNodeData(id, {
            ...data,
            dataSourceId: connectors[0].id,
          });
        }
      }
    }
  }, [connectors, data.dataSourceId, id, data]);

  const onUpdate = (updatedData: ReadMailsNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<ReadMailsNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

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
        nodeType={READ_MAILS_NODE_TYPE}
        onSettings={() => setIsEditDialogOpen(true)}
      >
        {/* Node content */}
        <NodeContent
          data={[
            {
              label: "Gmail Data Source",
              value: selectedConnector?.name || "",
            },
            { label: "From Email", value: data.searchCriteria?.from },
            { label: "To Email", value: data.searchCriteria?.to },
            { label: "Subject Contains", value: data.searchCriteria?.subject },
          ]}
        />
      </BaseNodeContainer>

      {/* Edit Dialog */}
      <ReadMailsDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        connectors={connectors}
        nodeId={id}
        nodeType={READ_MAILS_NODE_TYPE}
      />
    </>
  );
};

export default ReadMailsNode;
