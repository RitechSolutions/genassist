import React, { useState, useEffect } from "react";
import { NodeProps } from "reactflow";
import { SQLNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { getNodeColor } from "../../utils/nodeColors";
import BaseNodeContainer from "../BaseNodeContainer";
import { SQLDialog } from "../../nodeDialogs/SQLDialog";
import { DataSource } from "@/interfaces/dataSource.interface";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllDataSources } from "@/services/dataSources";
import { getAllLLMProviders } from "@/services/llmProviders";
import nodeRegistry from "../../registry/nodeRegistry";
import { NodeContentRow } from "../nodeContent";

export const SQL_NODE_TYPE = "sqlNode";

const SQLNode: React.FC<NodeProps<SQLNodeData>> = ({ id, data, selected }) => {
  const nodeDefinition = nodeRegistry.getNodeType(SQL_NODE_TYPE);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    []
  );
  const [availableDataSources, setAvailableDataSources] = useState<
    DataSource[]
  >([]);

  const color = getNodeColor(nodeDefinition.category);

  // Fetch providers and data sources to map IDs to names for display
  useEffect(() => {
    const loadResources = async () => {
      try {
        const [providers, dataSources] = await Promise.all([
          getAllLLMProviders(),
          getAllDataSources(),
        ]);
        setAvailableProviders(providers.filter((p) => p.is_active === 1));
        setAvailableDataSources(dataSources);
      } catch (err) {
        // ignore
      }
    };
    loadResources();
  }, []);

  const onUpdate = (updatedData: SQLNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<SQLNodeData> = {
        ...data,
        ...updatedData,
      };
      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Find the names of selected provider and data source
  const selectedProvider = availableProviders.find(
    (p) => p.id === data.providerId
  );
  const selectedDataSource = availableDataSources.find(
    (ds) => ds.id === data.dataSourceId
  );

  const numberOfParameters = data.parameters
    ? Object.keys(data.parameters).length
    : 0;

  const nodeContent: NodeContentRow[] = [
    {
      label: "LLM Provider",
      value: selectedProvider?.name,
      placeholder: "None selected",
    },
    {
      label: "Data Source",
      value: selectedDataSource?.name,
      placeholder: "None selected",
    },
    {
      label: "Parameters",
      value:
        numberOfParameters === 1
          ? "1 parameter"
          : numberOfParameters > 1
          ? `${numberOfParameters} parameters`
          : "",
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
        nodeType={SQL_NODE_TYPE}
        nodeContent={nodeContent}
        onSettings={() => setIsEditDialogOpen(true)}
      />

      {/* Edit Dialog */}
      <SQLDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        nodeId={id}
        nodeType={SQL_NODE_TYPE}
      />
    </>
  );
};

export default SQLNode;
