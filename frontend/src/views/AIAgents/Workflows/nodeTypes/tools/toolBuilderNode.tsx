import React, { useState } from "react";
import { NodeProps, useReactFlow } from "reactflow";
import { ToolBuilderNodeData } from "../../types/nodes";
import { TestDialog } from "../../components/TestDialog";
import { HandlersRenderer } from "../../components/HandleTooltip";
import { NodeSchema } from "../../types/schemas";
import { getNodeColors } from "../../utils/nodeColors";
import { useChatInputSchema } from "../../hooks/useChatInputSchema";
import NodeHeader from "../nodeHeader";
import NodeContent from "../nodeContent";
import { ToolBuilderDialog } from "../../components/ToolBuilderDialog";
import { testToolBuilder } from "@/services/workflows";
import { useWorkflow } from "../../WorkflowContext";

const ToolBuilderNode: React.FC<NodeProps<ToolBuilderNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("toolBuilderNode");
  const [response, setResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const { getNodes, getEdges } = useReactFlow();
  const { workflow } = useWorkflow();

  const handleToolFunction = async (
    data: ToolBuilderNodeData,
    inputs: Record<string, string>
  ) => {
    setIsLoading(true);
    setError(null);
    setResponse(null);
    try {
      // Build up-to-date workflow with latest nodes and edges
      const upToDateWorkflow = {
        ...workflow,
        nodes: getNodes(),
        edges: getEdges(),
      };
      const results = await testToolBuilder(id, upToDateWorkflow, inputs);
      setResponse(JSON.stringify(results, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setResponse(`Error: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Generate input fields based on parameter mapping
  const generateInputFields = (inputSchema: NodeSchema) => {
    try {
      return Object.entries(inputSchema || {}).map(([key, value]) => ({
        id: key,
        label: key,
        type: value.type,
        required: value.required,
        defaultValue: value?.defaultValue ?? "",
      }));
    } catch {
      return [];
    }
  };

  const onUpdate = (updatedData: ToolBuilderNodeData) => {
    if (data.updateNodeData) {
      const dataToUpdate: Partial<ToolBuilderNodeData> = {
        ...data,
        ...updatedData,
      };

      data.updateNodeData(id, dataToUpdate);
    }
  };

  // Get ChatInputNode's schema using reusable hook
  const chatInputSchema = useChatInputSchema(id);

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <NodeHeader
          iconName={"wrench"}
          title={data.name}
          subtitle={"Custom tool for parameter forwarding"}
          color={colors.header}
          onSettings={() => setIsEditDialogOpen(true)}
          onTest={() => setIsTestDialogOpen(true)}
        />

        {/* Node content */}
        <NodeContent
          data={[
            { label: "Tool Name", value: data.name },
            { label: "Node Description", value: data.description },
            { label: "Input Variables", value: data.inputSchema },
          ]}
        />

        <HandlersRenderer id={id} data={data} />
      </div>

      {/* Edit Dialog */}
      <ToolBuilderDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
        availableParams={chatInputSchema}
      />

      {/* Test Dialog */}
      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${data.name}`}
        description="Fill in the required values for testing the tool configuration"
        inputFields={generateInputFields(data.inputSchema)}
        onRun={(inputs) => handleToolFunction(data, inputs ?? {})}
        output={response}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default ToolBuilderNode; 