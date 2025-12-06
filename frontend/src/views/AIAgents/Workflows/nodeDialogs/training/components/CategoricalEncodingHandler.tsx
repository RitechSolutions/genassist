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
  CategoricalEncodingConfig,
  CategoricalEncodingItem,
  CategoricalEncodingStrategy,
} from "../preprocessingConfig";
import { CSVAnalysisResult } from "@/services/mlModels";

interface CategoricalEncodingHandlerProps {
  config: CategoricalEncodingConfig | undefined;
  onChange: (config: CategoricalEncodingConfig) => void;
  analysisResult: CSVAnalysisResult | null;
}

export const CategoricalEncodingHandler: React.FC<
  CategoricalEncodingHandlerProps
> = ({ config, onChange, analysisResult }) => {
  const [columns, setColumns] = useState<CategoricalEncodingItem[]>(
    config?.columns || []
  );

  // Get categorical columns from analysis result
  const getCategoricalColumns = (): CategoricalEncodingItem[] => {
    if (!analysisResult) return [];

    const categoricalColumns = analysisResult.columns_info
      .filter((col) => {
        // Only include columns that are categorical type
        return col.type === "categorical";
      })
      .map((col) => ({
        columnName: col.name,
        strategy: "no_action" as CategoricalEncodingStrategy, // Default strategy
        dropFirst: false, // Default for one-hot
      }));

    return categoricalColumns;
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
      const categoricalColumns = getCategoricalColumns();
      const configColumns = config?.columns || [];

      if (configColumns.length === 0 && categoricalColumns.length > 0) {
        // Initialize from analysis result only if no config exists
        setColumns(categoricalColumns);
        onChange({
          enabled: config?.enabled ?? true,
          columns: categoricalColumns,
        });
      } else if (configColumns.length > 0) {
        // Sync with analysis result - add new categorical columns that aren't in config
        // Use config.columns as source of truth to preserve user's settings
        const existingColumnsMap = new Map(
          configColumns.map((col) => [col.columnName, col])
        );

        // Build columns from config (source of truth)
        const syncedColumns: CategoricalEncodingItem[] = [...configColumns];

        // Add any new categorical columns from analysis that aren't in config
        categoricalColumns.forEach((col) => {
          if (!existingColumnsMap.has(col.columnName)) {
            syncedColumns.push({
              ...col,
              dropFirst: false,
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
    strategy: CategoricalEncodingStrategy
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

  const handleDropFirstChange = (columnName: string, dropFirst: boolean) => {
    const newColumns = columns.map((col) =>
      col.columnName === columnName
        ? {
            ...col,
            dropFirst,
          }
        : col
    );
    setColumns(newColumns);
    onChange({
      enabled: config?.enabled ?? true,
      columns: newColumns,
    });
  };

  const categoricalColumns = getCategoricalColumns();

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Categorical Encoding</Label>
        <p className="text-xs text-gray-500">
          Encode categorical columns for machine learning
        </p>
      </div>

      {(
        <div className="space-y-2">
          {!analysisResult ? (
            <p className="text-sm text-gray-500 italic py-2">
              Please analyze the CSV file first to see categorical columns.
            </p>
          ) : categoricalColumns.length === 0 ? (
            <p className="text-sm text-gray-500 italic py-2">
              No categorical columns found or all categorical columns are
              filtered out.
            </p>
          ) : (
            <div className="space-y-3">
              <Label className="text-sm">Categorical Columns</Label>
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
                              ({columnInfo.unique_count} unique
                              {columnInfo.category_count
                                ? `, ${columnInfo.category_count} categories`
                                : ""}
                              )
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Select
                          value={column.strategy}
                          onValueChange={(value) =>
                            handleStrategyChange(
                              column.columnName,
                              value as CategoricalEncodingStrategy
                            )
                          }
                        >
                          <SelectTrigger className="w-[160px]">
                            <SelectValue placeholder="Select encoding" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="no_action">No Action</SelectItem>
                            <SelectItem value="one_hot">One-Hot</SelectItem>
                            <SelectItem value="label">Label</SelectItem>
                            <SelectItem value="ordinal">Ordinal</SelectItem>
                          </SelectContent>
                        </Select>
                        {column.strategy === "one_hot" && (
                          <div className="flex items-center gap-2">
                            <Label className="text-xs">Drop First:</Label>
                            <Switch
                              checked={column.dropFirst ?? false}
                              onCheckedChange={(checked) =>
                                handleDropFirstChange(column.columnName, checked)
                              }
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-gray-500">
                {columns.length} categorical column
                {columns.length !== 1 ? "s" : ""} available. One-Hot creates
                binary columns, Label assigns numeric codes, Ordinal uses custom
                mapping.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

