import React, { useState, useEffect } from "react";
import { TrainModelNodeData } from "../../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
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

type TrainModelDialogProps = BaseNodeDialogProps<
  TrainModelNodeData,
  TrainModelNodeData
>;

export const TrainModelDialog: React.FC<TrainModelDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate, nodeId } = props;
  const { getAvailableDataForNode } = useWorkflowExecution();

  const [name, setName] = useState(data.name || "Train Model");
  const [fileUrl, setFileUrl] = useState(data.fileUrl || "");
  const [modelType, setModelType] = useState(data.modelType || "xgboost");
  const [targetColumn, setTargetColumn] = useState(data.targetColumn || "");
  const [featureColumns, setFeatureColumns] = useState<string[]>(
    data.featureColumns || []
  );
  const [modelParameters, setModelParameters] = useState<Record<string, unknown>>(
    data.modelParameters || {}
  );
  const [validationSplit, setValidationSplit] = useState(
    data.validationSplit || 0.2
  );
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<CSVAnalysisResult | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Train Model");
      setFileUrl(data.fileUrl || "");
      setModelType(data.modelType || "xgboost");
      setTargetColumn(data.targetColumn || "");
      setFeatureColumns(data.featureColumns || []);
      setModelParameters(data.modelParameters || {});
      setValidationSplit(data.validationSplit || 0.2);
      setAnalysisResult(data.analysisResult || null);
    }
  }, [isOpen, data]);

  // Clean up featureColumns: remove targetColumn and invalid columns
  useEffect(() => {
    setFeatureColumns((prev) => {
      let cleaned = [...prev];
      
      // Remove targetColumn if it's in featureColumns
      if (targetColumn) {
        cleaned = cleaned.filter((col) => col !== targetColumn);
      }
      
      // If we have analysisResult, only keep columns that exist in the analysis
      if (analysisResult) {
        cleaned = cleaned.filter((col) =>
          analysisResult.column_names.includes(col)
        );
      }
      
      return cleaned;
    });
  }, [targetColumn, analysisResult]);

  const handleSave = () => {
    if (!targetColumn.trim()) {
      toast({
        title: "Validation Error",
        description: "Please specify the target column",
        variant: "destructive",
      });
      return;
    }

    if (featureColumns.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select at least one feature column",
        variant: "destructive",
      });
      return;
    }

    onUpdate({
      ...data,
      name,
      fileUrl,
      analysisResult: analysisResult || undefined,
      modelType,
      targetColumn,
      featureColumns,
      modelParameters,
      validationSplit,
    });
    onClose();
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
      setAnalysisResult(result);
      
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
    setFeatureColumns([...featureColumns, ""]);
  };

  const updateFeatureColumn = (index: number, value: string) => {
    const newColumns = [...featureColumns];
    newColumns[index] = value;
    setFeatureColumns(newColumns);
  };

  const removeFeatureColumn = (index: number) => {
    setFeatureColumns(featureColumns.filter((_, i) => i !== index));
  };

  const handleFeatureColumnToggle = (columnName: string) => {
    // Prevent adding targetColumn as a feature
    if (columnName === targetColumn) {
      return;
    }
    const isSelected = featureColumns.includes(columnName);
    if (isSelected) {
      setFeatureColumns(featureColumns.filter((col) => col !== columnName));
    } else {
      setFeatureColumns([...featureColumns, columnName]);
    }
  };

  const handleCommaSeparatedInputChange = (value: string) => {
    // Parse comma-separated values
    const parsedColumns = value
      .split(",")
      .map((col) => col.trim())
      .filter((col) => col.length > 0);
    setFeatureColumns(parsedColumns);
  };

  const handleModelTypeChange = (value: string) => {
    setModelType(value as TrainModelNodeData["modelType"]);
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
        data={{
          ...data,
          name,
          fileUrl,
          analysisResult: analysisResult || undefined,
          modelType,
          targetColumn,
          featureColumns,
          modelParameters,
          validationSplit,
        }}
      >
        <div className="space-y-4">
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
            {analysisResult && (
              <CSVAnalysisDisplay analysisResult={analysisResult} />
            )}
          </div>

          {/* Model Type */}
          <div className="space-y-2">
            <Label htmlFor="modelType">Model Type *</Label>
            <Select value={modelType} onValueChange={handleModelTypeChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select model type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="xgboost">XGBoost</SelectItem>
                <SelectItem value="random_forest">Random Forest</SelectItem>
                <SelectItem value="linear_regression">
                  Linear Regression
                </SelectItem>
                <SelectItem value="logistic_regression">
                  Logistic Regression
                </SelectItem>
                <SelectItem value="neural_network">
                  Neural Network
                </SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              Select the machine learning algorithm to use
            </p>
          </div>

          {/* Target Column */}
          <div className="space-y-2">
            <Label htmlFor="targetColumn">Target Column *</Label>
            {analysisResult ? (
              <Select value={targetColumn} onValueChange={setTargetColumn}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select target column" />
                </SelectTrigger>
                <SelectContent>
                  {analysisResult.column_names.map((columnName) => (
                    <SelectItem key={columnName} value={columnName}>
                      {columnName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <DraggableInput
                id="targetColumn"
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
                placeholder="Enter target column name"
                className="w-full"
              />
            )}
            <p className="text-xs text-gray-500">
              Name of the column containing the target variable to predict
            </p>
          </div>

          {/* Feature Columns */}
          <div className="space-y-2">
            <Label>Feature Columns *</Label>
            {analysisResult ? (
              /* Badge view when column names are available */
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
                  {analysisResult.column_names
                    .filter((columnName) => columnName !== targetColumn)
                    .map((columnName) => {
                      const isSelected = featureColumns.includes(columnName);
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
                <p className="text-xs text-gray-500">
                  {featureColumns.length} of{" "}
                  {analysisResult.column_names.filter(
                    (col) => col !== targetColumn
                  ).length}{" "}
                  columns selected. Click badges to toggle selection.
                </p>
              </div>
            ) : (
              /* Text input when no column names available */
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Columns</span>
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
                  <Input
                    value={featureColumns.join(", ")}
                    onChange={(e) =>
                      handleCommaSeparatedInputChange(e.target.value)
                    }
                    placeholder="Enter column names separated by commas (e.g., col1, col2, col3)"
                    className="w-full"
                  />
                  {featureColumns.length > 0 && (
                    <>
                      <div className="flex flex-wrap gap-2 p-2 border rounded bg-gray-50">
                        {featureColumns.map((column, index) => (
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
                      <p className="text-xs text-gray-500">
                        {featureColumns.length} column
                        {featureColumns.length !== 1 ? "s" : ""} added
                      </p>
                    </>
                  )}
                  {featureColumns.length === 0 && (
                    <p className="text-sm text-gray-500 italic">
                      No feature columns defined. Add columns to specify which
                      features to use for training.
                    </p>
                  )}
                </div>
              </div>
            )}
            <p className="text-xs text-gray-500">
              Select the columns to use as features for training the model
            </p>
          </div>

          {/* Validation Split */}
          <div className="space-y-2">
            <Label>
              Validation Split: {Math.round(validationSplit * 100)}%
            </Label>
            <Slider
              value={[validationSplit]}
              onValueChange={(value) => setValidationSplit(value[0])}
              max={0.5}
              min={0.1}
              step={0.05}
              className="w-full"
            />
            <p className="text-xs text-gray-500">
              Fraction of data to use for validation (10% - 50%)
            </p>
          </div>
        </div>
      </NodeConfigPanel>
    </>
  );
};
