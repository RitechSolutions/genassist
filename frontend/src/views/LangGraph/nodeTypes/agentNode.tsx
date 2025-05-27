import React, { useState, useEffect, useCallback } from "react";
import {
  Handle,
  Position,
  NodeProps,
  useReactFlow,
  useUpdateNodeInternals,
} from "reactflow";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { ScrollArea } from "@/components/scroll-area";
import { Save, Play, Brain } from "lucide-react";
import { TestDialog, TestInputField } from "../components/TestDialog";
import { HandleTooltip } from "../components/HandleTooltip";
import { createSimpleSchema } from "../types/schemas";
import { AgentNodeData, NodeHandler } from "../types/nodes";
import { ModelConfig, ModelConfiguration } from "../components/ModelConfiguration";
import { getNodeColors } from "../utils/nodeColors";
const AgentNode: React.FC<NodeProps<AgentNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const { getNodes, getEdges } = useReactFlow();
  const [config, setConfig] = useState<ModelConfig>({
    providerId: data.providerId || "openai",
    localConfig: {
      ...data.localConfig,
    },
  });
  const [inputText, setInputText] = useState(data.inputText || "");
  const [outputText, setOutputText] = useState(data.outputText || "");
  const [mode, setMode] = useState<"normal" | "json-parsing">(
    data.jsonParsing ? "json-parsing" : "normal"
  );
  const [isDirty, setIsDirty] = useState(false);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [testOutput, setTestOutput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const updateNodeInternals = useUpdateNodeInternals();
  const colors = getNodeColors('agentNode');

  // Get available tools from connected nodes
  const getAvailableTools = useCallback(() => {
    const edges = getEdges();
    const connectedToolNodes = getNodes().filter(
      (node) =>
        ["apiToolNode", "knowledgeBaseNode"].includes(node.type) &&
        edges.some((edge) => edge.target === id && edge.source === node.id)
    );

    return connectedToolNodes.map((node) => ({
      id: node.id,
      name: node.data.name || "Unnamed Tool",
      description: node.data.description || "No description available",
      category: node.type === "apiToolNode" ? "API Tool" : "Knowledge Base",
    }));
  }, [getNodes, getEdges, id]);

  // Mark form as dirty when any field changes
  useEffect(() => {
    setTimeout(() => {
      saveChanges()
    }, 1000);
  }, [config, mode]);

 
  const saveChanges = useCallback(() => {
    console.log(data);

    const handlers = [
      {
        id: "input_prompt",
        type: "target",
        compatibility: "text",
      },  
      {
        id: "input_tools",
        type: "target",
        compatibility: "tools",
      },
      {
        id: "output",
        type: "source",
        compatibility: mode === "json-parsing" ? "json" : "text",
      },
    ];
    
    data.updateNodeData<AgentNodeData>(id, {
      ...data,
      handlers: handlers as NodeHandler[],
      label: "Agent",
      ...config,
      jsonParsing: mode === "json-parsing",
    });
    updateNodeInternals(id);

  }, [data, id, updateNodeInternals, mode, config]);



  // Handle receiving prompt input
  const onPromptReceived = useCallback(
    (text: string) => {
      setInputText(text);
      // Here you would normally call the LLM to process the input with the tools
      // For now we'll just echo the input
      const tools = getAvailableTools();
      setOutputText(
        `Processed input: ${text}\nAvailable tools: ${tools.length}`
      );
    },
    [getAvailableTools]
  );

  // Handle receiving tools input
  const onToolsReceived = useCallback(
    (
      tools: Array<{
        id: string;
        name: string;
        description: string;
        category: string;
      }>
    ) => {
      // Update the available tools
      if (data.updateNodeData) {
        data.updateNodeData<AgentNodeData>(id, {
          availableTools: tools,
        });
      }
    },
    [id, data]
  );

  // Register the input handlers
  useEffect(() => {
    if (data.onPromptReceived !== onPromptReceived) {
      data.onPromptReceived = onPromptReceived;
    }
    if (data.onToolsReceived !== onToolsReceived) {
      data.onToolsReceived = onToolsReceived;
    }
  }, [data, onPromptReceived, onToolsReceived]);

  // Test the node
  const handleTest = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
    try {
      const testInput = inputs.prompt || "";
      const tools = getAvailableTools();

      // Simulate agent processing
      const output = {
        response:
          mode === "json-parsing"
            ? {
                message: `Processed input: ${testInput}`,
                tools: tools.map((t) => t.name),
                confidence: 0.95,
              }
            : `Processed input: ${testInput}\nAvailable tools: ${tools.length}`,
      };

      setTestOutput(JSON.stringify(output, null, 2));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred during testing"
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Define input fields for testing
  const inputFields: TestInputField[] = [
    {
      id: "prompt",
      label: "Test Prompt",
      type: "text",
      placeholder: "Enter a test prompt...",
      required: true,
    },
  ];

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-80 ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <div className={`flex justify-between items-center px-4 py-2 border-b ${colors.header}`}>
          <div className="flex items-center">
            <Brain className={`h-4 w-4 text-white mr-2`} />
            <div className="text-sm font-medium text-white">Agent</div>
          </div>
        </div>


        <div className="space-y-4 p-4">
          {/* Model Configuration */}
          <ModelConfiguration
            id={id}
            config={config}
            onConfigChange={setConfig}
          />

          {/* Mode Selection */}
          <div className="flex justify-between items-center">
            <Label className="font-medium text-sm">Mode</Label>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={mode === "normal" ? "default" : "outline"}
                className="h-7 px-2 text-xs"
                onClick={() => setMode("normal")}
              >
                Normal
              </Button>
              <Button
                size="sm"
                variant={mode === "json-parsing" ? "default" : "outline"}
                className="h-7 px-2 text-xs"
                onClick={() => setMode("json-parsing")}
              >
                JSON Parsing
              </Button>
            </div>
          </div>

          {/* Available Tools */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <Label>Available Tools</Label>
            <ScrollArea className="h-32 border rounded-md p-2 bg-gray-50">
              {getAvailableTools().map((tool) => (
                <div key={tool.id} className="p-2 rounded-md mb-2 bg-white">
                  <div className="text-sm font-medium">{tool.name}</div>
                  <div className="text-xs text-gray-600">
                    {tool.description}
                  </div>
                </div>
              ))}
            </ScrollArea>
          </div>

          {/* Input/Output Display */}
          {inputText && (
            <div className="space-y-2 pt-2 border-t border-gray-200">
              <Label>Input</Label>
              <ScrollArea className="h-32 border rounded-md p-2 bg-gray-50">
                <div className="text-sm whitespace-pre-wrap">{inputText}</div>
              </ScrollArea>
            </div>
          )}

          {outputText && (
            <div className="space-y-2 pt-2 border-t border-gray-200">
              <Label>Output</Label>
              <ScrollArea className="h-32 border rounded-md p-2 bg-blue-50">
                <div className="text-sm whitespace-pre-wrap">{outputText}</div>
              </ScrollArea>
            </div>
          )}
        </div>

        {/* Render all handlers */}
        {data.handlers
          ?.filter((handler) => handler.type === "source")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
        {data.handlers
          ?.filter((handler) => handler.type === "target")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={
                handler.type === "source" ? Position.Right : Position.Left
              }
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
      </div>

      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title="Test Agent"
        description="Test the agent with a sample prompt"
        inputFields={inputFields}
        onRun={handleTest}
        output={testOutput}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default AgentNode;
