import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { TrainDataSourceNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { TrainDataSourceDialog } from "../../nodeDialogs/training/TrainDataSourceDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import { getAllDataSources } from "@/services/dataSources";
import nodeRegistry from "../../registry/nodeRegistry";
import { get } from "http";
import { NodeContentRow } from "../nodeContent";

export const TRAIN_DATA_SOURCE_NODE_TYPE = "trainDataSourceNode";

const TrainDataSourceNode: React.FC<NodeProps<TrainDataSourceNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const nodeDefinition = nodeRegistry.getNodeType(TRAIN_DATA_SOURCE_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);

  const color = getNodeColor(nodeDefinition.category);

  // Fetch data sources to map IDs to names for display
  useEffect(() => {
    const loadDataSources = async () => {
      try {
        const dataSources = await getAllDataSources();
        // Filter for timedb and snowflake
        const trainingDataSources = dataSources.filter(
          (ds) =>
            ds.source_type.toLowerCase().includes("timedb") ||
            ds.source_type.toLowerCase().includes("snowflake") ||
            ds.source_type.toLowerCase().includes("timescale") ||
            ds.source_type.toLowerCase().includes("postgres")
        );
        setAvailableDataSources(trainingDataSources);
      } catch (err) {
        // ignore
      }
    };
    loadDataSources();
  }, []);

  const onUpdate = (updatedData: TrainDataSourceNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<TrainDataSourceNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Find the name of selected data source
  const selectedDataSource = availableDataSources.find(
    (ds) => ds.id === data.dataSourceId
  );

  const getSourceTypeLabel = () => {
    if (data.sourceType === "csv") {
      return "CSV upload";
    }
    return "Data source";
  };

  const getDataSourceInfo = () => {
    if (data.sourceType === "csv") {
      return data.csvFileName || (data.csvFilePath ? "CSV file" : "");
    }
    return selectedDataSource
      ? `${selectedDataSource.name} (${selectedDataSource.source_type})`
      : "";
  };

  const queryPreview =
    data.query && data.sourceType === "datasource"
      ? data.query.length > 50
        ? `${data.query.substring(0, 50)}...`
        : data.query
      : data.sourceType === "datasource"
      ? "No query set"
      : "N/A";

  const nodeContent: NodeContentRow[] = [
    { label: "Source Type", value: data.sourceType, isSelection: true },
    { label: "Data Source", value: getDataSourceInfo() },
    { label: "Query", value: data.query },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="database"
        title={data.name || "Train Data Source"}
        subtitle="Fetch training data"
        color={color}
        nodeType={TRAIN_DATA_SOURCE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <TrainDataSourceDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TRAIN_DATA_SOURCE_NODE_TYPE}
      />
    </>
  );
};

export default TrainDataSourceNode;
