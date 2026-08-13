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
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { getAllWorkflows } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { NodeSchema, SchemaField } from "../types/schemas";
import { RichInput } from "@/components/richInput";
import { useNodeDialogState } from "./useNodeDialogState";

export const WorkflowExecutorDialog: React.FC<
  BaseNodeDialogProps<WorkflowExecutorNodeData, WorkflowExecutorNodeData>
> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      workflowId: data.workflowId || "",
      workflowName: data.workflowName || "",
      inputParameters: data.inputParameters || {},
    })
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

  // Update input schema when workflow is selected
  useEffect(() => {
    if (values.workflowId && workflows.length > 0) {
      const selectedWorkflow = workflows.find(
        (w) => w.id === values.workflowId
      );
      if (selectedWorkflow) {
        setField("workflowName", selectedWorkflow.name);
        extractInputSchema(selectedWorkflow);
      }
    } else {
      setSelectedWorkflowInputSchema(null);
    }
  }, [values.workflowId, workflows, setField]);

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
        if (!(key in values.inputParameters)) {
          newInputParameters[key] = "";
        } else {
          newInputParameters[key] = values.inputParameters[key];
        }
      });
      setField("inputParameters", newInputParameters);
    } else {
      setSelectedWorkflowInputSchema(null);
    }
  };

  const handleWorkflowChange = (newWorkflowId: string) => {
    setField("workflowId", newWorkflowId);
    const selectedWorkflow = workflows.find((w) => w.id === newWorkflowId);
    if (selectedWorkflow) {
      setField("workflowName", selectedWorkflow.name);
      extractInputSchema(selectedWorkflow);
    }
  };

  const handleParameterChange = (key: string, value: string) => {
    setField("inputParameters", {
      ...values.inputParameters,
      [key]: value,
    });
  };

  return (
    <NodeConfigPanel
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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <RichInput
          id="name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Workflow Executor"
          className="break-all w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">Select Workflow</Label>
        <Select
          value={values.workflowId}
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
        {values.workflowName && (
          <p className="text-xs text-muted-foreground">
            Selected: {values.workflowName}
          </p>
        )}
      </div>

      {selectedWorkflowInputSchema && Object.keys(selectedWorkflowInputSchema).length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm font-semibold">Input Parameters</Label>
          <div className="space-y-3 pl-2 border-l-2 border-border">
            {Object.entries(selectedWorkflowInputSchema).map(([key, field]: [string, SchemaField]) => (
              <div key={key} className="space-y-1">
                <Label
                  htmlFor={`param-${key}`}
                  className="text-xs text-muted-foreground flex items-center gap-1"
                >
                  {key}
                  {field.required && <span className="text-red-500">*</span>}
                  {field.description && (
                    <span className="text-muted-foreground font-normal">({field.description})</span>
                  )}
                </Label>
                <DraggableInput
                  id={`param-${key}`}
                  value={values.inputParameters[key] || ""}
                  onChange={(e) => handleParameterChange(key, e.target.value)}
                  placeholder={`Enter ${key}${field.required ? " (required)" : ""}`}
                  className="text-sm"
                />
                <div className="text-xs text-muted-foreground">
                  Use {"{{variable}}"} for dynamic values
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {values.workflowId && selectedWorkflowInputSchema && Object.keys(selectedWorkflowInputSchema).length === 0 && (
        <div className="text-sm text-muted-foreground text-center py-4">
          This workflow has no input parameters defined.
        </div>
      )}

      {!values.workflowId && (
        <div className="text-sm text-muted-foreground text-center py-4">
          Select a workflow to configure input parameters.
        </div>
      )}
    </NodeConfigPanel>
  );
};
