import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { TrainDataSourceNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import NodeContent from "../nodeContent";
import { TrainDataSourceDialog } from "../../nodeDialogs/training/TrainDataSourceDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import { getAllDataSources } from "@/services/dataSources";
import nodeRegistry from "../../registry/nodeRegistry";

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
      return "CSV Upload";
    }
    return "Datasource";
  };

  const getDataSourceInfo = () => {
    if (data.sourceType === "csv") {
      return (
        data.csvFileName ||
        (data.csvFilePath ? "CSV file uploaded" : "No file uploaded")
      );
    }
    return selectedDataSource
      ? `${selectedDataSource.name} (${selectedDataSource.source_type})`
      : "Not selected";
  };

  const queryPreview =
    data.query && data.sourceType === "datasource"
      ? data.query.length > 50
        ? `${data.query.substring(0, 50)}...`
        : data.query
      : data.sourceType === "datasource"
      ? "No query set"
      : "N/A";

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
        onSettings={() => setIsEditDialogOpen(true)}
      >
        <NodeContent
          data={[
            { label: "Source Type", value: getSourceTypeLabel() },
            { label: "Data Source", value: getDataSourceInfo() },
            { label: "Query", value: queryPreview },
          ]}
        />
      </BaseNodeContainer>

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
