import React, { useEffect, useState } from "react";
import { NodeProps } from "reactflow";
import { getNodeColor } from "../../utils/nodeColors.ts";
import { CalendarEventToolNodeData } from "../../types/nodes.ts";
import { getAllDataSources } from "@/services/dataSources.ts";
import { DataSource } from "@/interfaces/dataSource.interface.ts";
import { useQuery } from "@tanstack/react-query";
import BaseNodeContainer from "../BaseNodeContainer";
import { CalendarEventDialog } from "@/views/AIAgents/Workflows/nodeDialogs/CalendarEventDialog.tsx";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent.tsx";

export const CALENDAR_EVENT_NODE_TYPE = "calendarEventNode";

const CalendarEventNode: React.FC<NodeProps<CalendarEventToolNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(CALENDAR_EVENT_NODE_TYPE);
  const color = getNodeColor(nodeDefinition.category);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const { data: connectors = [] } = useQuery({
    queryKey: ["dataSources"],
    queryFn: getAllDataSources,
    select: (data: DataSource[]) =>
      data.filter(
        (p) =>
          (p.is_active === 1 && p.source_type === "gmail") ||
          p.source_type === "o365"
      ),
  });

  useEffect(() => {
    if (data.dataSourceId === undefined && connectors.length > 0) {
      if (data.updateNodeData) {
        data.updateNodeData<CalendarEventToolNodeData>(id, {
          ...data,
          dataSourceId: connectors[0].id,
        });
      }
    }
  }, [connectors, data.dataSourceId, id, data]);

  const onUpdate = (updatedData: Partial<CalendarEventToolNodeData>) => {
    if (data.updateNodeData) {
      data.updateNodeData(id, { ...data, ...updatedData });
    }
  };

  const nodeContent: NodeContentRow[] = [
    {
      label: "Connector",
      value: data.dataSourceId,
      placeholder: "None selected",
    },
    {
      label: "Operation",
      value: data.operation,
      placeholder: "None selected",
      isSelection: true,
    },
    { label: "Summary", value: data.summary },
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
        nodeType={CALENDAR_EVENT_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      <CalendarEventDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        connectors={connectors}
        nodeId={id}
        nodeType={CALENDAR_EVENT_NODE_TYPE}
      />
    </>
  );
};

export default CalendarEventNode;
