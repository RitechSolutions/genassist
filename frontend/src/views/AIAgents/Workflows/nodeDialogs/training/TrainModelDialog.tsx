import React, { useState, useEffect } from "react";
import { TrainModelNodeData, HyperparameterOptimizationMethod, OptimizationConfig } from "../../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Slider } from "@/components/slider";
import { useToast } from "@/components/use-toast";
import { Save, Plus, X, Search } from "lucide-react";
import { Badge } from "@/components/badge";
import { NodeConfigPanel } from "../../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "../base";
import { DraggableInput } from "../../components/custom/DraggableInput";
import { analyzeCSV, CSVAnalysisResult } from "@/services/mlModels";
import { CSVAnalysisDisplay } from "./components/CSVAnalysisDisplay";
import { useWorkflowExecution } from "../../context/WorkflowExecutionContext";
import { extractDynamicVariables, getValueFromPath } from "../../utils/helpers";
import { useNodeDialogState } from "../useNodeDialogState";
import { ML_MODEL_TYPES } from "@/constants/mlModelTypes";

const HYPERPARAMETER_OPTIMIZATION_METHODS: {
  value: HyperparameterOptimizationMethod;
  label: string;
  description: string;
}[] = [
  { value: "none", label: "No Optimization", description: "Train once with the fixed parameters above." },
  {
    value: "random_search",
    label: "Random Search",
    description: "Randomly samples parameter combinations from a curated search space.",
  },
  {
    value: "grid_search",
    label: "Grid Search",
    description: "Exhaustively tries every combination on a discretized grid. Slower, thorough.",
  },
  {
    value: "bayesian_optimization",
    label: "Bayesian Optimization",
    description: "Uses Optuna to sequentially focus the search on promising regions.",
  },
];

type TrainModelDialogProps = BaseNodeDialogProps<
  TrainModelNodeData,
  TrainModelNodeData
>;

export const TrainModelDialog: React.FC<TrainModelDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate, nodeId } = props;
  const { getAvailableDataForNode } = useWorkflowExecution();

  const { values, setField, setValues, merged } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "Train Model",
      fileUrl: data.fileUrl || "",
      modelType: data.modelType || "xgboost",
      targetColumn: data.targetColumn || "",
      featureColumns: data.featureColumns || [],
      modelParameters: data.modelParameters || {},
      validationSplit: data.validationSplit || 0.2,
      analysisResult: data.analysisResult || null,
      splitMethod: data.splitMethod || "random",
      dateColumn: data.dateColumn || "",
      hyperparameterOptimization: data.hyperparameterOptimization || "none",
      optimizationConfig: data.optimizationConfig || {},
    }),
    (v) => ({
      name: v.name,
      fileUrl: v.fileUrl,
      analysisResult: v.analysisResult || undefined,
      modelType: v.modelType,
      targetColumn: v.targetColumn,
      featureColumns: v.featureColumns,
      modelParameters: v.modelParameters,
      validationSplit: v.validationSplit,
      splitMethod: v.splitMethod,
      dateColumn: v.splitMethod === "time_based" ? v.dateColumn : undefined,
      hyperparameterOptimization: v.hyperparameterOptimization,
      optimizationConfig:
        v.hyperparameterOptimization === "none" ? undefined : v.optimizationConfig,
    })
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const { toast } = useToast();

  // Clean up featureColumns: remove targetColumn and invalid columns
  useEffect(() => {
    setValues((v) => {
      let cleaned = [...v.featureColumns];

      // Remove targetColumn if it's in featureColumns
      if (v.targetColumn) {
        cleaned = cleaned.filter((col) => col !== v.targetColumn);
      }

      // If we have analysisResult, only keep columns that exist in the analysis
      if (v.analysisResult) {
        const analysis = v.analysisResult;
        cleaned = cleaned.filter((col) => analysis.column_names.includes(col));
      }

      return { ...v, featureColumns: cleaned };
    });
  }, [values.targetColumn, values.analysisResult, setValues]);

  const handleSave = () => {
    if (!values.targetColumn.trim()) {
      toast({
        title: "Validation Error",
        description: "Please specify the target column",
        variant: "destructive",
      });
      return;
    }

    if (values.featureColumns.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select at least one feature column",
        variant: "destructive",
      });
      return;
    }

    if (values.splitMethod === "time_based" && !values.dateColumn.trim()) {
      toast({
        title: "Validation Error",
        description: "Please specify a date column for a time-based split",
        variant: "destructive",
      });
      return;
    }

    onUpdate(merged);
    onClose();
  };

  const handleAnalyzeCSV = async () => {
    if (!values.fileUrl.trim()) {
      toast({
        title: "Validation Error",
        description: "Please provide a file URL to analyze",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsAnalyzing(true);

      let resolvedFileUrl = values.fileUrl;
      const variables = extractDynamicVariables(values.fileUrl);

      if (variables.size > 0 && nodeId) {
        const availableData = getAvailableDataForNode(nodeId);

        if (availableData) {
          variables.forEach((variable) => {
            const value = getValueFromPath(availableData, variable);
            if (value !== undefined) {
              const stringValue = typeof value === "string"
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
      setField("analysisResult", result);

      toast({
        title: "Analysis Complete",
        description: `Found ${result.column_count} columns and ${result.row_count} rows`,
      });
    } catch (err) {
      toast({
        title: "Analysis Failed",
        description: err instanceof Error ? err.message : "Failed to analyze CSV file",
        variant: "destructive",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };


  const addFeatureColumn = () => {
    setField("featureColumns", [...values.featureColumns, ""]);
  };

  const updateFeatureColumn = (index: number, value: string) => {
    const newColumns = [...values.featureColumns];
    newColumns[index] = value;
    setField("featureColumns", newColumns);
  };

  const removeFeatureColumn = (index: number) => {
    setField(
      "featureColumns",
      values.featureColumns.filter((_, i) => i !== index)
    );
  };

  const handleFeatureColumnToggle = (columnName: string) => {
    // Prevent adding targetColumn as a feature
    if (columnName === values.targetColumn) {
      return;
    }
    const isSelected = values.featureColumns.includes(columnName);
    if (isSelected) {
      setField(
        "featureColumns",
        values.featureColumns.filter((col) => col !== columnName)
      );
    } else {
      setField("featureColumns", [...values.featureColumns, columnName]);
    }
  };

  const handleCommaSeparatedInputChange = (value: string) => {
    // Parse comma-separated values
    const parsedColumns = value
      .split(",")
      .map((col) => col.trim())
      .filter((col) => col.length > 0);
    setField("featureColumns", parsedColumns);
  };

  const handleModelTypeChange = (value: string) => {
    setField("modelType", value as TrainModelNodeData["modelType"]);
  };

  const handleSplitMethodChange = (value: string) => {
    setField("splitMethod", value as TrainModelNodeData["splitMethod"]);
  };

  const handleHyperparameterOptimizationChange = (value: string) => {
    setField("hyperparameterOptimization", value as HyperparameterOptimizationMethod);
  };

  const updateOptimizationConfig = (patch: Partial<OptimizationConfig>) => {
    setField("optimizationConfig", { ...values.optimizationConfig, ...patch });
  };

  return (
    <>
      <NodeConfigPanel
        isOpen={isOpen}
        onClose={onClose}
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
        <div className="space-y-4">
          {/* Node Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Node Name</Label>
            <RichInput
              id="name"
              value={values.name}
              onChange={(e) => setField("name", e.target.value)}
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
                  value={values.fileUrl}
                  onChange={(e) => setField("fileUrl", e.target.value)}
                  placeholder="Enter file URL or drag variable"
                  className="w-full"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={handleAnalyzeCSV}
                disabled={isAnalyzing || !values.fileUrl.trim()}
                className="mb-0"
              >
                <Search className="h-4 w-4 mr-2" />
                {isAnalyzing ? "Analyzing..." : "Analyze"}
              </Button>
            </div>
            {values.analysisResult && (
              <CSVAnalysisDisplay analysisResult={values.analysisResult} />
            )}
          </div>

          {/* Model Type */}
          <div className="space-y-2">
            <Label htmlFor="modelType">Model Type *</Label>
            <Select value={values.modelType} onValueChange={handleModelTypeChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select model type" />
              </SelectTrigger>
              <SelectContent>
                {ML_MODEL_TYPES.map(({ value, label }) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Select the machine learning algorithm to use
            </p>
          </div>

          {/* Hyperparameter Optimization */}
          <div className="space-y-2">
            <Label htmlFor="hyperparameterOptimization">Hyperparameter Optimization</Label>
            <Select
              value={values.hyperparameterOptimization}
              onValueChange={handleHyperparameterOptimizationChange}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select optimization method" />
              </SelectTrigger>
              <SelectContent>
                {HYPERPARAMETER_OPTIMIZATION_METHODS.map(({ value, label }) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {
                HYPERPARAMETER_OPTIMIZATION_METHODS.find(
                  (m) => m.value === values.hyperparameterOptimization
                )?.description
              }{" "}
              Any parameter set in Model Parameters is fixed and excluded from the search.
            </p>

            {values.hyperparameterOptimization !== "none" && (
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div className="space-y-1">
                  <Label htmlFor="cvFolds" className="text-xs">
                    CV Folds
                  </Label>
                  <RichInput
                    id="cvFolds"
                    type="number"
                    min="2"
                    max="10"
                    value={values.optimizationConfig.cvFolds ?? 3}
                    onChange={(e) =>
                      updateOptimizationConfig({ cvFolds: Number(e.target.value) })
                    }
                    className="w-full"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="scoring" className="text-xs">
                    Scoring Metric
                  </Label>
                  <RichInput
                    id="scoring"
                    value={values.optimizationConfig.scoring ?? ""}
                    onChange={(e) => updateOptimizationConfig({ scoring: e.target.value })}
                    placeholder="auto (accuracy / r2)"
                    className="w-full"
                  />
                </div>

                {values.hyperparameterOptimization === "random_search" && (
                  <div className="space-y-1">
                    <Label htmlFor="nIter" className="text-xs">
                      Iterations
                    </Label>
                    <RichInput
                      id="nIter"
                      type="number"
                      min="1"
                      max="200"
                      value={values.optimizationConfig.nIter ?? 20}
                      onChange={(e) =>
                        updateOptimizationConfig({ nIter: Number(e.target.value) })
                      }
                      className="w-full"
                    />
                  </div>
                )}

                {values.hyperparameterOptimization === "grid_search" && (
                  <div className="space-y-1">
                    <Label htmlFor="gridPoints" className="text-xs">
                      Grid Points / Parameter
                    </Label>
                    <RichInput
                      id="gridPoints"
                      type="number"
                      min="2"
                      max="6"
                      value={values.optimizationConfig.gridPoints ?? 3}
                      onChange={(e) =>
                        updateOptimizationConfig({ gridPoints: Number(e.target.value) })
                      }
                      className="w-full"
                    />
                  </div>
                )}

                {values.hyperparameterOptimization === "bayesian_optimization" && (
                  <>
                    <div className="space-y-1">
                      <Label htmlFor="nTrials" className="text-xs">
                        Trials
                      </Label>
                      <RichInput
                        id="nTrials"
                        type="number"
                        min="1"
                        max="200"
                        value={values.optimizationConfig.nTrials ?? 30}
                        onChange={(e) =>
                          updateOptimizationConfig({ nTrials: Number(e.target.value) })
                        }
                        className="w-full"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="timeoutSeconds" className="text-xs">
                        Timeout (seconds)
                      </Label>
                      <RichInput
                        id="timeoutSeconds"
                        type="number"
                        min="1"
                        value={values.optimizationConfig.timeoutSeconds ?? ""}
                        placeholder="none"
                        onChange={(e) =>
                          updateOptimizationConfig({
                            timeoutSeconds: e.target.value ? Number(e.target.value) : undefined,
                          })
                        }
                        className="w-full"
                      />
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Target Column */}
          <div className="space-y-2">
            <Label htmlFor="targetColumn">Target Column *</Label>
            {values.analysisResult ? (
              <Select
                value={values.targetColumn}
                onValueChange={(v) => setField("targetColumn", v)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select target column" />
                </SelectTrigger>
                <SelectContent>
                  {values.analysisResult.column_names.map((columnName) => (
                    <SelectItem key={columnName} value={columnName}>
                      {columnName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <DraggableInput
                id="targetColumn"
                value={values.targetColumn}
                onChange={(e) => setField("targetColumn", e.target.value)}
                placeholder="Enter target column name"
                className="w-full"
              />
            )}
            <p className="text-xs text-muted-foreground">
              Name of the column containing the target variable to predict
            </p>
          </div>

          {/* Feature Columns */}
          <div className="space-y-2">
            <Label>Feature Columns *</Label>
            {values.analysisResult ? (
              /* Badge view when column names are available */
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
                  {values.analysisResult.column_names
                    .filter((columnName) => columnName !== values.targetColumn)
                    .map((columnName) => {
                      const isSelected =
                        values.featureColumns.includes(columnName);
                      return (
                        <Badge
                          key={columnName}
                          variant={isSelected ? "default" : "outline"}
                          className="cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={() => handleFeatureColumnToggle(columnName)}
                        >
                          {columnName}
                        </Badge>
                      );
                    })}
                </div>
                <p className="text-xs text-muted-foreground">
                  {values.featureColumns.length} of{" "}
                  {values.analysisResult.column_names.filter(
                    (col) => col !== values.targetColumn
                  ).length}{" "}
                  columns selected. Click badges to toggle selection.
                </p>
              </div>
            ) : (
              /* Text input when no column names available */
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Columns</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addFeatureColumn}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add Feature
                  </Button>
                </div>
                <div className="space-y-2">
                  <RichInput
                    value={values.featureColumns.join(", ")}
                    onChange={(e) =>
                      handleCommaSeparatedInputChange(e.target.value)
                    }
                    placeholder="Enter column names separated by commas (e.g., col1, col2, col3)"
                    className="w-full"
                  />
                  {values.featureColumns.length > 0 && (
                    <>
                      <div className="flex flex-wrap gap-2 p-2 border rounded bg-muted">
                        {values.featureColumns.map((column, index) => (
                          <div key={index} className="flex items-center gap-1">
                            <Badge variant="default">{column}</Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 w-5 p-0"
                              onClick={() => removeFeatureColumn(index)}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {values.featureColumns.length} column
                        {values.featureColumns.length !== 1 ? "s" : ""} added
                      </p>
                    </>
                  )}
                  {values.featureColumns.length === 0 && (
                    <p className="text-sm text-muted-foreground italic">
                      No feature columns defined. Add columns to specify which
                      features to use for training.
                    </p>
                  )}
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Select the columns to use as features for training the model
            </p>
          </div>

          {/* Split Method */}
          <div className="space-y-2">
            <Label htmlFor="splitMethod">Split Method</Label>
            <Select value={values.splitMethod} onValueChange={handleSplitMethodChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select split method" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="random">Random</SelectItem>
                <SelectItem value="time_based">Time-based</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Random shuffles rows before splitting. Time-based sorts by a date
              column and reserves the most recent rows for validation — use this
              for time-series data.
            </p>
          </div>

          {/* Date Column (time-based split only) */}
          {values.splitMethod === "time_based" && (
            <div className="space-y-2">
              <Label htmlFor="dateColumn">Date Column *</Label>
              {values.analysisResult ? (
                <Select
                  value={values.dateColumn}
                  onValueChange={(v) => setField("dateColumn", v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select date column" />
                  </SelectTrigger>
                  <SelectContent>
                    {values.analysisResult.column_names.map((columnName) => (
                      <SelectItem key={columnName} value={columnName}>
                        {columnName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <DraggableInput
                  id="dateColumn"
                  value={values.dateColumn}
                  onChange={(e) => setField("dateColumn", e.target.value)}
                  placeholder="Enter date/timestamp column name"
                  className="w-full"
                />
              )}
              <p className="text-xs text-muted-foreground">
                Column used to sort rows chronologically before splitting
              </p>
            </div>
          )}

          {/* Validation Split */}
          <div className="space-y-2">
            <Label>
              Validation Split: {Math.round(values.validationSplit * 100)}%
            </Label>
            <Slider
              value={[values.validationSplit]}
              onValueChange={(value) => setField("validationSplit", value[0])}
              max={0.5}
              min={0.1}
              step={0.05}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              {values.splitMethod === "time_based"
                ? "Fraction of the most recent rows to reserve for validation (10% - 50%)"
                : "Fraction of data to use for validation (10% - 50%)"}
            </p>
          </div>
        </div>
      </NodeConfigPanel>
    </>
  );
};
