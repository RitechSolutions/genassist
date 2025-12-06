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
  MissingValueHandlingConfig,
  MissingValueHandlingItem,
  MissingValueStrategy,
} from "../preprocessingConfig";
import { CSVAnalysisResult } from "@/services/mlModels";

interface MissingValueHandlerProps {
  config: MissingValueHandlingConfig | undefined;
  onChange: (config: MissingValueHandlingConfig) => void;
  analysisResult: CSVAnalysisResult | null;
}

export const MissingValueHandler: React.FC<MissingValueHandlerProps> = ({
  config,
  onChange,
  analysisResult,
}) => {
  const [columns, setColumns] = useState<MissingValueHandlingItem[]>(
    config?.columns || []
  );

  // Get columns with missing values from analysis result
  const getColumnsWithMissingValues = (): MissingValueHandlingItem[] => {
    if (!analysisResult) return [];

    const columnsWithMissing = analysisResult.columns_info
      .filter((col) => {
        // Only include columns that have missing values
        return col.missing_count > 0;
      })
      .map((col) => {
        const totalRows = analysisResult.row_count;
        const missingPercentage = totalRows > 0 
          ? (col.missing_count / totalRows) * 100 
          : 0;

        return {
          columnName: col.name,
          missingCount: col.missing_count,
          missingPercentage: missingPercentage,
          strategy: "no_action" as MissingValueStrategy, // Default strategy
        };
      })
      .sort((a, b) => b.missingPercentage - a.missingPercentage); // Sort by percentage descending

    return columnsWithMissing;
  };

  useEffect(() => {
    if (config) {
      setColumns(config.columns);
    }
  }, [config]);

  // Initialize columns from analysis result when no config exists
  useEffect(() => {
    if (analysisResult) {
      const columnsWithMissing = getColumnsWithMissingValues();
      
      if (columns.length === 0 && columnsWithMissing.length > 0) {
        // Initialize from analysis result
        setColumns(columnsWithMissing);
        onChange({
          enabled: true,
          columns: columnsWithMissing,
        });
      } else if (columns.length > 0) {
        // Sync with analysis result - update missing counts and percentages
        const existingColumnsMap = new Map(
          columns.map((col) => [col.columnName, col])
        );

        // Merge: keep existing columns (even if they no longer have missing values from analysis)
        // but update missing counts/percentages for columns that exist in analysis
        const analysisColumnsMap = new Map(
          columnsWithMissing.map((col) => [col.columnName, col])
        );

        // Start with existing columns to preserve user's configuration
        const syncedColumns: MissingValueHandlingItem[] = columns.map((col) => {
          const analysisCol = analysisColumnsMap.get(col.columnName);
          if (analysisCol) {
            // Update missing count/percentage from analysis
            return {
              ...col,
              missingCount: analysisCol.missingCount,
              missingPercentage: analysisCol.missingPercentage,
            };
          }
          // Keep existing column even if not in current analysis (preserve user config)
          return col;
        });

        // Add any new columns from analysis that aren't in existing config
        columnsWithMissing.forEach((col) => {
          if (!existingColumnsMap.has(col.columnName)) {
            syncedColumns.push(col);
          }
        });

        // Sort by missing percentage (highest first)
        syncedColumns.sort((a, b) => b.missingPercentage - a.missingPercentage);

        // Only update if there are actual changes
        const needsUpdate =
          syncedColumns.length !== columns.length ||
          syncedColumns.some(
            (col, idx) =>
              !columns[idx] ||
              col.columnName !== columns[idx]?.columnName ||
              col.missingCount !== columns[idx]?.missingCount ||
              col.missingPercentage !== columns[idx]?.missingPercentage ||
              col.strategy !== columns[idx]?.strategy ||
              col.imputeValue !== columns[idx]?.imputeValue
          );

        if (needsUpdate) {
          setColumns(syncedColumns);
            onChange({
              enabled: true,
              columns: syncedColumns,
            });
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisResult]);

  const handleStrategyChange = (
    columnName: string,
    strategy: MissingValueStrategy
  ) => {
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? { 
            ...col, 
            strategy, 
            imputeValue: strategy === "impute_constant" 
              ? (col.imputeValue ?? "0") // Default to "0" if not set
              : undefined 
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: true,
      columns: newColumns,
    });
  };

  const handleImputeValueChange = (columnName: string, value: string) => {
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            imputeValue: value,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: true,
      columns: newColumns,
    });
  };

  const columnsWithMissing = getColumnsWithMissingValues();

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Handle Missing Values</Label>
        <p className="text-xs text-gray-500">
          Configure how to handle missing values in columns
        </p>
      </div>

      {(
        <div className="space-y-2">
          {!analysisResult ? (
            <p className="text-sm text-gray-500 italic py-2">
              Please analyze the CSV file first to see columns with missing values.
            </p>
          ) : columnsWithMissing.length === 0 ? (
            <p className="text-sm text-gray-500 italic py-2">
              No columns with missing values found.
            </p>
          ) : (
            <div className="space-y-3">
              <Label className="text-sm">Columns with Missing Values</Label>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {columns.map((column) => (
                  <div
                    key={column.columnName}
                    className="flex items-center justify-between p-3 border rounded hover:bg-gray-50 gap-4"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Label className="font-medium text-sm">
                          {column.columnName}
                        </Label>
                        <span className="text-xs text-gray-500">
                          ({column.missingCount} missing,{" "}
                          {column.missingPercentage.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Select
                        value={column.strategy}
                        onValueChange={(value) =>
                          handleStrategyChange(
                            column.columnName,
                            value as MissingValueStrategy
                          )
                        }
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue placeholder="Select strategy" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="no_action">
                            No Action
                          </SelectItem>
                          <SelectItem value="drop_column">
                            Drop Column
                          </SelectItem>
                          <SelectItem value="drop_rows">Drop Rows</SelectItem>
                          <SelectItem value="impute_constant">
                            Impute as Constant
                          </SelectItem>
                          <SelectItem value="impute_mean">
                            Impute as Mean
                          </SelectItem>
                          <SelectItem value="impute_median">
                            Impute as Median
                          </SelectItem>
                          <SelectItem value="impute_mode">
                            Impute as Mode
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      {column.strategy === "impute_constant" && (
                        <Input
                          type="text"
                          placeholder="0"
                          value={column.imputeValue?.toString() || "0"}
                          onChange={(e) =>
                            handleImputeValueChange(
                              column.columnName,
                              e.target.value || "0"
                            )
                          }
                          className="w-[120px]"
                        />
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500">
                {columns.length} column{columns.length !== 1 ? "s" : ""} with
                missing values. Sorted by percentage (highest first).
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

