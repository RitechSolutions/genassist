import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { Checkbox } from "@/components/checkbox";
import {
  Loader2,
  Send,
  ChevronDown,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { testWorkflow, WorkflowTestResponse } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { NodeSchema, SchemaField } from "../types/schemas";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { getValueFromPath, parseInputValue, truncateNodeOutput, valueToString } from "../utils/helpers";
import JsonViewer from "@/components/JsonViewer";

interface WorkflowTestDialogProps {
  isOpen: boolean;
  onClose: () => void;
  workflowName: string;
  workflow: Workflow | null;
  onUpdateWorkflowTestInputs?: (inputs: Record<string, string>) => void;
}

const WorkflowTestDialog: React.FC<WorkflowTestDialogProps> = ({
  isOpen,
  onClose,
  workflowName,
  workflow,
  onUpdateWorkflowTestInputs,
}) => {
  const [testInput, setTestInputs] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [response, setResponse] = useState<WorkflowTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [inputSchema, setInputSchema] = useState<NodeSchema | null>(null);
  const [showMetadata, setShowMetadata] = useState(false);
  const [prefilledFields, setPrefilledFields] = useState<Set<string>>(
    new Set()
  );

  const { state: executionState } = useWorkflowExecution();

  // Find chatInputNode and get its inputSchema
  useEffect(() => {
    if (workflow) {
      const chatInputNode = workflow.nodes.find((node) =>
        node.type.includes("InputNode")
      );
      if (chatInputNode && chatInputNode.data.inputSchema) {
        setInputSchema(chatInputNode.data.inputSchema);

        // Initialize test inputs with session data or saved test inputs
        const initialInputs: Record<string, string> = {};
        const prefilled = new Set<string>();

        Object.entries(chatInputNode.data.inputSchema).forEach(([key, field]: [string, SchemaField]) => {
          let value: unknown = undefined;

          // First try to get value from session data
          if (
            executionState?.session &&
            typeof executionState.session === "object"
          ) {
            const sessionValue = getValueFromPath(executionState.session, key);
            if (sessionValue !== undefined) {
              value = sessionValue;
              prefilled.add(key);
            }
          }

          // Fallback to saved test inputs if no session value
          if (value === undefined) {
            const savedValue = workflow?.testInput?.[key];
            if (savedValue !== undefined) {
              value = savedValue;
            }
          }

          // Convert to string for input fields
          initialInputs[key] = value !== undefined 
            ? valueToString(value, field.type)
            : "";
        });

        setTestInputs(initialInputs);
        setPrefilledFields(prefilled);
      }
    }
  }, [workflow, executionState?.session]);

  // Handle test workflow
  const handleTestWorkflow = async () => {
    if (!workflow) {
      return;
    }

    // Check if all required fields are filled
    if (inputSchema) {
      const missingRequired = Object.entries(inputSchema)
        .filter(([_, field]: [string, SchemaField]) => field.required)
        .some(([key, field]: [string, SchemaField]) => {
          const value = testInput[key];
          if (!value) return true;
          // For string types, check if trimmed value is empty
          if (field.type === "string") {
            return !value.trim();
          }
          // For other types, just check if value exists
          return false;
        });

      if (missingRequired) {
        setError("Please fill in all required fields");
        return;
      }
    }

    setTesting(true);
    setError(null);
    setResponse(null);

    try {
      // Parse input values based on their schema types
      const parsedInputs: Record<string, unknown> = {
        message: testInput.message || "",
        thread_id: "test",
      };

      if (inputSchema) {
        Object.entries(inputSchema).forEach(([key, field]: [string, SchemaField]) => {
          if (key === "message") {
            // message is already handled above
            return;
          }
          const value = testInput[key];
          if (value !== undefined && value !== "") {
            try {
              parsedInputs[key] = parseInputValue(value, field.type);
            } catch (err) {
              // If parsing fails, use the original string value
              console.warn(`Failed to parse ${key} as ${field.type}, using string value`);
              parsedInputs[key] = value;
            }
          }
        });
      } else {
        // Fallback: include all testInput values as-is if no schema
        Object.entries(testInput).forEach(([key, value]) => {
          if (key !== "message") {
            parsedInputs[key] = value;
          }
        });
      }

      const response = await testWorkflow({
        input_data: parsedInputs,
        workflow: workflow,
      });
      // Truncate arrays in the output to a default of 4 items
      const truncatedResponse = {
        ...response,
        output: truncateNodeOutput(response.output),
      };
      setResponse(truncatedResponse as WorkflowTestResponse);
      // Update workflow.testInput with the latest changes
      if (onUpdateWorkflowTestInputs) {
        onUpdateWorkflowTestInputs(testInput);
      }
    } catch (err) {
      setError("Failed to test workflow. Please try again.");
    } finally {
      setTesting(false);
    }
  };

  // Get message role icon and color
  const getMessageStyle = (role: string) => {
    switch (role) {
      case "user":
        return {
          bgColor: "bg-blue-50",
          textColor: "text-blue-800",
          borderColor: "border-blue-100",
        };
      case "assistant":
        return {
          bgColor: "bg-green-50",
          textColor: "text-green-800",
          borderColor: "border-green-100",
        };
      case "system":
        return {
          bgColor: "bg-gray-50",
          textColor: "text-gray-800",
          borderColor: "border-gray-100",
        };
      default:
        return {
          bgColor: "bg-gray-50",
          textColor: "text-gray-800",
          borderColor: "border-gray-100",
        };
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-7xl max-h-[95vh] w-full overflow-hidden">
        <DialogHeader>
          <DialogTitle>Test Workflow: {workflowName}</DialogTitle>
          <DialogDescription>
            Test your workflow configuration with sample inputs
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto overflow-x-hidden p-1 max-h-[calc(85vh-180px)] min-w-0">
          <div className="flex flex-col space-y-4 min-w-0 w-full">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="test-input-message">
                  Message
                  {inputSchema?.message?.required && (
                    <span className="text-red-500 ml-1">*</span>
                  )}
                </Label>
                {prefilledFields.has("message") && (
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-200">
                    📝 Session
                  </span>
                )}
              </div>
              <Input
                id="test-input-message"
                placeholder="Enter your message"
                value={testInput.message || ""}
                onChange={(e) =>
                  setTestInputs((prev) => ({
                    ...prev,
                    message: e.target.value,
                  }))
                }
                disabled={testing}
                className={`flex-1 ${
                  prefilledFields.has("message")
                    ? "border-blue-300 bg-blue-50"
                    : ""
                }`}
              />
            </div>

            {inputSchema && Object.keys(inputSchema).length > 1 && (
              <div className="space-y-2">
                <Button
                  variant="ghost"
                  className="w-full flex items-center justify-between p-2"
                  onClick={() => setShowMetadata(!showMetadata)}
                >
                  <span className="font-medium">Metadata</span>
                  {showMetadata ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>

                {showMetadata && (
                  <div className="pl-4 space-y-4 border-l-2 border-gray-200">
                    {Object.entries(inputSchema)
                      .filter(([key]) => key !== "message")
                      .map(([key, field]: [string, SchemaField]) => {
                        const isBoolean = field.type === "boolean";
                        const isObjectOrArray = field.type === "object" || field.type === "array";
                        const isNumber = field.type === "number";
                        
                        return (
                          <div key={key} className="space-y-2">
                            <div className="flex items-center justify-between">
                              <Label htmlFor={`test-input-${key}`}>
                                {field.description || key}
                                {field.required && (
                                  <span className="text-red-500 ml-1">*</span>
                                )}
                                {field.type !== "string" && (
                                  <span className="text-xs text-gray-500 ml-2">
                                    ({field.type})
                                  </span>
                                )}
                              </Label>
                              {prefilledFields.has(key) && (
                                <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-200">
                                  📝 Session
                                </span>
                              )}
                            </div>
                            {isBoolean ? (
                              <div className="flex items-center space-x-2">
                                <Checkbox
                                  id={`test-input-${key}`}
                                  checked={testInput[key] === "true" || testInput[key] === "1"}
                                  onCheckedChange={(checked) =>
                                    setTestInputs((prev) => ({
                                      ...prev,
                                      [key]: String(checked),
                                    }))
                                  }
                                  disabled={testing}
                                  className={
                                    prefilledFields.has(key)
                                      ? "border-blue-300"
                                      : ""
                                  }
                                />
                                <Label
                                  htmlFor={`test-input-${key}`}
                                  className="text-sm font-normal cursor-pointer"
                                >
                                  {testInput[key] === "true" || testInput[key] === "1"
                                    ? "True"
                                    : "False"}
                                </Label>
                              </div>
                            ) : isObjectOrArray ? (
                              <Textarea
                                id={`test-input-${key}`}
                                placeholder={`Enter ${field.description || key} as JSON`}
                                value={testInput[key] || ""}
                                onChange={(e) =>
                                  setTestInputs((prev) => ({
                                    ...prev,
                                    [key]: e.target.value,
                                  }))
                                }
                                disabled={testing}
                                className={`flex-1 font-mono text-sm ${
                                  prefilledFields.has(key)
                                    ? "border-blue-300 bg-blue-50"
                                    : ""
                                }`}
                                rows={4}
                              />
                            ) : (
                              <Input
                                id={`test-input-${key}`}
                                type={isNumber ? "number" : "text"}
                                placeholder={`Enter ${field.description || key}`}
                                value={testInput[key] || ""}
                                onChange={(e) =>
                                  setTestInputs((prev) => ({
                                    ...prev,
                                    [key]: e.target.value,
                                  }))
                                }
                                disabled={testing}
                                className={`flex-1 ${
                                  prefilledFields.has(key)
                                    ? "border-blue-300 bg-blue-50"
                                    : ""
                                }`}
                              />
                            )}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                onClick={handleTestWorkflow}
                disabled={testing || !workflow}
                className="flex items-center gap-2"
              >
                {testing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Test
              </Button>
              <Button
                onClick={() => setIsDebugMode(!isDebugMode)}
                className="flex items-center gap-2"
                style={{
                  backgroundColor: isDebugMode ? "#000" : "#fff",
                  color: isDebugMode ? "#fff" : "#000",
                }}
              >
                {"Debug"}
              </Button>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 p-3 rounded-md">
                {error}
              </div>
            )}

            {response && (
              <div className="space-y-2">
                <Label>
                  Response {response?.status === "success" ? "✅" : "❌"}
                </Label>

                {response?.status === "success" && (
                  <div className="border rounded-md overflow-hidden">
                    <div className="max-h-80 overflow-y-auto p-2 space-y-3">
                      {/* Add the user's test message first */}
                      <div
                        className={`p-3 rounded-md border ${
                          getMessageStyle("user").bgColor
                        } ${getMessageStyle("user").borderColor}`}
                      >
                        <div className="font-semibold mb-1 text-xs uppercase text-blue-600">
                          You
                        </div>
                        <div className="whitespace-pre-wrap">
                          {typeof response.input === "object" &&
                          response.input !== null
                            ? JSON.stringify(response.input, null, 2)
                            : response.input}
                        </div>
                      </div>

                      {/* Show each message in the result */}
                      {!isDebugMode ? (
                        <div
                          className={`p-3 rounded-md border bg-gray-50 border-gray-100`}
                        >
                          <div
                            className={`font-semibold mb-1 text-xs uppercase text-green-600`}
                          >
                            Response
                          </div>
                          {/* Explicitly surface SQL node parameters if present */}
                          {typeof response.output === "object" &&
                            response.output &&
                            (response.output as Record<string, unknown>)
                              .parameters && (
                              <div className="mb-3 p-2 bg-white border rounded">
                                <div className="text-xs font-semibold mb-1">
                                  Parameters
                                </div>
                                <div className="text-xs text-gray-700">
                                  datasource_id:{" "}
                                  {((
                                    (response.output as Record<string, unknown>)
                                      .parameters as Record<string, unknown>
                                  )?.datasource_id as string) || ""}
                                </div>
                                <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto mt-1">
                                  {JSON.stringify(
                                    ((
                                      (
                                        response.output as Record<
                                          string,
                                          unknown
                                        >
                                      ).parameters as Record<string, unknown>
                                    )?.node_parameters as Record<
                                      string,
                                      unknown
                                    >) || {},
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                            )}
                          {typeof response.output === "string" ? (
                            <div className="whitespace-pre-wrap">
                              {response.output}
                            </div>
                          ) : (
                            <JsonViewer
                              data={response.output}
                              onCopy={(data) => {
                                navigator.clipboard.writeText(
                                  JSON.stringify(data, null, 2)
                                );
                              }}
                            />
                          )}
                        </div>
                      ) : (
                        <div
                          className={`p-3 rounded-md border bg-gray-50 border-gray-100`}
                        >
                          <div
                            className={`font-semibold mb-1 text-xs uppercase text-green-600`}
                          >
                            Debug View
                          </div>
                          <JsonViewer
                            data={response}
                            onCopy={(data) => {
                              navigator.clipboard.writeText(
                                JSON.stringify(data, null, 2)
                              );
                            }}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {response.status !== "success" && (
                  <div className="border border-red-200 rounded-md p-3 bg-red-50 text-sm text-red-600">
                    Error processing workflow
                  </div>
                )}

                {response.workflow_id && (
                  <div className="mt-2 text-xs text-gray-500">
                    Workflow ID: {response.workflow_id}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default WorkflowTestDialog;
