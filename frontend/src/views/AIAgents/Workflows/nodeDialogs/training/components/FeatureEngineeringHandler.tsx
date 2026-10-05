import React, { useState, useEffect } from "react";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
import { Button } from "@/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  FeatureEngineeringConfig,
  FeatureEngineeringItem,
  FeatureEngineeringStrategy,
} from "../../../types/nodes";
import { CSVAnalysisResult } from "@/services/mlModels";
import {
  STRATEGY_HINTS,
  defaultsForStrategy,
  isColumnTransformStrategy,
  isRetiredFeatureStrategy,
  outputColumnsHint,
  strategyOptionsFor,
} from "../featureEngineeringStrategies";
import { Switch } from "@/components/switch";
import { Plus, X } from "lucide-react";

interface FeatureEngineeringHandlerProps {
  config: FeatureEngineeringConfig | undefined;
  onChange: (config: FeatureEngineeringConfig) => void;
  analysisResult: CSVAnalysisResult | null;
  // The target column: never offered as a feature input (it's what the model
  // predicts - using it to build a feature would leak the answer).
  targetColumn?: string;
}

export const FeatureEngineeringHandler: React.FC<
  FeatureEngineeringHandlerProps
> = ({ config, onChange, analysisResult, targetColumn }) => {
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

  const availableColumns = (analysisResult?.column_names || []).filter(
    (col) => col !== targetColumn
  );

  // Column transforms (log/quantile/power/PCA) take numeric columns only: the
  // analysis' numeric columns, plus the output of earlier features (features
  // run in order, so a later one can use an earlier one's column).
  const numericColumnsFor = (featureIndex: number): string[] => {
    const numeric = (analysisResult?.columns_info || [])
      .filter((col) => col.type === "numeric" && col.name !== targetColumn)
      .map((col) => col.name);
    const earlier = features
      .slice(0, featureIndex)
      .map((f) => f.newColumnName)
      .filter((name) => name && !numeric.includes(name));
    return [...(numeric.length ? numeric : availableColumns), ...earlier];
  };

  const toggleSourceColumn = (feature: FeatureEngineeringItem, col: string, checked: boolean) => {
    const current = feature.sourceColumns || [];
    handleFeatureChange(feature.id, {
      sourceColumns: checked ? [...current, col] : current.filter((c) => c !== col),
    });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Feature Engineering</Label>
        <p className="text-xs text-muted-foreground">
          Create new features from existing columns
        </p>
      </div>

      {(
        <div className="space-y-2">
          {!analysisResult ? (
            <p className="text-sm text-muted-foreground italic py-2">
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
                {features.map((feature, index) => (
                  <div
                    key={feature.id}
                    className="p-3 border rounded hover:bg-muted space-y-2"
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
                        <RichInput
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
                              // Start the new strategy from valid settings.
                              ...defaultsForStrategy(value as FeatureEngineeringStrategy),
                            })
                          }
                        >
                          <SelectTrigger className="h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {strategyOptionsFor(feature.strategy).map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                                disabled={isRetiredFeatureStrategy(option.value)}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {STRATEGY_HINTS[feature.strategy] && (
                        <p className="text-xs text-muted-foreground">
                          {STRATEGY_HINTS[feature.strategy]}
                        </p>
                      )}
                      {isRetiredFeatureStrategy(feature.strategy) && (
                        <p className="text-xs text-amber-700 dark:text-amber-400">
                          {feature.strategy === "normalize" ? "Normalize" : "Standardize"} is
                          retired: Train Model's Scaling Method already scales every numeric
                          feature (fit on the training split only), so this would scale the
                          same values twice. It still works for now - switch this feature to
                          another strategy or remove it, and use Scaling Method instead.
                        </p>
                      )}
                      {feature.strategy === "custom_expression" && (
                        <div>
                          <Label className="text-xs">Expression</Label>
                          <RichTextarea
                            size="hint"
                            value={feature.expression || ""}
                            onChange={(e) =>
                              handleFeatureChange(feature.id, {
                                expression: e.target.value,
                              })
                            }
                            placeholder="e.g., price * quantity"
                            className="text-xs font-mono"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Reference columns by name, e.g. price * quantity. Use
                            backticks for a name with spaces, e.g. `unit price` * quantity.
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
                            <RichInput
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
                          <p className="text-xs text-muted-foreground mb-1">
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
                            <RichInput
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
                            <p className="text-xs text-muted-foreground mb-1">
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
                      {isColumnTransformStrategy(feature.strategy) && (
                        <>
                          <div>
                            <Label className="text-xs">Columns</Label>
                            <p className="text-xs text-muted-foreground mb-1">
                              {feature.strategy === "pca"
                                ? "Select at least 2 numeric columns to combine"
                                : "Select numeric columns to transform"}
                            </p>
                            <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                              {numericColumnsFor(index).map((col) => (
                                <label key={col} className="flex items-center space-x-2 text-xs">
                                  <input
                                    type="checkbox"
                                    checked={feature.sourceColumns?.includes(col) || false}
                                    onChange={(e) => toggleSourceColumn(feature, col, e.target.checked)}
                                    className="rounded"
                                  />
                                  <span>{col}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                          {feature.strategy === "quantile_transform" && (
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <Label className="text-xs">Output distribution</Label>
                                <Select
                                  value={feature.quantileOutputDistribution || "uniform"}
                                  onValueChange={(value) =>
                                    handleFeatureChange(feature.id, {
                                      quantileOutputDistribution: value as "uniform" | "normal",
                                    })
                                  }
                                >
                                  <SelectTrigger className="h-8 text-xs">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="uniform">Uniform (0 to 1)</SelectItem>
                                    <SelectItem value="normal">Normal</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              <div>
                                <Label className="text-xs">Number of quantiles</Label>
                                <RichInput
                                  type="number"
                                  min="2"
                                  value={feature.nQuantiles?.toString() || "1000"}
                                  onChange={(e) =>
                                    handleFeatureChange(feature.id, {
                                      nQuantiles: parseInt(e.target.value, 10) || 1000,
                                    })
                                  }
                                  className="h-8 text-xs"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                  Capped at the number of training rows.
                                </p>
                              </div>
                            </div>
                          )}
                          {feature.strategy === "power_transform" && (
                            <div>
                              <Label className="text-xs">Method</Label>
                              <Select
                                value={feature.powerMethod || "yeo-johnson"}
                                onValueChange={(value) =>
                                  handleFeatureChange(feature.id, {
                                    powerMethod: value as "yeo-johnson" | "box-cox",
                                  })
                                }
                              >
                                <SelectTrigger className="h-8 text-xs">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="yeo-johnson">Yeo-Johnson (any values)</SelectItem>
                                  <SelectItem value="box-cox">Box-Cox (values above 0 only)</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          )}
                          {feature.strategy === "pca" && (
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <Label className="text-xs">Number of components</Label>
                                <RichInput
                                  type="number"
                                  min="0"
                                  step="any"
                                  value={feature.pcaComponents?.toString() ?? "2"}
                                  onChange={(e) => {
                                    const value = parseFloat(e.target.value);
                                    handleFeatureChange(feature.id, {
                                      pcaComponents: isNaN(value) ? 2 : value,
                                    });
                                  }}
                                  className="h-8 text-xs"
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                  A whole number (e.g. 2), or a share of variance to keep (e.g. 0.95).
                                </p>
                              </div>
                              <div className="flex items-center gap-2 pt-5">
                                <Switch
                                  checked={feature.pcaStandardize ?? true}
                                  onCheckedChange={(checked) =>
                                    handleFeatureChange(feature.id, { pcaStandardize: checked })
                                  }
                                />
                                <Label className="text-xs">Standardize columns first</Label>
                              </div>
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={feature.replaceSourceColumns ?? feature.strategy === "pca"}
                              onCheckedChange={(checked) =>
                                handleFeatureChange(feature.id, { replaceSourceColumns: checked })
                              }
                            />
                            <Label className="text-xs">
                              Replace source columns (train on the transformed columns only)
                            </Label>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {outputColumnsHint(feature)}. Fit on the training split only.
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {features.length === 0 && (
                <p className="text-sm text-muted-foreground italic py-2 text-center">
                  No features added. Click "Add Feature" to create a new feature.
                </p>
              )}
              <p className="text-xs text-muted-foreground">
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

