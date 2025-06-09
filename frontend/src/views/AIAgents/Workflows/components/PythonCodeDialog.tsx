import React, { useState, useEffect } from "react";
import { ClipboardList, Play, Sparkles } from "lucide-react";

import AceEditor from "react-ace";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/mode-json";
import { toast } from "react-hot-toast";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

import { PythonCodeNodeData } from "../types/nodes";
import { NodeSchema, SchemaField } from "../types/schemas";
import { ParameterSection } from "./ParameterSection";
import { generatePythonTemplate, testPythonCode } from "@/services/workflows";
import { TestDialog, TestInputField } from "./TestDialog";

interface PythonCodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: PythonCodeNodeData;
  onUpdate: (data: PythonCodeNodeData) => void;
}

export const PythonCodeDialog: React.FC<PythonCodeDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [inputSchema, setInputSchema] = useState<NodeSchema>(
    data.inputSchema || {}
  );
  const [code, setCode] = useState(data.code);
  const [loading, setLoading] = useState(false);
  const [isTestDialogOpen, setIsTestDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);


  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Update data.inputSchema when dynamicParams changes
  useEffect(() => {
    onUpdate({
      ...data,
      inputSchema: inputSchema,
      code: code, // Also update the code when parameters change
    });
  }, [inputSchema, code]);

  const addItem = (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    template: SchemaField
  ) => {
    const newName = `param_${Object.keys(inputSchema).length + 1}`;
    setter((prev) => {
      const newParams = {
        ...prev,
        [newName]: template,
      };
      // Update parent component immediately
      onUpdate({
        ...data,
        inputSchema: newParams,
        code: code,
      });
      return newParams;
    });
  };

  const removeItem = (
    setter: React.Dispatch<React.SetStateAction<NodeSchema>>,
    name: string
  ) => {
    setter((prev) => {
      const newParams = { ...prev };
      delete newParams[name];
      // Update parent component immediately
      onUpdate({
        ...data,
        inputSchema: newParams,
        code: code,
      });
      return newParams;
    });
  };

  const handleGenerateTemplate = async () => {
    try {


      const properties: Record<string, unknown> = {};
      Object.entries(inputSchema).forEach(([name, field]) => {
        properties[name] = {
          type: field.type,
          description: field.description,
          required: field.required,
        };
      });

      const result = await generatePythonTemplate(inputSchema);

      if (result && typeof result === "object" && "template" in result) {
        setCode(result.template as string);
      } 
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTestCode = async (inputs: Record<string, string>) => {
    setIsLoading(true);
    setError(null);
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

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-4xl h-[90vh] flex flex-col overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Python Code</DialogTitle>
            <DialogDescription>
              Write and test your Python code here
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 flex flex-col">
            <ParameterSection
              dynamicParams={inputSchema}
              setDynamicParams={setInputSchema}
              addItem={addItem}
              removeItem={removeItem}
            />

            <div className="editor-card relative flex flex-col p-6 gap-2.5 h-[600px] bg-[#1C1C1C] backdrop-blur-[20px] rounded-[16px]">
              <div className="editor-controls absolute top-4 right-4 flex gap-2 z-10">
                <button
                  className="editor-button flex justify-center items-center p-1 w-[28px] h-[28px] rounded-[8px] hover:bg-white/10"
                  onClick={() => {
                    navigator.clipboard.writeText(code);
                    toast.success("Code copied");
                  }}
                >
                  <ClipboardList className="w-5 h-5 text-white" />
                </button>
                {/* Generate Template Button */}
                <button
                  className="editor-button flex justify-center items-center p-1 w-[28px] h-[28px] rounded-[8px] hover:bg-white/10"
                  onClick={handleGenerateTemplate}
                  disabled={loading}
                  title="Generate Template"
                  type="button"
                >
                  <Sparkles className="w-5 h-5 text-white" />
                </button>
                <button
                  className="editor-button flex justify-center items-center p-1 w-[28px] h-[28px] rounded-[8px] hover:bg-white/10"
                  onClick={() => setIsTestDialogOpen(true)}
                  title="Test Code"
                  type="button"
                >
                  <Play className="w-5 h-5 text-white" />
                </button>
              </div>
              <div className="inner-ace w-full h-full rounded-[8px]">
                <AceEditor
                  mode="python"
                  theme="twilight"
                  name="python-editor"
                  value={code}
                  onChange={setCode}
                  width="100%"
                  height="100%"
                  setOptions={{
                    showLineNumbers: true,
                    tabSize: 4,
                    useWorker: false,
                    enableBasicAutocompletion: true,
                    enableLiveAutocompletion: true,
                    enableSnippets: true,
                    showPrintMargin: false,
                    fontSize: 14,
                  }}
                />
              </div>
            </div>

            <div className="bg-gray-50 rounded-2xl p-4 mt-4 border-b border-gray-200">
              <h2 className="text-sm font-semibold mb-4">Code Instructions:</h2>
              <ul className="list-disc list-inside text-sm text-gray-500 space-y-2">
                <li>
                  Use <code className="bg-gray-100 px-1 rounded">params</code>{" "}
                  dictionary to access input parameters
                </li>
                <li>
                  Store your return value in{" "}
                  <code className="bg-gray-100 px-1 rounded">result</code>{" "}
                  variable
                </li>
                <li>Available libraries: json, requests, datetime, math, re</li>
                <li>
                  Code runs in a sandboxed environment with limited resources
                </li>
                <li>Maximum execution time: 5 seconds</li>
                <li>
                  Example:{" "}
                  <code className="bg-gray-100 px-1 rounded">
                    result = params['input'] + " processed"
                  </code>
                </li>
              </ul>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <TestDialog
        isOpen={isTestDialogOpen}
        onClose={() => setIsTestDialogOpen(false)}
        title={`Test ${data.name}`}
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
