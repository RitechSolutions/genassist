import React, { useState, useEffect, useRef } from "react";
import { PreprocessingNodeData } from "../../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { useToast } from "@/components/use-toast";
import {
  Save,
  Sparkles,
  Code,
  Settings,
  Search,
  Plus,
  X,
  GripVertical,
  Play,
} from "lucide-react";
import { toast as hotToast } from "react-hot-toast";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-twilight";
import { generatePythonTemplate } from "@/services/workflows";
import { DraggableAceEditor } from "../../components/custom/DraggableAceEditor";
import { DraggableInput } from "../../components/custom/DraggableInput";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/tabs";
import { NodeConfigPanel } from "../../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "../base";
import {
  PreprocessingConfig,
  PreprocessingStep,
  PreprocessingStepType,
  parsePythonCodeToConfig,
  generatePythonCodeFromConfig,
  BASE_PYTHON_TEMPLATE,
  createPreprocessingStep,
  getStepTypeDisplayName,
  StepConfig,
  ColumnFilterStepConfig,
  MissingValueHandlingStepConfig,
  OutlierHandlingStepConfig,
  CategoricalEncodingStepConfig,
  FeatureEngineeringStepConfig,
} from "./preprocessingConfig";
import { ColumnFilter } from "./components/ColumnFilter";
import { MissingValueHandler } from "./components/MissingValueHandler";
import { OutlierHandler } from "./components/OutlierHandler";
import { CategoricalEncodingHandler } from "./components/CategoricalEncodingHandler";
import { FeatureEngineeringHandler } from "./components/FeatureEngineeringHandler";
import { CSVAnalysisDisplay } from "./components/CSVAnalysisDisplay";
import { analyzeCSV, CSVAnalysisResult } from "@/services/mlModels";
import { useWorkflowExecution } from "../../context/WorkflowExecutionContext";
import { extractDynamicVariables, getValueFromPath } from "../../utils/helpers";
import { Switch } from "@/components/switch";

type PreprocessingDialogProps = BaseNodeDialogProps<
  PreprocessingNodeData,
  PreprocessingNodeData
>;

export const PreprocessingDialog: React.FC<PreprocessingDialogProps> = (
  props
) => {
  const { isOpen, onClose, data, onUpdate, nodeId } = props;
  const { getAvailableDataForNode } = useWorkflowExecution();

  const [name, setName] = useState(data.name || "Data Preprocessing");
  const [pythonCode, setPythonCode] = useState(data.pythonCode || "");
  const [fileUrl, setFileUrl] = useState(data.fileUrl || "");
  const [loading, setLoading] = useState(false);
  const [isPromptDialogOpen, setIsPromptDialogOpen] = useState(false);
  const [templatePrompt, setTemplatePrompt] = useState("");
  const [mode, setMode] = useState<"configure" | "code">("configure");
  const [config, setConfig] = useState<PreprocessingConfig>({ steps: [] });
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<
    Record<string, CSVAnalysisResult>
  >({});
  const [runningStepId, setRunningStepId] = useState<string | null>(null);
  const isGeneratingCodeRef = useRef(false);
  const isInitializingRef = useRef(true);
  const pythonCodeRef = useRef<string>("");
  const { toast } = useToast();

  // Parse Python code to config when switching to configure mode
  const handleModeChange = (newMode: "configure" | "code") => {
    if (newMode === "configure") {
      if (pythonCode) {
        try {
          const parsedConfig = parsePythonCodeToConfig(pythonCode);
          setConfig(parsedConfig);
        } catch (error) {
          console.error("Failed to parse Python code:", error);
          setConfig({ steps: [] });
        }
      } else {
        setConfig({ steps: [] });
      }
    }
    setMode(newMode);
  };

  // Update ref when pythonCode changes
  useEffect(() => {
    pythonCodeRef.current = pythonCode;
  }, [pythonCode]);

  // Generate Python code from config when config changes in configure mode
  useEffect(() => {
    if (mode === "configure" && !isGeneratingCodeRef.current && !isInitializingRef.current) {
      isGeneratingCodeRef.current = true;
      const existingCode = pythonCodeRef.current || BASE_PYTHON_TEMPLATE;
      const generatedCode = generatePythonCodeFromConfig(config, existingCode);
      setPythonCode(generatedCode);
      pythonCodeRef.current = generatedCode;
      setTimeout(() => {
        isGeneratingCodeRef.current = false;
      }, 100);
    }
  }, [config, mode]);

  useEffect(() => {
    if (isOpen) {
      isInitializingRef.current = true;
      setName(data.name || "Data Preprocessing");
      const initialPythonCode = data.pythonCode || BASE_PYTHON_TEMPLATE;
      setPythonCode(initialPythonCode);
      pythonCodeRef.current = initialPythonCode;
      const newFileUrl = data.fileUrl || "";
      setFileUrl(newFileUrl);

      // Initialize analysis results - restore from persisted data
      if (data.stepAnalysisResults) {
        // Use stepAnalysisResults if available (new format)
        setAnalysisResults(data.stepAnalysisResults);
      } else if (data.analysisResult) {
        // Fallback to old format for backward compatibility
        setAnalysisResults({ initial: data.analysisResult });
      } else {
        setAnalysisResults({});
      }

      if (data.pythonCode) {
        try {
          const parsedConfig = parsePythonCodeToConfig(data.pythonCode);
          setConfig(parsedConfig);
        } catch (error) {
          setConfig({ steps: [] });
        }
      } else {
        setConfig({ steps: [] });
      }

      setTimeout(() => {
        isInitializingRef.current = false;
      }, 100);
    } else {
      isInitializingRef.current = true;
    }
  }, [isOpen, data]);

  useEffect(() => {
    if (!isInitializingRef.current && fileUrl) {
      // Clear all analysis results when file URL changes
      setAnalysisResults({});
    }
  }, [fileUrl]);

  const handleSave = () => {
    if (!pythonCode.trim()) {
      toast({
        title: "Validation Error",
        description: "Please provide Python preprocessing code",
        variant: "destructive",
      });
      return;
    }

    // Save all analysis results (initial + all step results)
    // Also keep analysisResult for backward compatibility (initial result)
    onUpdate({
      ...data,
      name,
      pythonCode,
      fileUrl,
      analysisResult: analysisResults.initial || undefined, // For backward compatibility
      stepAnalysisResults:
        Object.keys(analysisResults).length > 0 ? analysisResults : undefined,
    });
    onClose();
  };

  const handleGenerateTemplate = async (prompt?: string) => {
    try {
      setLoading(true);
      const result = await generatePythonTemplate({}, prompt);
      if (result && typeof result === "object" && "template" in result) {
        setPythonCode(result.template as string);
        hotToast.success("Template generated successfully.");
      }
    } catch (err) {
      hotToast.error("Failed to generate template.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeCSV = async () => {
    if (!fileUrl.trim()) {
      toast({
        title: "Validation Error",
        description: "Please provide a file URL to analyze",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsAnalyzing(true);

      let resolvedFileUrl = fileUrl;
      const variables = extractDynamicVariables(fileUrl);

      if (variables.size > 0 && nodeId) {
        const availableData = getAvailableDataForNode(nodeId);

        if (availableData) {
          variables.forEach((variable) => {
            const value = getValueFromPath(availableData, variable);
            if (value !== undefined) {
              const stringValue =
                typeof value === "string"
                  ? value
                  : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value);

              resolvedFileUrl = resolvedFileUrl.replace(
                new RegExp(`{{${variable}}}`, "g"),
                stringValue
              );
            }
          });
        }
      }

      const result = await analyzeCSV(resolvedFileUrl);
      // Store initial analysis result
      setAnalysisResults({ initial: result });

      toast({
        title: "Analysis Complete",
        description: `Found ${result.column_count} columns and ${result.row_count} rows`,
      });
    } catch (err) {
      console.error(err);
      toast({
        title: "Analysis Failed",
        description:
          err instanceof Error ? err.message : "Failed to analyze CSV file",
        variant: "destructive",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Generate code up to a specific step (inclusive)
  const generateCodeUpToStep = (stepId: string): string => {
    const stepIndex = config.steps.findIndex((step) => step.id === stepId);
    if (stepIndex === -1) {
      return pythonCodeRef.current || BASE_PYTHON_TEMPLATE;
    }

    // Create a config with only steps up to and including this step
    const partialConfig: PreprocessingConfig = {
      steps: config.steps.slice(0, stepIndex + 1),
    };

    const existingCode = pythonCodeRef.current || BASE_PYTHON_TEMPLATE;
    return generatePythonCodeFromConfig(partialConfig, existingCode);
  };

  // Run a specific step
  const handleRunStep = async (stepId: string) => {
    if (!fileUrl.trim()) {
      toast({
        title: "Validation Error",
        description: "Please provide a file URL to analyze",
        variant: "destructive",
      });
      return;
    }

    try {
      setRunningStepId(stepId);

      // Generate code up to this step
      const stepCode = generateCodeUpToStep(stepId);

      // Resolve file URL variables
      let resolvedFileUrl = fileUrl;
      const variables = extractDynamicVariables(fileUrl);

      if (variables.size > 0 && nodeId) {
        const availableData = getAvailableDataForNode(nodeId);

        if (availableData) {
          variables.forEach((variable) => {
            const value = getValueFromPath(availableData, variable);
            if (value !== undefined) {
              const stringValue =
                typeof value === "string"
                  ? value
                  : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value);

              resolvedFileUrl = resolvedFileUrl.replace(
                new RegExp(`{{${variable}}}`, "g"),
                stringValue
              );
            }
          });
        }
      }

      const result = await analyzeCSV(resolvedFileUrl, stepCode);
      // Store result for this specific step
      setAnalysisResults((prev) => ({
        ...prev,
        [stepId]: result,
      }));

      toast({
        title: "Step Execution Complete",
        description: `Step executed successfully. Found ${result.column_count} columns and ${result.row_count} rows`,
      });
    } catch (err) {
      console.error(err);
      toast({
        title: "Step Execution Failed",
        description:
          err instanceof Error ? err.message : "Failed to execute step",
        variant: "destructive",
      });
    } finally {
      setRunningStepId(null);
    }
  };

  // Step management functions
  const handleAddStep = (type: PreprocessingStepType) => {
    const newStep = createPreprocessingStep(type);
    setConfig((prevConfig) => ({
      ...prevConfig,
      steps: [...prevConfig.steps, newStep],
    }));
  };

  const handleRemoveStep = (stepId: string) => {
    setConfig((prevConfig) => {
      const stepIndex = prevConfig.steps.findIndex((step) => step.id === stepId);
      const newSteps = prevConfig.steps.filter((step) => step.id !== stepId);
      
      // Clear analysis results for this step and all subsequent steps
      setAnalysisResults((prev) => {
        const updated = { ...prev };
        // Remove result for this step
        delete updated[stepId];
        // Remove results for all steps after this one (they depend on previous steps)
        if (stepIndex >= 0) {
          newSteps.slice(stepIndex).forEach((step) => {
            delete updated[step.id];
          });
        }
        return updated;
      });
      
      return {
        ...prevConfig,
        steps: newSteps,
      };
    });
  };

  const handleToggleStep = (stepId: string, enabled: boolean) => {
    setConfig((prevConfig) => ({
      ...prevConfig,
      steps: prevConfig.steps.map((step) =>
        step.id === stepId ? { ...step, enabled } : step
      ),
    }));
  };

  const handleUpdateStepConfig = (stepId: string, newConfig: StepConfig) => {
    setConfig((prevConfig) => ({
      ...prevConfig,
      steps: prevConfig.steps.map((step) =>
        step.id === stepId ? { ...step, config: newConfig } : step
      ),
    }));
  };

  const handleMoveStep = (stepId: string, direction: "up" | "down") => {
    setConfig((prevConfig) => {
      const index = prevConfig.steps.findIndex((step) => step.id === stepId);
      if (index === -1) return prevConfig;

      const newIndex = direction === "up" ? index - 1 : index + 1;
      if (newIndex < 0 || newIndex >= prevConfig.steps.length) return prevConfig;

      const newSteps = [...prevConfig.steps];
      [newSteps[index], newSteps[newIndex]] = [
        newSteps[newIndex],
        newSteps[index],
      ];
      
      // Clear analysis results for moved step and all subsequent steps (they depend on order)
      setAnalysisResults((prev) => {
        const updated = { ...prev };
        const minIndex = Math.min(index, newIndex);
        // Clear results for all steps from the minimum moved index onwards
        newSteps.slice(minIndex).forEach((step) => {
          delete updated[step.id];
        });
        return updated;
      });
      
      return { ...prevConfig, steps: newSteps };
    });
  };

  // Get analysis result for a specific step (from previous step or initial)
  const getAnalysisResultForStep = (
    stepIndex: number
  ): CSVAnalysisResult | null => {
    if (stepIndex === 0) {
      // First step uses initial analysis result
      return analysisResults.initial || null;
    }

    // Get result from previous step
    const previousStep = config.steps[stepIndex - 1];
    if (previousStep && analysisResults[previousStep.id]) {
      return analysisResults[previousStep.id];
    }

    // Fallback to initial if previous step hasn't been run
    return analysisResults.initial || null;
  };

  // Render step configuration component
  const renderStepConfig = (step: PreprocessingStep, stepIndex: number) => {
    // Get analysis result from previous step
    const stepAnalysisResult = getAnalysisResultForStep(stepIndex);

    switch (step.type) {
      case "column_filter":
        return (
          <ColumnFilter
            config={{
              enabled: step.enabled,
              columns: (step.config as ColumnFilterStepConfig).columns,
            }}
            availableColumns={stepAnalysisResult?.column_names || []}
            onChange={(columnFilterConfig) => {
              handleUpdateStepConfig(step.id, {
                columns: columnFilterConfig.columns,
              });
            }}
          />
        );
      case "missing_value_handling":
        return (
          <MissingValueHandler
            config={{
              enabled: step.enabled,
              columns: (step.config as MissingValueHandlingStepConfig).columns,
            }}
            analysisResult={stepAnalysisResult}
            onChange={(missingValueConfig) => {
              handleUpdateStepConfig(step.id, {
                columns: missingValueConfig.columns,
              });
              if (missingValueConfig.enabled !== step.enabled) {
                handleToggleStep(step.id, missingValueConfig.enabled);
              }
            }}
          />
        );
      case "outlier_handling":
        return (
          <OutlierHandler
            config={{
              enabled: step.enabled,
              columns: (step.config as OutlierHandlingStepConfig).columns,
            }}
            analysisResult={stepAnalysisResult}
            onChange={(outlierConfig) => {
              handleUpdateStepConfig(step.id, {
                columns: outlierConfig.columns,
              });
              if (outlierConfig.enabled !== step.enabled) {
                handleToggleStep(step.id, outlierConfig.enabled);
              }
            }}
          />
        );
      case "categorical_encoding":
        return (
          <CategoricalEncodingHandler
            config={{
              enabled: step.enabled,
              columns: (step.config as CategoricalEncodingStepConfig).columns,
            }}
            analysisResult={stepAnalysisResult}
            onChange={(encodingConfig) => {
              handleUpdateStepConfig(step.id, {
                columns: encodingConfig.columns,
              });
              if (encodingConfig.enabled !== step.enabled) {
                handleToggleStep(step.id, encodingConfig.enabled);
              }
            }}
          />
        );
      case "feature_engineering":
        return (
          <FeatureEngineeringHandler
            config={{
              enabled: step.enabled,
              features: (step.config as FeatureEngineeringStepConfig).features,
            }}
            analysisResult={stepAnalysisResult}
            onChange={(feConfig) => {
              handleUpdateStepConfig(step.id, {
                features: feConfig.features,
              });
              if (feConfig.enabled !== step.enabled) {
                handleToggleStep(step.id, feConfig.enabled);
              }
            }}
          />
        );
      default:
        return null;
    }
  };

  const stepTypes: PreprocessingStepType[] = [
    "column_filter",
    "missing_value_handling",
    "outlier_handling",
    "categorical_encoding",
    "feature_engineering",
  ];

  return (
    <>
      <NodeConfigPanel
        isOpen={isOpen}
        onClose={onClose}
        className="w-[95vw] h-[95vh] max-w-[95vw] max-h-[95vh]"
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
          pythonCode,
          fileUrl,
        }}
      >
        <div className="space-y-4 overflow-y-auto max-h-[calc(95vh-200px)]">
          {/* Node Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Node Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter the name of this node"
              className="w-full"
            />
          </div>

          {/* File URL */}
          <div className="space-y-2">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <DraggableInput
                  id="fileUrl"
                  label="File URL"
                  value={fileUrl}
                  onChange={(e) => setFileUrl(e.target.value)}
                  placeholder="Enter file URL or drag variable"
                  className="w-full"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={handleAnalyzeCSV}
                disabled={isAnalyzing || !fileUrl.trim()}
                className="mb-0"
              >
                <Search className="h-4 w-4 mr-2" />
                {isAnalyzing ? "Analyzing..." : "Analyze"}
              </Button>
            </div>
            {analysisResults.initial && (
              <CSVAnalysisDisplay analysisResult={analysisResults.initial} />
            )}
          </div>

          {/* Mode Toggle */}
          <div className="space-y-2">
            <Label>Configuration Mode</Label>
            <Tabs
              value={mode}
              onValueChange={(v) => handleModeChange(v as "configure" | "code")}
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger
                  value="configure"
                  className="flex items-center gap-2"
                >
                  <Settings className="h-4 w-4" />
                  Configure
                </TabsTrigger>
                <TabsTrigger value="code" className="flex items-center gap-2">
                  <Code className="h-4 w-4" />
                  Code
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Code Mode */}
          {mode === "code" && (
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <Label>Python Code *</Label>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 text-xs"
                    onClick={() => setIsPromptDialogOpen(true)}
                    disabled={loading}
                  >
                    <Sparkles className="h-3 w-3 mr-1" />
                    Generate Template
                  </Button>
                </div>
              </div>
              <DraggableAceEditor
                id="python-editor"
                name="python-editor"
                mode="python"
                theme="twilight"
                value={pythonCode}
                onChange={(value: string) => setPythonCode(value)}
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
                  wrap: true,
                }}
              />
              <div className="text-xs text-gray-500">
                <ul className="list-disc list-inside space-y-1">
                  <li className="break-words">
                    Use{" "}
                    <code className="bg-gray-100 px-1 rounded">
                      params["df"]
                    </code>{" "}
                    to access the input dataframe from previous node
                  </li>
                  <li className="break-words">
                    Store your processed dataframe in{" "}
                    <code className="bg-gray-100 px-1 rounded">df</code>{" "}
                    variable and return it
                  </li>
                  <li className="break-words">
                    Available libraries: pandas, numpy, sklearn, scipy
                  </li>
                  <li className="break-words">
                    Code runs in a sandboxed environment with limited resources
                  </li>
                  <li className="break-words">
                    Maximum execution time: 30 seconds
                  </li>
                </ul>
              </div>
            </div>
          )}

          {/* Configure Mode */}
          {mode === "configure" && (
            <div className="space-y-4">
              <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg border border-blue-200">
                <p className="font-medium mb-1">Visual Configuration</p>
                <p className="text-xs">
                  Add preprocessing steps below. Steps are executed in order.
                  You can add multiple steps of the same type.
                </p>
              </div>

              {/* Steps List */}
              <div className="space-y-3">
                {config.steps.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 border border-dashed rounded-lg">
                    <p className="text-sm">No preprocessing steps added yet.</p>
                    <p className="text-xs mt-1">
                      Click the + button below to add your first step.
                    </p>
                  </div>
                ) : (
                  config.steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="border rounded-lg p-4 space-y-3 bg-white"
                    >
                      {/* Step Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 flex-1">
                          <GripVertical className="h-4 w-4 text-gray-400" />
                          <span className="text-xs font-medium text-gray-500">
                            Step {index + 1}
                          </span>
                          <span className="text-sm font-semibold">
                            {getStepTypeDisplayName(step.type)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs"
                            onClick={() => handleRunStep(step.id)}
                            disabled={runningStepId !== null || !fileUrl.trim()}
                            title="Run this step"
                          >
                            <Play className="h-3 w-3 mr-1" />
                            {runningStepId === step.id ? "Running..." : "Run"}
                          </Button>
                          {/* Hidden: Enable switch */}
                          <div className="hidden">
                            <div className="flex items-center gap-2">
                              <Label className="text-xs">Enabled</Label>
                              <Switch
                                checked={step.enabled}
                                onCheckedChange={(checked) =>
                                  handleToggleStep(step.id, checked)
                                }
                              />
                            </div>
                          </div>
                          {/* Hidden: Move up/down buttons */}
                          <div className="hidden">
                            <div className="flex items-center gap-1">
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-7 w-7 p-0"
                                onClick={() => handleMoveStep(step.id, "up")}
                                disabled={index === 0}
                              >
                                ↑
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-7 w-7 p-0"
                                onClick={() => handleMoveStep(step.id, "down")}
                                disabled={index === config.steps.length - 1}
                              >
                                ↓
                              </Button>
                            </div>
                          </div>
                          {/* Delete button - only show on last step */}
                          {index === config.steps.length - 1 && (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-7 w-7 p-0 text-red-600 hover:text-red-700"
                              onClick={() => handleRemoveStep(step.id)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Step Configuration */}
                      {step.enabled && (
                        <div className="pl-6 border-l-2 border-gray-200">
                          {renderStepConfig(step, index)}
                        </div>
                      )}

                      {/* Show analysis result for this step if available */}
                      {analysisResults[step.id] && (
                        <div className="pl-6 border-l-2 border-gray-200 mt-3">
                          <div className="text-xs font-medium text-gray-600 mb-2">
                            Result after this step:
                          </div>
                          <CSVAnalysisDisplay
                            analysisResult={analysisResults[step.id]}
                          />
                        </div>
                      )}
                    </div>
                  ))
                )}

                {/* Add Step Button - appears after last step */}
                <div className="flex items-center justify-center py-2">
                  <div className="relative inline-block">
                    <Select
                      value=""
                      onValueChange={(value) => {
                        if (value) {
                          handleAddStep(value as PreprocessingStepType);
                        }
                      }}
                    >
                      <SelectTrigger className="h-9 p-2 border rounded-md">
                        <div className="flex items-center gap-2 pr-2">
                          ADD
                          {/* <Plus className="h-4 w-4" /> */}
                        </div>
                      </SelectTrigger>
                      <SelectContent>
                        {stepTypes.map((type) => (
                          <SelectItem key={type} value={type}>
                            {getStepTypeDisplayName(type)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </NodeConfigPanel>

      {/* Prompt Dialog for Template Generation */}
      <Dialog open={isPromptDialogOpen} onOpenChange={setIsPromptDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Include a prompt?</DialogTitle>
            <DialogDescription>
              Would you like to include a prompt for template generation?
              (Optional)
            </DialogDescription>
          </DialogHeader>
          <textarea
            placeholder="Enter a prompt (optional)"
            value={templatePrompt}
            onChange={(e) => setTemplatePrompt(e.target.value)}
            className="mt-2 w-full rounded border border-gray-300 p-2 text-sm min-h-[80px] resize-y bg-background"
            rows={4}
          />
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => {
                setIsPromptDialogOpen(false);
                setTemplatePrompt("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                setIsPromptDialogOpen(false);
                handleGenerateTemplate(templatePrompt);
                setTemplatePrompt("");
              }}
              disabled={loading}
            >
              <Sparkles className="h-4 w-4 mr-2" />
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
