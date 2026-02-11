import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Input } from "@/components/input";
import { Checkbox } from "@/components/checkbox";
import { Play, X } from "lucide-react";
import { NodeData } from "../types/nodes";
import { testNode, WorkflowTestResponse } from "@/services/workflows";
import { extractDynamicVariables, getValueFromPath, parseInputValue, truncateNodeOutput } from "../utils/helpers";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { SchemaField, SchemaType } from "../types/schemas";
import JsonViewer from "@/components/JsonViewer";

export interface GenericTestInputField {
  id: string;
  label: string;
  type: string;
  placeholder?: string;
  required?: boolean;
  defaultValue?: string;
  source?: string; // Added source property
}

interface GenericTestDialogProps {
  isOpen: boolean;
  onClose: () => void;
  nodeType: string;
  nodeData: NodeData;
  nodeName?: string;
  nodeId?: string; // Add nodeId prop
}

export const GenericTestDialog: React.FC<GenericTestDialogProps> = ({
  isOpen,
  onClose,
  nodeType,
  nodeData,
  nodeName,
  nodeId,
}) => {
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [output, setOutput] = useState<string | Record<string, unknown> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputFields, setInputFields] = useState<GenericTestInputField[]>([]);
  const [availableData, setAvailableData] = useState<Record<
    string,
    unknown
  > | null>(null);

  const { updateNodeOutput, getAvailableDataForNode, getNodeOutput } =
    useWorkflowExecution();

  // Extract variables from node config when dialog opens
  useEffect(() => {
    if (isOpen && nodeData) {
      let variables = extractVariablesFromNodeConfig(nodeData);
      variables = variables.filter((v) => v !== "direct_input");
      const schemaFields = extractInputSchemaFields(nodeData);
      // Create a set of schema field names to avoid duplicates
      const schemaFieldNames = new Set(schemaFields.map((field) => field.id));
      const availableData = nodeId ? getAvailableDataForNode(nodeId) : null;

      if (!nodeId) {
        // ignore
      }

      const allFields =
        variables.length > 0
          ? variables.map((variable) => ({
              id: variable,
              label: variable,
              type: "string",
              placeholder: `Enter ${variable}`,
              required: true,
              defaultValue: "",
              source: "config",
            }))
          : schemaFields;

      setInputFields(allFields);
      setAvailableData(availableData);

      // Initialize form data with available data from workflow execution context
      const initialData: Record<string, string> = {};

      // Get the node's own output to check for previous test input values
      const nodeOutput = nodeId ? getNodeOutput(nodeId) : null;
      const output = nodeOutput ? nodeOutput.output : null;

      allFields.forEach((field) => {
        let previousValueStr = "";
        if (output && typeof output === "object" && output !== null) {
          const outputObj = output as Record<string, unknown>;
          const prevValue = outputObj[`session.${field.id}`];
          previousValueStr = prevValue !== undefined ? String(prevValue) : "";
        }
        let defaultValue: string = field.defaultValue || previousValueStr || "";

        // Try to get value from availableData using the field ID as a path
        if (availableData) {
          const availableValue = getValueFromPath(availableData, field.id);
          if (availableValue !== undefined) {
            // Handle different types properly
            if (field.type === "boolean") {
              defaultValue = String(availableValue);
            } else if (typeof availableValue === "string") {
              defaultValue = availableValue;
            } else if (typeof availableValue === "object") {
              defaultValue = JSON.stringify(availableValue);
            } else {
              defaultValue = String(availableValue);
            }
          } else {
            // ignore
          }
        }

        initialData[field.id] = defaultValue;
      });
      setFormData(initialData);
    }
  }, [isOpen, nodeData, nodeId, getAvailableDataForNode, getNodeOutput, nodeType]);

  // Extract all {{var}} parameters from node config
  const extractVariablesFromNodeConfig = (data: NodeData): string[] => {
    // Convert node data to string and extract variables
    const configString = JSON.stringify(data);
    const extractedVars = extractDynamicVariables(configString);

    // Convert Set to Array
    return Array.from(extractedVars);
  };

  // Extract inputSchema fields from node data
  const extractInputSchemaFields = (
    data: NodeData
  ): Array<{
    id: string;
    label: string;
    type: string;
    placeholder?: string;
    required?: boolean;
    defaultValue?: string;
    source: string;
  }> => {
    const fields: Array<{
      id: string;
      label: string;
      type: string;
      placeholder?: string;
      required?: boolean;
      defaultValue?: string;
      source: string;
    }> = [];

    // Check if the node has inputSchema
    if ("inputSchema" in data && data.inputSchema) {
      Object.entries(data.inputSchema).forEach(([key, schema]) => {
        fields.push({
          id: key,
          label: key,
          type: schema.type,
          placeholder: schema.description
            ? `Enter ${schema.description}`
            : `Enter ${key}`,
          required: schema.required || false,
          defaultValue: schema.defaultValue || "",
          source: "inputSchema",
        });
      });
    }

    return fields;
  };

  const handleInputChange = (id: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [id]: value,
    }));
  };

  const handleRun = async () => {
    setIsLoading(true);
    setError(null);
    setOutput(null);

    try {
      // Parse input values based on their schema types
      const parsedData: Record<string, unknown> = {};
      
      // Get inputSchema if available
      const inputSchema = "inputSchema" in nodeData && nodeData.inputSchema 
        ? nodeData.inputSchema 
        : null;

      for (const field of inputFields) {
        const value = formData[field.id];
        
        if (value === undefined || value === "") {
          // Skip empty values unless required
          if (!field.required) {
            continue;
          }
        }

        // Try to get the schema field type from inputSchema
        let fieldType: SchemaType = field.type as SchemaType;
        if (inputSchema && field.id in inputSchema) {
          const schemaField = inputSchema[field.id] as SchemaField;
          fieldType = schemaField.type;
        }

        // Parse the value based on its type
        try {
          parsedData[field.id] = parseInputValue(value || "", fieldType);
        } catch (err) {
          // If parsing fails, validate JSON for object/array types
          if (fieldType === "object" || fieldType === "array") {
            try {
              JSON.parse(value);
              parsedData[field.id] = value; // Keep as string if JSON is valid but parsing failed
            } catch (jsonErr) {
              setError(`Invalid JSON in field "${field.label}"`);
              setIsLoading(false);
              return;
            }
          } else {
            // For other types, use the original value
            parsedData[field.id] = value;
          }
        }
      }

      const response = await testNode({
        input_data: parsedData,
        node_type: nodeType,
        node_config: nodeData,
      });

      setOutput(response);

      // Update the node output in the workflow execution context
      if (nodeId && response && response.output !== undefined) {
        // Extract the actual output from the response
        const nodeOutput = response.output;

        const truncatedOutput = truncateNodeOutput(nodeOutput) as string | Record<string, unknown>;

        // Update the workflow execution context
        updateNodeOutput(
          nodeId,
          truncatedOutput,
          nodeType,
          nodeData.name || nodeType
        );
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      setOutput({ status: "error", output: errorMessage });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] w-full overflow-hidden">
        <DialogHeader>
          <DialogTitle>{`Test ${nodeName}`}</DialogTitle>
          <p className="text-sm text-gray-500">
            Test this node using sample inputs or extracted variables.
          </p>
          {!nodeId && (
            <div className="mt-2 p-2 bg-yellow-50 rounded-md border border-yellow-200">
              <div className="text-xs text-yellow-700">
                ⚠️ Warning: Node ID not provided. Input fields cannot be
                prefilled with available data from the workflow.
              </div>
            </div>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-y-auto overflow-x-hidden p-1 max-h-[calc(85vh-180px)] min-w-0">
          <div className="flex flex-col space-y-4 min-w-0 w-full">
            {/* Input Fields */}
            {inputFields.length > 0 ? (
              <div className="space-y-4">
                <Label>Input Variables</Label>
                {inputFields.map((field) => (
                  <div key={field.id} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={field.id}>
                        {field.label}
                        {field.required && (
                          <span className="text-red-500 ml-1">*</span>
                        )}
                      </Label>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                          {field.source || "config"}
                        </span>
                        {availableData &&
                          getValueFromPath(availableData, field.id) !==
                            undefined && (
                            <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-200">
                              Prefilled
                            </span>
                          )}
                      </div>
                    </div>
                    {field.type === "textarea" || field.type === "text" ? (
                      <Textarea
                        id={field.id}
                        placeholder={field.placeholder}
                        value={formData[field.id] || ""}
                        onChange={(e) =>
                          handleInputChange(field.id, e.target.value)
                        }
                        disabled={isLoading}
                        className={`flex-1 ${
                          availableData &&
                          getValueFromPath(availableData, field.id) !==
                            undefined
                            ? "border-blue-300 bg-blue-50"
                            : ""
                        }`}
                      />
                    ) : field.type === "boolean" ? (
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id={field.id}
                          checked={formData[field.id] === "true"}
                          onCheckedChange={(checked) =>
                            handleInputChange(
                              field.id,
                              checked ? "true" : "false"
                            )
                          }
                          disabled={isLoading}
                        />
                        <Label
                          htmlFor={field.id}
                          className="text-sm font-normal"
                        >
                          {field.placeholder || `Enable ${field.label}`}
                        </Label>
                      </div>
                    ) : field.type === "object" || field.type === "array" ? (
                      <div className="space-y-2">
                        <Textarea
                          id={field.id}
                          placeholder={
                            field.placeholder ||
                            `Enter ${
                              field.type === "object"
                                ? "JSON object"
                                : "JSON array"
                            }`
                          }
                          value={formData[field.id] || ""}
                          onChange={(e) =>
                            handleInputChange(field.id, e.target.value)
                          }
                          disabled={isLoading}
                          className={`flex-1 font-mono text-xs ${
                            availableData &&
                            getValueFromPath(availableData, field.id) !==
                              undefined
                              ? "border-blue-300 bg-blue-50"
                              : ""
                          }`}
                          rows={3}
                        />
                        <p className="text-xs text-gray-500">
                          {field.type === "object"
                            ? 'Enter a valid JSON object (e.g., {"key": "value"})'
                            : 'Enter a valid JSON array (e.g., ["item1", "item2"])'}
                        </p>
                      </div>
                    ) : (
                      <Input
                        id={field.id}
                        type={field.type === "number" ? "number" : "text"}
                        placeholder={field.placeholder}
                        value={formData[field.id] || ""}
                        onChange={(e) =>
                          handleInputChange(field.id, e.target.value)
                        }
                        disabled={isLoading}
                        className={`flex-1 ${
                          availableData &&
                          getValueFromPath(availableData, field.id) !==
                            undefined
                            ? "border-blue-300 bg-blue-50"
                            : ""
                        }`}
                      />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 italic">
                No variables found in node configuration or inputSchema
              </div>
            )}

            {/* Output Section */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label>Output</Label>
                {isLoading && (
                  <div className="text-xs text-blue-500">Loading...</div>
                )}
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 p-2 rounded-md text-xs mb-2">
                  {error}
                </div>
              )}
              {output === null ? (
                <div className="whitespace-pre-wrap">No output yet</div>
              ) : typeof output === "string" ? (
                <div className="whitespace-pre-wrap">{output}</div>
              ) : (
                <JsonViewer
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  data={output as any}
                  onCopy={(data) => {
                    navigator.clipboard.writeText(
                      JSON.stringify(data, null, 2)
                    );
                  }}
                />
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            <X className="h-4 w-4 mr-2" />
            Close
          </Button>
          <Button
            onClick={handleRun}
            disabled={
              isLoading ||
              inputFields.some((field) => field.required && !formData[field.id])
            }
          >
            <Play className="h-4 w-4 mr-2" />
            Run Test
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
