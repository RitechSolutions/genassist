import React, { useState, useEffect } from "react";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  FeatureEngineeringConfig,
  FeatureEngineeringItem,
  FeatureEngineeringStrategy,
} from "../preprocessingConfig";
import { CSVAnalysisResult } from "@/services/mlModels";
import { Plus, X } from "lucide-react";

interface FeatureEngineeringHandlerProps {
  config: FeatureEngineeringConfig | undefined;
  onChange: (config: FeatureEngineeringConfig) => void;
  analysisResult: CSVAnalysisResult | null;
}

export const FeatureEngineeringHandler: React.FC<
  FeatureEngineeringHandlerProps
> = ({ config, onChange, analysisResult }) => {
  const [features, setFeatures] = useState<FeatureEngineeringItem[]>(
    config?.features || []
  );


  useEffect(() => {
    if (config) {
      setFeatures(config.features || []);
    } else {
      setFeatures([]);
    }
  }, [config]);


  const handleAddFeature = () => {
    const newFeature: FeatureEngineeringItem = {
      id: `feature_${Date.now()}`,
      newColumnName: "",
      strategy: "custom_expression",
      expression: "",
    };
    const newFeatures = [...features, newFeature];
    setFeatures(newFeatures);
    onChange({
      enabled: true,
      features: newFeatures,
    });
  };

  const handleRemoveFeature = (id: string) => {
    const newFeatures = features.filter((f) => f.id !== id);
    setFeatures(newFeatures);
    onChange({
      enabled: true,
      features: newFeatures,
    });
  };

  const handleFeatureChange = (
    id: string,
    updates: Partial<FeatureEngineeringItem>
  ) => {
    const newFeatures = features.map((f) =>
      f.id === id ? { ...f, ...updates } : f
    );
    setFeatures(newFeatures);
    onChange({
      enabled: true,
      features: newFeatures,
    });
  };

  const availableColumns = analysisResult?.column_names || [];

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Feature Engineering</Label>
        <p className="text-xs text-gray-500">
          Create new features from existing columns
        </p>
      </div>

      {(
        <div className="space-y-2">
          {!analysisResult ? (
            <p className="text-sm text-gray-500 italic py-2">
              Please analyze the CSV file first to see available columns.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm">Features</Label>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleAddFeature}
                  className="h-7 text-xs"
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add Feature
                </Button>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {features.map((feature) => (
                  <div
                    key={feature.id}
                    className="p-3 border rounded hover:bg-gray-50 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium">
                        Feature #{features.indexOf(feature) + 1}
                      </Label>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveFeature(feature.id)}
                        className="h-6 w-6 p-0"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <Label className="text-xs">New Column Name</Label>
                        <Input
                          value={feature.newColumnName}
                          onChange={(e) =>
                            handleFeatureChange(feature.id, {
                              newColumnName: e.target.value,
                            })
                          }
                          placeholder="e.g., feature_sum"
                          className="h-8 text-xs"
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Strategy</Label>
                        <Select
                          value={feature.strategy}
                          onValueChange={(value) =>
                            handleFeatureChange(feature.id, {
                              strategy: value as FeatureEngineeringStrategy,
                            })
                          }
                        >
                          <SelectTrigger className="h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="custom_expression">
                              Custom Expression
                            </SelectItem>
                            <SelectItem value="bin_numeric">Bin Numeric</SelectItem>
                            <SelectItem value="normalize">Normalize</SelectItem>
                            <SelectItem value="standardize">Standardize</SelectItem>
                            <SelectItem value="polynomial">Polynomial</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {feature.strategy === "custom_expression" && (
                        <div>
                          <Label className="text-xs">Expression</Label>
                          <Input
                            value={feature.expression || ""}
                            onChange={(e) =>
                              handleFeatureChange(feature.id, {
                                expression: e.target.value,
                              })
                            }
                            placeholder='e.g., df["col1"] + df["col2"]'
                            className="h-8 text-xs font-mono"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Use df["column_name"] to reference columns
                          </p>
                        </div>
                      )}
                      {feature.strategy === "bin_numeric" && (
                        <>
                          <div>
                            <Label className="text-xs">Column to Bin</Label>
                            <Select
                              value={feature.binColumn || ""}
                              onValueChange={(value) =>
                                handleFeatureChange(feature.id, {
                                  binColumn: value,
                                })
                              }
                            >
                              <SelectTrigger className="h-8 text-xs">
                                <SelectValue placeholder="Select column" />
                              </SelectTrigger>
                              <SelectContent>
                                {availableColumns.map((col) => (
                                  <SelectItem key={col} value={col}>
                                    {col}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="text-xs">Number of Bins</Label>
                            <Input
                              type="number"
                              min="2"
                              max="100"
                              value={feature.numBins?.toString() || "5"}
                              onChange={(e) =>
                                handleFeatureChange(feature.id, {
                                  numBins: parseInt(e.target.value, 10) || 5,
                                })
                              }
                              className="h-8 text-xs"
                            />
                          </div>
                        </>
                      )}
                      {(feature.strategy === "normalize" ||
                        feature.strategy === "standardize") && (
                        <div>
                          <Label className="text-xs">Columns</Label>
                          <p className="text-xs text-gray-500 mb-1">
                            Select columns to {feature.strategy}
                          </p>
                          <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                            {availableColumns.map((col) => (
                              <label
                                key={col}
                                className="flex items-center space-x-2 text-xs"
                              >
                                <input
                                  type="checkbox"
                                  checked={
                                    feature.sourceColumns?.includes(col) || false
                                  }
                                  onChange={(e) => {
                                    const current = feature.sourceColumns || [];
                                    const updated = e.target.checked
                                      ? [...current, col]
                                      : current.filter((c) => c !== col);
                                    handleFeatureChange(feature.id, {
                                      sourceColumns: updated,
                                    });
                                  }}
                                  className="rounded"
                                />
                                <span>{col}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                      {feature.strategy === "polynomial" && (
                        <>
                          <div>
                            <Label className="text-xs">Degree</Label>
                            <Input
                              type="number"
                              min="2"
                              max="5"
                              value={feature.polynomialDegree?.toString() || "2"}
                              onChange={(e) =>
                                handleFeatureChange(feature.id, {
                                  polynomialDegree:
                                    parseInt(e.target.value, 10) || 2,
                                })
                              }
                              className="h-8 text-xs"
                            />
                          </div>
                          <div>
                            <Label className="text-xs">Columns</Label>
                            <p className="text-xs text-gray-500 mb-1">
                              Select columns for polynomial features
                            </p>
                            <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                              {availableColumns.map((col) => (
                                <label
                                  key={col}
                                  className="flex items-center space-x-2 text-xs"
                                >
                                  <input
                                    type="checkbox"
                                    checked={
                                      feature.polynomialColumns?.includes(
                                        col
                                      ) || false
                                    }
                                    onChange={(e) => {
                                      const current =
                                        feature.polynomialColumns || [];
                                      const updated = e.target.checked
                                        ? [...current, col]
                                        : current.filter((c) => c !== col);
                                      handleFeatureChange(feature.id, {
                                        polynomialColumns: updated,
                                      });
                                    }}
                                    className="rounded"
                                  />
                                  <span>{col}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {features.length === 0 && (
                <p className="text-sm text-gray-500 italic py-2 text-center">
                  No features added. Click "Add Feature" to create a new feature.
                </p>
              )}
              <p className="text-xs text-gray-500">
                {features.length} feature{features.length !== 1 ? "s" : ""}{" "}
                configured. Features are created in the order listed.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

