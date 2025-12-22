import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors";
import { GmailNodeData } from "../../types/nodes";
import { getAllDataSources } from "@/services/dataSources";
import { DataSource } from "@/interfaces/dataSource.interface";
import { useQuery } from "@tanstack/react-query";
import BaseNodeContainer from "../BaseNodeContainer";
import { GmailDialog } from "../../nodeDialogs/GmailDialog";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import { extractDynamicVariablesAsRecord } from "../../utils/helpers";

export const GMAIL_NODE_TYPE = "gmailNode";

const GmailNode: React.FC<NodeProps<GmailNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(GMAIL_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const { data: connectors = [] } = useQuery({
    queryKey: ["dataSources"],
    queryFn: getAllDataSources,
    select: (data: DataSource[]) =>
      data.filter((p) => p.is_active === 1 && p.source_type === "gmail"),
  });

  useEffect(() => {
    if (data.dataSourceId === undefined && connectors.length > 0) {
      if (data.updateNodeData) {
        data.updateNodeData<GmailNodeData>(id, {
          ...data,
          dataSourceId: connectors[0].id,
        });
      }
    }
  }, [connectors, data.dataSourceId, id, data]);

  const onUpdate = (updatedData: Partial<GmailNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    { label: "Recipient", value: data.to },
    { label: "Subject", value: data.subject },
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
        nodeType={GMAIL_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <GmailDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        connectors={connectors}
        nodeId={id}
        nodeType={GMAIL_NODE_TYPE}
      />
    </>
  );
};

export default GmailNode;
