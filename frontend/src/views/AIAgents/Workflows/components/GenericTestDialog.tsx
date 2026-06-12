import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Play, X } from "lucide-react";
import { NodeData, HumanInTheLoopNodeData } from "../types/nodes";
import { testNode } from "@/services/workflows";
import { extractDynamicVariables, getValueFromPath, parseInputValue, truncateNodeOutput } from "../utils/helpers";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { SchemaField, SchemaType } from "../types/schemas";
import { useAudioTest } from "../hooks/useAudioTest";
import { TestInputFields, STTAudioInput } from "./TestInputFields";
import { TestOutputSection } from "./TestOutputSection";

export interface GenericTestInputField {
  id: string;
  label: string;
  type: string;
  placeholder?: string;
  required?: boolean;
  defaultValue?: string;
  source?: string;
  options?: Array<{ value: string; label: string }>;
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
  const [fieldTypes, setFieldTypes] = useState<Record<string, SchemaType>>({});
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

  const {
    isSTTNode, isAudioInputNode, isRecording, audioFileName, fileInputRef,
    getAudioKey, handleAudioFileUpload, startRecording, stopRecording,
  } = useAudioTest({ nodeType, nodeData, setFormData, setError });

  const { updateNodeOutput, getAvailableDataForNode, getNodeOutput } =
    useWorkflowExecution();

  // Extract variables from node config when dialog opens
  useEffect(() => {
    if (isOpen && nodeData) {
      // Special handling for humanInTheLoopNode — populate fields from form_fields config
      if (nodeType === "humanInTheLoopNode" && "form_fields" in nodeData) {
        const uiNodeData = nodeData as HumanInTheLoopNodeData;
        const formFields = uiNodeData.form_fields || [];
        const humanInTheLoopFields: GenericTestInputField[] = formFields.map((field) => ({
          id: field.name,
          label: field.label,
          type: field.type,
          placeholder: field.placeholder || `Enter ${field.label}`,
          required: field.required || false,
          defaultValue: "",
          source: "form_fields",
          options: field.type === "select" ? field.options : undefined,
        }));
        setInputFields(humanInTheLoopFields);
        setAvailableData(nodeId ? getAvailableDataForNode(nodeId) : null);
        const initialData: Record<string, string> = {};
        humanInTheLoopFields.forEach((field) => { initialData[field.id] = ""; });
        setFormData(initialData);
        return;
      }

      let variables = extractVariablesFromNodeConfig(nodeData);
      variables = variables.filter((v) => v !== "direct_input");
      const schemaFields = extractInputSchemaFields(nodeData);
      // Create a set of schema field names to avoid duplicates
      const schemaFieldNames = new Set(schemaFields.map((field) => field.id));
      const availableData = nodeId ? getAvailableDataForNode(nodeId) : null;

      if (!nodeId) {
        // ignore
      }

      // Filter out stateful parameters and conversation_history from variables
      const filteredVariables = variables.filter((v) => {
        // Check if this variable is a stateful parameter in inputSchema
        if ("inputSchema" in nodeData && nodeData.inputSchema) {
          const schema = nodeData.inputSchema[v];
          if (schema?.stateful) {
            return false;
          }
        }
        return true;
      });

      const allFields =
        filteredVariables.length > 0
          ? filteredVariables.map((variable) => ({
              id: variable,
              label: variable,
              type: "string",
              placeholder: `Enter ${variable}`,
              required: false,
              defaultValue: "",
              source: "config",
            }))
          : schemaFields;

      setInputFields(allFields);
      setAvailableData(availableData);

      // Initialize field types from the field definitions
      const initialTypes: Record<string, SchemaType> = {};
      allFields.forEach((field) => {
        initialTypes[field.id] = (field.type as SchemaType) || "string";
      });
      setFieldTypes(initialTypes);

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
        // Skip stateful parameters and conversation_history
        if (schema.stateful) {
          return;
        }
        
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

  const handleTypeChange = (id: string, newType: SchemaType) => {
    setFieldTypes((prev) => ({
      ...prev,
      [id]: newType,
    }));
  };

  const allFieldsOptional = nodeType === "humanInTheLoopNode" && inputFields.length > 0 && inputFields.every((f) => !f.required);

  const handleSkip = async () => {
    setIsLoading(true);
    setError(null);
    setOutput(null);

    try {
      const response = await testNode({
        input_data: {},
        node_type: nodeType,
        node_config: nodeData,
      });

      if (response && response.output !== undefined) {
        const truncatedOutput = truncateNodeOutput(response.output) as string | Record<string, unknown>;
        setOutput(Object.assign({}, response, { output: truncatedOutput }));
        if (nodeId) {
          updateNodeOutput(nodeId, truncatedOutput, nodeType, nodeData.name || nodeType);
        }
      } else {
        setOutput(response);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      setOutput({ status: "error", output: errorMessage });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRun = async () => {
    setIsLoading(true);
    setError(null);
    setOutput(null);

    try {
      // Parse input values based on their schema types
      const parsedData: Record<string, unknown> = {};

      // For audio-input nodes (STT, Voice Agent), pass a structured audio dict
      if (isAudioInputNode) {
        const key = getAudioKey();
        const audioData = formData[key];
        if (audioData) {
          try {
            parsedData[key] = JSON.parse(audioData);
          } catch {
            parsedData[key] = audioData;
          }
        }
      }

      // Get inputSchema if available
      const inputSchema = "inputSchema" in nodeData && nodeData.inputSchema
        ? nodeData.inputSchema
        : null;

      for (const field of inputFields) {
        // Skip stateful parameters and conversation_history
        if (inputSchema && field.id in inputSchema) {
          const schemaField = inputSchema[field.id] as SchemaField;
          if (schemaField.stateful) {
            continue;
          }
        }
        
        const value = formData[field.id];

        if (value === undefined || value === "") {
          // Skip empty values unless required
          if (!field.required) {
            continue;
          }
        }

        // Determine the field type for parsing
        let fieldType: SchemaType = fieldTypes[field.id] || (field.type as SchemaType) || "string";
        // For inputSchema fields, prefer the schema type
        if (inputSchema && field.id in inputSchema) {
          const schemaField = inputSchema[field.id] as SchemaField;
          fieldType = schemaField.type;
        }
        // Map humanInTheLoopNode field types to schema-compatible types
        if (field.source === "form_fields") {
          const typeMap: Record<string, SchemaType> = {
            text: "string", select: "string", date: "string",
            number: "number", boolean: "boolean",
          };
          fieldType = typeMap[field.type] || "string";
        }

        // Parse the value based on its type
        try {
          parsedData[field.id] = parseInputValue(value || "", fieldType);
        } catch (err) {
          // If parsing fails, validate JSON for object/array types
          if (fieldType === "object" || fieldType === "array") {
            try {
              JSON.parse(value);
              parsedData[field.id] = value;
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


      if (response && response.output !== undefined) {
        const truncatedOutput = truncateNodeOutput(response.output) as string | Record<string, unknown>;

        // Store the full output in state but only display the truncated version
        setOutput(Object.assign({}, response, { output: truncatedOutput }));

        if (nodeId) {
            updateNodeOutput(
              nodeId,
              truncatedOutput,
              nodeType,
              nodeData.name || nodeType
            );
        }
      } else {
        setOutput(response);
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
      <DialogContent className="max-w-2xl max-h-[85vh] w-full overflow-hidden" style={{ zIndex: 1201 }}>
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
            {isAudioInputNode && (
              <STTAudioInput
                isLoading={isLoading}
                isRecording={isRecording}
                audioFileName={audioFileName}
                fileInputRef={fileInputRef}
                onFileUpload={handleAudioFileUpload}
                onStartRecording={startRecording}
                onStopRecording={stopRecording}
              />
            )}

            {!isSTTNode && (
              <TestInputFields
                inputFields={inputFields}
                formData={formData}
                fieldTypes={fieldTypes}
                availableData={availableData}
                isLoading={isLoading}
                onInputChange={handleInputChange}
                onTypeChange={handleTypeChange}
              />
            )}

            <TestOutputSection
              output={output}
              error={error}
              isLoading={isLoading}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            <X className="h-4 w-4 mr-2" />
            Close
          </Button>
          {allFieldsOptional && (
            <Button variant="outline" onClick={handleSkip} disabled={isLoading}>
              Skip
            </Button>
          )}
          <Button
            onClick={handleRun}
            disabled={
              isLoading ||
              (isSTTNode ? !formData[getAudioKey()] : inputFields.some((field) => field.required && !formData[field.id]))
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
