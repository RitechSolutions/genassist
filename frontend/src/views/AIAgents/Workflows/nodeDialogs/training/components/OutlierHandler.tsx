import React, { useState, useEffect } from "react";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Input } from "@/components/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  OutlierHandlingConfig,
  OutlierHandlingItem,
  OutlierStrategy,
  OutlierMethod,
} from "../preprocessingConfig";
import { CSVAnalysisResult } from "@/services/mlModels";

interface OutlierHandlerProps {
  config: OutlierHandlingConfig | undefined;
  onChange: (config: OutlierHandlingConfig) => void;
  analysisResult: CSVAnalysisResult | null;
}

export const OutlierHandler: React.FC<OutlierHandlerProps> = ({
  config,
  onChange,
  analysisResult,
}) => {
  const [columns, setColumns] = useState<OutlierHandlingItem[]>(
    config?.columns || []
  );

  // Get numeric columns from analysis result
  const getNumericColumns = (): OutlierHandlingItem[] => {
    if (!analysisResult) return [];

    const numericColumns = analysisResult.columns_info
      .filter((col) => {
        // Only include columns that are numeric type
        return col.type === "numeric";
      })
      .map((col) => ({
        columnName: col.name,
        strategy: "no_action" as OutlierStrategy, // Default strategy
        method: "iqr" as OutlierMethod, // Default method
        iqrMultiplier: 1.5, // Default IQR multiplier
        zScoreThreshold: 3, // Default Z-score threshold
      }));

    return numericColumns;
  };

  useEffect(() => {
    if (config) {
      // Use config.columns as source of truth
      setColumns(config.columns);
    }
  }, [config]);

  // Initialize columns from analysis result when no config exists
  useEffect(() => {
    if (analysisResult) {
      const numericColumns = getNumericColumns();
      const configColumns = config?.columns || [];

      if (configColumns.length === 0 && numericColumns.length > 0) {
        // Initialize from analysis result only if no config exists
        setColumns(numericColumns);
        onChange({
          enabled: config?.enabled ?? true,
          columns: numericColumns,
        });
      } else if (configColumns.length > 0) {
        // Sync with analysis result - add new numeric columns that aren't in config
        // Use config.columns as source of truth to preserve user's settings
        const existingColumnsMap = new Map(
          configColumns.map((col) => [col.columnName, col])
        );

        // Build columns from config (source of truth)
        const syncedColumns: OutlierHandlingItem[] = [...configColumns];

        // Add any new numeric columns from analysis that aren't in config
        numericColumns.forEach((col) => {
          if (!existingColumnsMap.has(col.columnName)) {
            syncedColumns.push({
              ...col,
              method: "iqr",
              iqrMultiplier: 1.5,
              zScoreThreshold: 3,
            });
          }
        });

        // Only update local state if new columns were added, don't call onChange
        // to avoid overwriting user's changes
        if (syncedColumns.length !== columns.length) {
          setColumns(syncedColumns);
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisResult]);

  const handleStrategyChange = (
    columnName: string,
    strategy: OutlierStrategy
  ) => {
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            strategy,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: config?.enabled ?? true,
      columns: newColumns,
    });
  };

  const handleMethodChange = (
    columnName: string,
    method: OutlierMethod
  ) => {
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            method,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: config?.enabled ?? true,
      columns: newColumns,
    });
  };

  const handleIqrMultiplierChange = (
    columnName: string,
    value: string
  ) => {
    const multiplier = parseFloat(value) || 1.5;
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            iqrMultiplier: multiplier,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: config?.enabled ?? true,
      columns: newColumns,
    });
  };

  const handleZScoreThresholdChange = (
    columnName: string,
    value: string
  ) => {
    const threshold = parseFloat(value) || 3;
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            zScoreThreshold: threshold,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: config?.enabled ?? true,
      columns: newColumns,
    });
  };

  const numericColumns = getNumericColumns();

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Handle Outliers</Label>
        <p className="text-xs text-gray-500">
          Configure how to handle outliers in numeric columns
        </p>
      </div>

      {(
        <div className="space-y-2">
          {!analysisResult ? (
            <p className="text-sm text-gray-500 italic py-2">
              Please analyze the CSV file first to see numeric columns.
            </p>
          ) : numericColumns.length === 0 ? (
            <p className="text-sm text-gray-500 italic py-2">
              No numeric columns found or all numeric columns are filtered out.
            </p>
          ) : (
            <div className="space-y-3">
              <Label className="text-sm">Numeric Columns</Label>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {columns.map((column) => {
                  const columnInfo = analysisResult.columns_info.find(
                    (col) => col.name === column.columnName
                  );
                  return (
                    <div
                      key={column.columnName}
                      className="flex items-center justify-between p-3 border rounded hover:bg-gray-50 gap-4"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Label className="font-medium text-sm">
                            {column.columnName}
                          </Label>
                          {columnInfo && (
                            <span className="text-xs text-gray-500">
                              (min: {columnInfo.min ?? "N/A"}, max:{" "}
                              {columnInfo.max ?? "N/A"})
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Select
                          value={column.method || "iqr"}
                          onValueChange={(value) =>
                            handleMethodChange(
                              column.columnName,
                              value as OutlierMethod
                            )
                          }
                        >
                          <SelectTrigger className="w-[100px]">
                            <SelectValue placeholder="Method" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="iqr">IQR</SelectItem>
                            <SelectItem value="zscore">Z-Score</SelectItem>
                          </SelectContent>
                        </Select>
                        <Select
                          value={column.strategy}
                          onValueChange={(value) =>
                            handleStrategyChange(
                              column.columnName,
                              value as OutlierStrategy
                            )
                          }
                        >
                          <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="Strategy" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="no_action">No Action</SelectItem>
                            <SelectItem value="remove_outliers">
                              Remove
                            </SelectItem>
                            <SelectItem value="cap_outliers">
                              Cap
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        {column.method === "iqr" && column.strategy !== "no_action" && (
                          <Input
                            type="number"
                            step="0.1"
                            min="0.5"
                            max="5"
                            placeholder="1.5"
                            value={column.iqrMultiplier?.toString() || "1.5"}
                            onChange={(e) =>
                              handleIqrMultiplierChange(
                                column.columnName,
                                e.target.value
                              )
                            }
                            className="w-[80px]"
                            title="IQR Multiplier (default: 1.5)"
                          />
                        )}
                        {column.method === "zscore" && column.strategy !== "no_action" && (
                          <Input
                            type="number"
                            step="0.1"
                            min="1"
                            max="5"
                            placeholder="3"
                            value={column.zScoreThreshold?.toString() || "3"}
                            onChange={(e) =>
                              handleZScoreThresholdChange(
                                column.columnName,
                                e.target.value
                              )
                            }
                            className="w-[80px]"
                            title="Z-Score Threshold (default: 3)"
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-gray-500">
                {columns.length} numeric column{columns.length !== 1 ? "s" : ""}{" "}
                available. IQR method uses Q1/Q3 quartiles. Z-Score method uses
                standard deviations from mean.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

