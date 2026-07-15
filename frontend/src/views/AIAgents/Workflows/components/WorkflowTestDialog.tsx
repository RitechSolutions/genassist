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
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import { Checkbox } from "@/components/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/resizable";
import {
  Loader2,
  Send,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  ClipboardList,
  Volume2,
  MessageSquareText,
  Bug,
  Network,
} from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { HumanInTheLoopFormField } from "../types/nodes";
import { testWorkflow, WorkflowTestResponse } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { NodeSchema, SchemaField } from "../types/schemas";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { getValueFromPath, parseInputValue, truncateNodeOutput, valueToString } from "../utils/helpers";
import { useAudioCapture } from "../hooks/useAudioCapture";
import { getAudioUrl, stripAudioDataForDisplay } from "../hooks/useAudioTest";
import { STTAudioInput } from "./TestInputFields";
import JsonViewer from "@/components/JsonViewer";
import NodeExecutionView from "./execution/NodeExecutionView";

type TestViewMode = "response" | "debug" | "execution";

// Node types that consume audio input from the workflow's session state.
const AUDIO_INPUT_NODE_TYPES = ["voiceAgentNode", "sttNode"];

interface PausedFormSchema {
  message: string;
  fields: HumanInTheLoopFormField[];
  node_id: string;
}

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
  const [audioData, setAudioData] = useState<{ data: string; format: string } | null>(null);
  const [viewMode, setViewMode] = useState<TestViewMode>("response");
  const [inputSchema, setInputSchema] = useState<NodeSchema | null>(null);
  const [showMetadata, setShowMetadata] = useState(false);
  const [prefilledFields, setPrefilledFields] = useState<Set<string>>(
    new Set()
  );

  // Dynamic pause/resume state
  const [pausedFormSchema, setPausedFormSchema] = useState<PausedFormSchema | null>(null);
  const [pausedThreadId, setPausedThreadId] = useState<string | null>(null);
  const [pausedNodeId, setPausedNodeId] = useState<string | null>(null);
  const [humanInTheLoopFormData, setHumanInTheLoopFormData] = useState<Record<string, string>>({});
  // Generate thread_id function
  const generateThreadId = () => {
    const newThreadId = uuidv4();
    setTestInputs((prev) => ({
      ...prev,
      thread_id: newThreadId,
    }));
  };

  const { state: executionState } = useWorkflowExecution();

  // Show audio capture when the workflow contains a node that consumes audio.
  const hasAudioNode = !!workflow?.nodes.some((n) =>
    AUDIO_INPUT_NODE_TYPES.includes(n.type)
  );

  const {
    isRecording,
    audioFileName,
    fileInputRef,
    handleAudioFileUpload,
    startRecording,
    stopRecording,
  } = useAudioCapture({
    convertToWav: true,
    onAudio: (data, format) => setAudioData({ data, format }),
    onError: setError,
  });

  // Find chatInputNode and get its inputSchema
  useEffect(() => {
    if (workflow && isOpen) {
      const chatInputNode = workflow.nodes.find((node) =>
        node.type.includes("InputNode")
      );
      if (chatInputNode && chatInputNode.data.inputSchema) {
        setInputSchema(chatInputNode.data.inputSchema);

        // Initialize test inputs with session data or saved test inputs
        const initialInputs: Record<string, string> = {};
        const prefilled = new Set<string>();

        Object.entries(chatInputNode.data.inputSchema).forEach(([key, field]: [string, SchemaField]) => {
          // Skip stateful parameters
          if (field.stateful) {
            return;
          }

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

        // Always restore thread_id from saved testInput (it may not be in node's inputSchema)
        if (workflow?.testInput?.thread_id !== undefined && workflow.testInput.thread_id !== "") {
          initialInputs.thread_id = valueToString(workflow.testInput.thread_id, "string");
        }

        setTestInputs(initialInputs);
        setPrefilledFields(prefilled);
      }
    }
  }, [workflow, executionState?.session, isOpen]);

  // Start on the Response view each time the dialog opens, so the input pane
  // (which is hidden on Debug/Execution) is always available on open.
  useEffect(() => {
    if (isOpen) {
      setViewMode("response");
    }
  }, [isOpen]);

  // Check if a response indicates a paused workflow
  const isPausedResponse = (res: WorkflowTestResponse): boolean => {
    return res.status === "awaiting_input" || res.state?.status === "paused";
  };

  // Extract pause info from the response
  const extractPauseInfo = (res: WorkflowTestResponse) => {
    // New path: form_schema is inside res.output (HumanInTheLoopNode returns it as output)
    const output = res.output;
    const formSchema = (
      (output != null && typeof output === "object" && (output as Record<string, unknown>).form_schema) ||
      res.form_schema ||
      res.state?.paused_form_schema
    ) as PausedFormSchema | undefined;
    const nodeId = (
      (output != null && typeof output === "object" && (output as Record<string, unknown>).node_id) ||
      res.node_id
    ) as string | undefined;
    const threadId = (res.thread_id || res.state?.input?.thread_id) as string | undefined;
    return { formSchema, threadId, nodeId };
  };

  // Handle paused response from test or resume
  const handlePausedResponse = (res: WorkflowTestResponse) => {
    const { formSchema, threadId, nodeId } = extractPauseInfo(res);
    if (!formSchema || !formSchema.fields) {
      setError("Workflow paused but no form schema received");
      return;
    }
    setPausedFormSchema(formSchema);
    setPausedThreadId(threadId || null);
    setPausedNodeId(nodeId || formSchema.node_id || null);
    // Initialize form data for the paused node's fields
    const initialData: Record<string, string> = {};
    formSchema.fields.forEach((f) => { initialData[f.name] = ""; });
    setHumanInTheLoopFormData(initialData);
  };

  // Handle completed response from test or resume
  const handleCompletedResponse = (res: WorkflowTestResponse) => {
    setPausedFormSchema(null);
    setPausedThreadId(null);
    setPausedNodeId(null);
    const truncatedResponse = {
      ...res,
      output: truncateNodeOutput(res.output),
    };
    setResponse(truncatedResponse as WorkflowTestResponse);
    if (onUpdateWorkflowTestInputs) {
      onUpdateWorkflowTestInputs(testInput);
    }
  };

  // Handle test workflow
  const handleTestWorkflow = async () => {
    if (!workflow) {
      return;
    }

    // Check if all required fields are filled
    if (inputSchema) {
      const missingRequired = Object.entries(inputSchema)
        .filter(([key, field]: [string, SchemaField]) => {
          // Exclude stateful parameters from validation
          return field.required && !field.stateful;
        })
        .some(([key, field]: [string, SchemaField]) => {
          // A recorded/uploaded voice message stands in for the text message.
          if (key === "message" && audioData) return false;
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
    setPausedFormSchema(null);

    try {
      // Parse input values based on their schema types
      const parsedInputs: Record<string, unknown> = {
        message: testInput.message || "",
        thread_id: testInput.thread_id || uuidv4(),
      };

      if (inputSchema) {
        Object.entries(inputSchema).forEach(([key, field]: [string, SchemaField]) => {
          if (key === "message") {
            // message is already handled above
            return;
          }
          // Skip stateful parameters
          if (field.stateful) {
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

      // Attach a recorded/uploaded voice message so audio-consuming nodes
      // (Voice Agent, STT) receive it from the workflow session state.
      // Mirror the real chat flow: `audio_data` is a base64 string and the
      // format is carried separately (the Chat Input node wraps these into the
      // audio payload its downstream nodes consume).
      if (audioData) {
        parsedInputs.audio_data = audioData.data;
        parsedInputs.audio_format = audioData.format;
        if (!parsedInputs.message) {
          parsedInputs.message = "[Voice message]";
        }
      }

      const res = await testWorkflow({
        input_data: parsedInputs,
        workflow: workflow,
      });

      if (!res) {
        setError("No response received from server");
        return;
      }

      if (isPausedResponse(res)) {
        handlePausedResponse(res);
      } else {
        handleCompletedResponse(res);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to test workflow: ${msg}`);
    } finally {
      setTesting(false);
    }
  };

  // Handle resuming a paused workflow with user input
  const handleResumeWorkflow = async () => {
    if (!workflow || !pausedThreadId || !pausedFormSchema) return;

    setTesting(true);
    setError(null);

    try {
      // Parse form values based on field types
      const parsedValues: Record<string, unknown> = {};
      pausedFormSchema.fields.forEach((field) => {
        const val = humanInTheLoopFormData[field.name] || "";
        if (field.type === "number") {
          parsedValues[field.name] = val ? Number(val) : 0;
        } else if (field.type === "boolean") {
          parsedValues[field.name] = val === "true";
        } else {
          parsedValues[field.name] = val;
        }
      });

      const res = await testWorkflow({
        input_data: {
          thread_id: pausedThreadId,
          human_in_the_loop_from_form: parsedValues,
          ...(pausedNodeId && { human_in_the_loop_node_id: pausedNodeId }),
        },
        workflow: workflow,
      });

      if (!res) {
        setError("No response received from server");
        return;
      }

      if (isPausedResponse(res)) {
        handlePausedResponse(res);
      } else {
        handleCompletedResponse(res);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Failed to resume workflow: ${msg}`);
    } finally {
      setTesting(false);
    }
  };

  // Reset test state for a fresh run
  const handleStartOver = () => {
    setPausedFormSchema(null);
    setPausedThreadId(null);
    setPausedNodeId(null);
    setHumanInTheLoopFormData({});
    setResponse(null);
    setError(null);
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
      <DialogContent className="flex h-[88vh] max-h-[88vh] w-full max-w-7xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Test Workflow: {workflowName}</DialogTitle>
          <DialogDescription>
            Test your workflow configuration with sample inputs
          </DialogDescription>
        </DialogHeader>

        {/* Two-column layout: inputs on the left (resizable), results on the right. */}
        <div className="min-h-0 flex-1">
          <ResizablePanelGroup
            direction="horizontal"
            autoSaveId="workflow-test-dialog"
            className="rounded-md border border-gray-200"
          >
            {/* LEFT — inputs: message, metadata, run action / paused form. */}
            <ResizablePanel
              id="inputs"
              order={1}
              defaultSize={33}
              minSize={24}
              maxSize={55}
            >
              <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
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
                  <RichInput
                    id="test-input-message"
                    placeholder="Enter your message"
                    value={testInput.message || ""}
                    onChange={(e) =>
                      setTestInputs((prev) => ({
                        ...prev,
                        message: e.target.value,
                      }))
                    }
                    disabled={testing || !!pausedFormSchema}
                    className={`flex-1 ${
                      prefilledFields.has("message")
                        ? "border-blue-300 bg-blue-50"
                        : ""
                    }`}
                  />
                </div>

                {hasAudioNode && !pausedFormSchema && (
                  <STTAudioInput
                    isLoading={testing}
                    isRecording={isRecording}
                    audioFileName={audioFileName}
                    fileInputRef={fileInputRef}
                    onFileUpload={handleAudioFileUpload}
                    onStartRecording={startRecording}
                    onStopRecording={stopRecording}
                  />
                )}

                {inputSchema && (
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
                        {/* Thread ID field - always show so saved testInput.thread_id is visible and usable */}
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <Label htmlFor="test-input-thread_id">
                              Thread ID
                              {inputSchema?.thread_id?.required && (
                                <span className="text-red-500 ml-1">*</span>
                              )}
                            </Label>
                          </div>
                          <div className="flex gap-2">
                            <RichInput
                              id="test-input-thread_id"
                              type="text"
                              placeholder="Thread ID will be auto-generated"
                              value={testInput.thread_id || ""}
                              readOnly
                              disabled={testing}
                              className="flex-1 bg-gray-50 cursor-not-allowed"
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              onClick={generateThreadId}
                              disabled={testing}
                              title="Generate new Thread ID"
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {Object.entries(inputSchema)
                          .filter(([key, field]: [string, SchemaField]) => {
                            // Exclude message, stateful parameters, and thread_id
                            return (
                              key !== "message" &&
                              !field.stateful &&
                              key !== "thread_id"
                            );
                          })
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
                                      disabled={testing || !!pausedFormSchema}
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
                                  <RichTextarea
                                    id={`test-input-${key}`}
                                    placeholder={`Enter ${field.description || key} as JSON`}
                                    value={testInput[key] || ""}
                                    onChange={(e) =>
                                      setTestInputs((prev) => ({
                                        ...prev,
                                        [key]: e.target.value,
                                      }))
                                    }
                                    disabled={testing || !!pausedFormSchema}
                                    className={`flex-1 font-mono text-sm ${
                                      prefilledFields.has(key)
                                        ? "border-blue-300 bg-blue-50"
                                        : ""
                                    }`}
                                    rows={4}
                                  />
                                ) : (
                                  <RichInput
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
                                    disabled={testing || !!pausedFormSchema}
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

                {/* Primary action — run the workflow. */}
                {!pausedFormSchema && (
                  <Button
                    onClick={handleTestWorkflow}
                    disabled={testing || !workflow}
                    className="flex w-full items-center justify-center gap-2"
                  >
                    {testing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    {testing ? "Running…" : "Test"}
                  </Button>
                )}

                {/* Paused Workflow — Dynamic User Input Form */}
                {pausedFormSchema && (
                  <div className="space-y-4 p-4 border-2 border-blue-200 rounded-lg bg-blue-50/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ClipboardList className="h-5 w-5 text-blue-600" />
                        <span className="font-medium text-blue-700">
                          Workflow Paused — User Input Required
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-gray-500"
                        onClick={handleStartOver}
                      >
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Start Over
                      </Button>
                    </div>

                    {pausedFormSchema.message && (
                      <p className="text-sm text-gray-600">{pausedFormSchema.message}</p>
                    )}

                    <div className="space-y-3">
                      {pausedFormSchema.fields.map((field) => {
                        const fieldKey = `paused-${field.name}`;
                        const val = humanInTheLoopFormData[field.name] || "";
                        const onChange = (v: string) =>
                          setHumanInTheLoopFormData((prev) => ({ ...prev, [field.name]: v }));

                        return (
                          <div key={field.name} className="space-y-1">
                            <Label htmlFor={fieldKey} className="text-sm">
                              {field.label}
                              {field.required && (
                                <span className="text-red-500 ml-1">*</span>
                              )}
                              <span className="text-xs text-gray-500 ml-2">
                                ({field.type})
                              </span>
                            </Label>
                            {field.type === "boolean" ? (
                              <div className="flex items-center space-x-2">
                                <Checkbox
                                  id={fieldKey}
                                  checked={val === "true"}
                                  onCheckedChange={(checked) =>
                                    onChange(String(checked))
                                  }
                                  disabled={testing}
                                />
                                <Label
                                  htmlFor={fieldKey}
                                  className="text-sm font-normal cursor-pointer"
                                >
                                  {val === "true" ? "True" : "False"}
                                </Label>
                              </div>
                            ) : field.type === "select" &&
                              field.options &&
                              field.options.length > 0 ? (
                              <Select
                                value={val}
                                onValueChange={onChange}
                                disabled={testing}
                              >
                                <SelectTrigger className="text-sm">
                                  <SelectValue
                                    placeholder={
                                      field.placeholder ||
                                      `Select ${field.label}`
                                    }
                                  />
                                </SelectTrigger>
                                <SelectContent>
                                  {field.options.map((opt) => (
                                    <SelectItem
                                      key={opt.value}
                                      value={opt.value}
                                    >
                                      {opt.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            ) : (
                              <RichInput
                                id={fieldKey}
                                type={
                                  field.type === "number"
                                    ? "number"
                                    : field.type === "date"
                                    ? "date"
                                    : "text"
                                }
                                placeholder={
                                  field.placeholder ||
                                  `Enter ${field.label}`
                                }
                                value={val}
                                onChange={(e) => onChange(e.target.value)}
                                disabled={testing}
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>

                    <div className="flex gap-2">
                      <Button
                        onClick={handleResumeWorkflow}
                        disabled={
                          testing ||
                          pausedFormSchema.fields.some(
                            (f) => f.required && !humanInTheLoopFormData[f.name]
                          )
                        }
                        className="flex items-center gap-2"
                      >
                        {testing ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Send className="h-4 w-4" />
                        )}
                        Resume
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle />

            {/* RIGHT — results: view switcher + response / debug / execution. */}
            <ResizablePanel id="results" order={2} defaultSize={67} minSize={45}>
              <div className="flex h-full flex-col overflow-hidden">
                {/* Header: result label + status badge + view switcher */}
                <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-semibold text-gray-700">
                      Result
                    </Label>
                    {response && (
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                          response.status === "success"
                            ? "border-green-200 bg-green-50 text-green-700"
                            : "border-red-200 bg-red-50 text-red-600"
                        }`}
                      >
                        {response.status === "success" ? "Success" : "Failed"}
                      </span>
                    )}
                  </div>
                  <Tabs
                    value={viewMode}
                    onValueChange={(v) => setViewMode(v as TestViewMode)}
                  >
                    <TabsList className="h-9">
                      <TabsTrigger
                        value="response"
                        className="gap-1.5 px-3 text-xs"
                      >
                        <MessageSquareText className="h-3.5 w-3.5" />
                        Response
                      </TabsTrigger>
                      <TabsTrigger value="debug" className="gap-1.5 px-3 text-xs">
                        <Bug className="h-3.5 w-3.5" />
                        Debug
                      </TabsTrigger>
                      <TabsTrigger
                        value="execution"
                        className="gap-1.5 px-3 text-xs"
                      >
                        <Network className="h-3.5 w-3.5" />
                        Execution
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>

                {/* Content — fills the panel and scrolls internally. */}
                <div className="min-h-0 flex-1 overflow-y-auto p-4">
                  {viewMode === "execution" ? (
                    <NodeExecutionView
                      response={response}
                      testing={testing}
                      error={error}
                      workflow={workflow}
                    />
                  ) : testing && !response ? (
                    <div className="flex h-full items-center justify-center gap-2 text-sm text-gray-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running the workflow…
                    </div>
                  ) : error ? (
                    <div className="bg-red-50 border border-red-200 text-red-600 p-3 rounded-md">
                      {error}
                    </div>
                  ) : response ? (
                    <div className="space-y-3">
                      {response?.status === "success" ? (
                        <>
                          {/* The user's test message */}
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

                          {/* Response or raw Debug view */}
                          {viewMode === "response" ? (
                            <div className="p-3 rounded-md border bg-gray-50 border-gray-100">
                              <div className="font-semibold mb-1 text-xs uppercase text-green-600">
                                Response
                              </div>
                              {/* Play synthesized voice when the response carries audio */}
                              {(() => {
                                const audioUrl = getAudioUrl(response.output);
                                return audioUrl ? (
                                  <div className="mb-3 space-y-2">
                                    <div className="flex items-center gap-2 text-sm text-teal-700 bg-teal-50 border border-teal-200 rounded-md px-3 py-2">
                                      <Volume2 className="h-4 w-4" />
                                      Voice response
                                    </div>
                                    <audio controls className="w-full" src={audioUrl} />
                                  </div>
                                ) : null;
                              })()}
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
                                  data={stripAudioDataForDisplay(response.output) as unknown as never}
                                  onCopy={(data) => {
                                    navigator.clipboard.writeText(
                                      JSON.stringify(data, null, 2)
                                    );
                                  }}
                                />
                              )}
                            </div>
                          ) : (
                            <div className="p-3 rounded-md border bg-gray-50 border-gray-100">
                              <div className="font-semibold mb-1 text-xs uppercase text-green-600">
                                Debug View
                              </div>
                              <JsonViewer
                                data={stripAudioDataForDisplay(response) as unknown as never}
                                onCopy={(data) => {
                                  navigator.clipboard.writeText(
                                    JSON.stringify(data, null, 2)
                                  );
                                }}
                              />
                            </div>
                          )}
                        </>
                      ) : (
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
                  ) : (
                    /* Empty state — nothing run yet */
                    <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-gray-500">
                      <MessageSquareText className="h-6 w-6" aria-hidden="true" />
                      <div className="text-sm font-medium">No results yet</div>
                      <div className="text-xs">
                        Enter a message and run a test to see the response here.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </ResizablePanel>
          </ResizablePanelGroup>
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
