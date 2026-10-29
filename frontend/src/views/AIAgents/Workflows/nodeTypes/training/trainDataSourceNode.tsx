import React, { useEffect, useRef, useState } from "react";
import { NodeProps } from "reactflow";
import { TrainDataSourceNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { TrainDataSourceDialog } from "../../nodeDialogs/training/TrainDataSourceDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import { getAllDataSources } from "@/services/dataSources";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";
import {
  getTrainDataSourceShape,
  getTrainDataSourceSummary,
  hasTrainDataSourceConfigurationChanged,
  isTrainingDatabaseSource,
} from "../../utils/trainDataSource";
import { useWorkflowExecution } from "../../context/WorkflowExecutionContext";

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
  const { clearNodeOutput, getNodeOutput } = useWorkflowExecution();
  const outputTimestampWhenDialogOpened = useRef<number | undefined>();
  const dialogWasSaved = useRef(false);

  const color = getNodeColor(nodeDefinition.category);

  // Fetch data sources to map IDs to names for display
  useEffect(() => {
    const loadDataSources = async () => {
      try {
        const dataSources = await getAllDataSources();
        const trainingDataSources = dataSources.filter(
          isTrainingDatabaseSource
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
      const currentOutputTimestamp = getNodeOutput(id)?.timestamp;
      const testedSinceDialogOpened =
        currentOutputTimestamp !== undefined &&
        currentOutputTimestamp !== outputTimestampWhenDialogOpened.current;
      if (
        hasTrainDataSourceConfigurationChanged(data, updatedData) &&
        !testedSinceDialogOpened
      ) {
        clearNodeOutput(id);
      }
      dialogWasSaved.current = true;
      data.updateNodeData(id, dataToUpdate);
    }
  };

  const handleOpenSettings = () => {
    outputTimestampWhenDialogOpened.current = getNodeOutput(id)?.timestamp;
    dialogWasSaved.current = false;
    setIsEditDialogOpen(true);
  };

  const handleCloseSettings = () => {
    const currentOutputTimestamp = getNodeOutput(id)?.timestamp;
    const testedWhileDialogWasOpen =
      currentOutputTimestamp !== undefined &&
      currentOutputTimestamp !== outputTimestampWhenDialogOpened.current;
    if (!dialogWasSaved.current && testedWhileDialogWasOpen) {
      clearNodeOutput(id);
    }
    setIsEditDialogOpen(false);
  };

  // Find the name of selected data source
  const selectedDataSource = availableDataSources.find(
    (ds) => ds.id === data.dataSourceId
  );

  const summary = getTrainDataSourceSummary(data, selectedDataSource);
  const shape = getTrainDataSourceShape(data, getNodeOutput(id)?.output);
  const hasSourceType = summary.sourceTypeLabel !== "Not configured";

  const nodeContent: NodeContentRow[] = [
    {
      label: "Source Type",
      value: hasSourceType ? summary.sourceTypeLabel : "",
      isSelection: true,
    },
    {
      label: summary.sourceFieldLabel,
      value: summary.sourceLabel,
    },
    { label: "Shape", value: shape },
  ];

  return (
    <>
      <BaseNodeContainer
        id={id}
        data={data}
        selected={selected}
        iconName="database"
        title={data.name || "Train Data Source"}
        subtitle="Load training data"
        color={color}
        nodeType={TRAIN_DATA_SOURCE_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={handleOpenSettings}
      />

      {/* Edit Dialog */}
      <TrainDataSourceDialog
        isOpen={isEditDialogOpen}
        onClose={handleCloseSettings}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={TRAIN_DATA_SOURCE_NODE_TYPE}
      />
    </>
  );
};

export default React.memo(TrainDataSourceNode);
