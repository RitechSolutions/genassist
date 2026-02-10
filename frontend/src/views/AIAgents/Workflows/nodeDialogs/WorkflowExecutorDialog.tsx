import React, { useEffect, useState } from "react";
import { WorkflowExecutorNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save } from "lucide-react";
import { NodeConfigDialog } from "../components/NodeConfigDialog";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { getAllWorkflows } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { NodeSchema, SchemaField } from "../types/schemas";
import { Input } from "@/components/input";
import { valueToString } from "../utils/helpers";

export const WorkflowExecutorDialog: React.FC<
  BaseNodeDialogProps<WorkflowExecutorNodeData, WorkflowExecutorNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [workflowId, setWorkflowId] = useState(data.workflowId || "");
  const [workflowName, setWorkflowName] = useState(data.workflowName || "");
  const [inputParameters, setInputParameters] = useState<Record<string, string>>(
    data.inputParameters || {}
  );
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedWorkflowInputSchema, setSelectedWorkflowInputSchema] = useState<NodeSchema | null>(null);

  // Fetch workflows when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchWorkflows();
    }
  }, [isOpen]);

  // Update local state when data changes
  useEffect(() => {
    setName(data.name || "");
    setWorkflowId(data.workflowId || "");
    setWorkflowName(data.workflowName || "");
    setInputParameters(data.inputParameters || {});
  }, [isOpen, data]);

  // Update input schema when workflow is selected
  useEffect(() => {
    if (workflowId && workflows.length > 0) {
      const selectedWorkflow = workflows.find((w) => w.id === workflowId);
      if (selectedWorkflow) {
        setWorkflowName(selectedWorkflow.name);
        extractInputSchema(selectedWorkflow);
      }
    } else {
      setSelectedWorkflowInputSchema(null);
    }
  }, [workflowId, workflows]);

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const allWorkflows = await getAllWorkflows();
      setWorkflows(allWorkflows);
    } catch (error) {
      console.error("Error fetching workflows:", error);
    } finally {
      setLoading(false);
    }
  };

  const extractInputSchema = (workflow: Workflow) => {
    if (!workflow.nodes || workflow.nodes.length === 0) {
      setSelectedWorkflowInputSchema(null);
      return;
    }

    // Find the chatInputNode which contains the input schema
    const chatInputNode = workflow.nodes.find((node) =>
      node.type?.includes("InputNode") || node.type === "chatInputNode"
    );

    if (chatInputNode && chatInputNode.data?.inputSchema) {
      const schema = chatInputNode.data.inputSchema as NodeSchema;
      setSelectedWorkflowInputSchema(schema);

      // Initialize input parameters with empty values for all schema fields
      const newInputParameters: Record<string, string> = {};
      Object.keys(schema).forEach((key) => {
        if (!(key in inputParameters)) {
          newInputParameters[key] = "";
        } else {
          newInputParameters[key] = inputParameters[key];
        }
      });
      setInputParameters(newInputParameters);
    } else {
      setSelectedWorkflowInputSchema(null);
    }
  };

  const handleWorkflowChange = (newWorkflowId: string) => {
    setWorkflowId(newWorkflowId);
    const selectedWorkflow = workflows.find((w) => w.id === newWorkflowId);
    if (selectedWorkflow) {
      setWorkflowName(selectedWorkflow.name);
      extractInputSchema(selectedWorkflow);
    }
  };

  const handleParameterChange = (key: string, value: string) => {
    setInputParameters({
      ...inputParameters,
      [key]: value,
    });
  };

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      workflowId,
      workflowName,
      inputParameters,
    });
    onClose();
  };

  return (
    <NodeConfigDialog
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        workflowId,
        workflowName,
        inputParameters,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Workflow Executor"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">Select Workflow</Label>
        <Select
          value={workflowId}
          onValueChange={handleWorkflowChange}
          disabled={loading}
        >
          <SelectTrigger>
            <SelectValue placeholder={loading ? "Loading workflows..." : "Select a workflow"} />
          </SelectTrigger>
          <SelectContent>
            {workflows.map((workflow) => (
              <SelectItem key={workflow.id} value={workflow.id || ""}>
                {workflow.name} {workflow.version ? `(v${workflow.version})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {workflowName && (
          <p className="text-xs text-gray-500">
            Selected: {workflowName}
          </p>
        )}
      </div>

      {selectedWorkflowInputSchema && Object.keys(selectedWorkflowInputSchema).length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm font-semibold">Input Parameters</Label>
          <div className="space-y-3 pl-2 border-l-2 border-gray-200">
            {Object.entries(selectedWorkflowInputSchema).map(([key, field]: [string, SchemaField]) => (
              <div key={key} className="space-y-1">
                <Label
                  htmlFor={`param-${key}`}
                  className="text-xs text-gray-600 flex items-center gap-1"
                >
                  {key}
                  {field.required && <span className="text-red-500">*</span>}
                  {field.description && (
                    <span className="text-gray-400 font-normal">({field.description})</span>
                  )}
                </Label>
                <DraggableInput
                  id={`param-${key}`}
                  value={inputParameters[key] || ""}
                  onChange={(e) => handleParameterChange(key, e.target.value)}
                  placeholder={`Enter ${key}${field.required ? " (required)" : ""}`}
                  className="text-sm"
                />
                <div className="text-xs text-gray-400">
                  Use {"{{variable}}"} for dynamic values
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {workflowId && selectedWorkflowInputSchema && Object.keys(selectedWorkflowInputSchema).length === 0 && (
        <div className="text-sm text-gray-500 text-center py-4">
          This workflow has no input parameters defined.
        </div>
      )}

      {!workflowId && (
        <div className="text-sm text-gray-500 text-center py-4">
          Select a workflow to configure input parameters.
        </div>
      )}
    </NodeConfigDialog>
  );
};
