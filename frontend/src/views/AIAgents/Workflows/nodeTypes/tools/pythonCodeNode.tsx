import React, { useState, useEffect, useCallback } from "react";
import { Position, NodeProps } from "reactflow";
import { PythonCodeNodeData } from "../../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Code, Play, Settings } from "lucide-react";
import { TestDialog, TestInputField } from "../../components/TestDialog";
import { HandleTooltip } from "../../components/HandleTooltip";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/mode-json";
import { getNodeColors } from "../../utils/nodeColors";
import { PythonCodeDialog } from "../../components/PythonCodeDialog";
import { testPythonCode } from "@/services/workflows";
import { NodeSchema } from "../../types/schemas";

const PythonCodeNode: React.FC<NodeProps<PythonCodeNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const colors = getNodeColors("pythonCodeNode");
  const [name, setName] = useState(data.name || "Python Code");
  const [description, setDescription] = useState(
    data.description || "Execute Python code in a sandboxed environment"
  );
  const [code, setCode] = useState(data.code);
  const [inputSchema, setInputSchema] = useState(data.inputSchema || {});
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const saveConfiguration = useCallback(() => {
    if (data.updateNodeData) {
      // Create input schema from test parameters

      const updatedData: Partial<PythonCodeNodeData> = {
        ...data,
        name,
        description,
        code,
        inputSchema,
      };

      data.updateNodeData(id, updatedData);
    }
  }, [data, name, description, code, inputSchema, id]);

  // Save configuration whenever relevant state changes
  useEffect(() => {
    saveConfiguration();
  }, [name, description, code, inputSchema]);


  const handleTestCode = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
    setSuccess(null);
    setTestResult(null);
    try {
      const results = await testPythonCode(data, inputs);
      setTestResult(JSON.stringify(results, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };


  // Generate input fields for test dialog
  const generateInputFields = (inputSchema: NodeSchema): TestInputField[] => {
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

  // Get code preview (first few lines)
  const getCodePreview = () => {
    console.log("code", code);
    if (!code) return "";
    const lines = code?.split("\n");
    if (lines?.length <= 3) return code;
    return lines?.slice(0, 3).join("\n") + "\n...";
  };

  const onUpdate = (updatedData: PythonCodeNodeData) => {
    setInputSchema(updatedData.inputSchema || {});
    setCode(updatedData.code || "");
  };

  return (
    <>
      <div
        className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
          selected ? "border-blue-500" : "border-gray-200"
        }`}
      >
        {/* Node header */}
        <div
          className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}
        >
          <div className="flex items-center">
            <Code className={`h-4 w-4 text-white mr-2`} />
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={`text-sm font-medium h-6 py-0 bg-transparent border-transparent ${colors.focus} text-white ${colors.placeholder}`}
              maxLength={40}
            />
          </div>
          <div className="flex space-x-1">
            <Button
              size="icon"
              variant="ghost"
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Edit code"
              onClick={() => setIsEditDialogOpen(true)}
            >
              <Settings className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className={`h-6 w-6 text-white ${colors.hover}`}
              title="Test code"
              onClick={() => setIsTestDialogOpen(true)}
            >
              <Play className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Node content */}
        <div className="p-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this Python code does"
              />
            </div>

            <div className="space-y-2">
              <Label>Code Preview</Label>
              <div className="p-4 bg-gray-50 rounded-lg font-mono text-sm">
                <pre className="whitespace-pre-wrap">{getCodePreview()}</pre>
              </div>
            </div>
          </div>
        </div>

        {/* Handles */}
        {data.handlers
          ?.filter((handler) => handler.type === "source")
          .map((handler, index) => (
            <HandleTooltip
              key={handler.id}
              type={handler.type}
              position={Position.Right}
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
              position={Position.Left}
              id={handler.id}
              nodeId={id}
              compatibility={handler.compatibility}
              style={{ top: `${(index + 1) * (100 / data.handlers.length)}%` }}
            />
          ))}
      </div>

      {/* Edit Dialog */}
      <PythonCodeDialog
        isOpen={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        data={data}
        onUpdate={onUpdate}
      />
      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${name}`}
        description="Fill in the required values for testing the Python code"
        inputFields={generateInputFields(inputSchema)}
        onRun={handleTestCode}
        output={testResult || ""}
        isLoading={isLoading}
        error={error}
      />
    </>
  );
};

export default PythonCodeNode;
