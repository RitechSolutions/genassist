import React, { useState, useEffect } from "react";
import { Label } from "@/components/label";
import { Input } from "@/components/input";
import { Badge } from "@/components/badge";
import { ColumnFilterConfig, ColumnFilterItem } from "../preprocessingConfig";

interface ColumnFilterProps {
  config: ColumnFilterConfig | undefined;
  onChange: (config: ColumnFilterConfig) => void;
  availableColumns?: string[]; // Column names from CSV analysis
}

export const ColumnFilter: React.FC<ColumnFilterProps> = ({
  config,
  onChange,
  availableColumns = [],
}) => {
  const [columns, setColumns] = useState<ColumnFilterItem[]>(
    config?.columns || []
  );
  const [commaSeparatedInput, setCommaSeparatedInput] = useState<string>(
    availableColumns.length === 0 && config?.columns && config.columns.length > 0
      ? config.columns.map((col) => col.name).join(", ")
      : ""
  );

  useEffect(() => {
    if (config) {
      setColumns(config.columns);
      // Sync comma-separated input when no availableColumns
      if (availableColumns.length === 0 && config.columns.length > 0) {
        setCommaSeparatedInput(
          config.columns.map((col) => col.name).join(", ")
        );
      }
    }
  }, [config, availableColumns.length]);

  // Sync columns with availableColumns when they change (only if no config columns exist)
  useEffect(() => {
    if (
      availableColumns.length > 0 &&
      (!config?.columns || config.columns.length === 0) &&
      columns.length === 0
    ) {
      // Initialize from availableColumns
      const initialColumns: ColumnFilterItem[] = availableColumns.map(
        (name) => ({
          name,
          selected: true,
        })
      );
      setColumns(initialColumns);
      onChange({
        enabled: true,
        columns: initialColumns,
      });
    } else if (availableColumns.length > 0) {
      // Sync: ensure all availableColumns are in the list, keep existing selections from config
      // Use config.columns as source of truth if available, otherwise use local columns state
      const sourceColumns = config?.columns && config.columns.length > 0 
        ? config.columns 
        : columns;
      
      const existingColumnsMap = new Map(
        sourceColumns.map((col) => [col.name, col])
      );

      const syncedColumns: ColumnFilterItem[] = availableColumns.map(
        (name) => {
          const existing = existingColumnsMap.get(name);
          // If column exists in config, use its selection state
          // If it's a new column (not in parsed config), mark as unselected by default
          return existing || { name, selected: false };
        }
      );

      // Only update if the order or content changed
      const needsUpdate =
        syncedColumns.length !== columns.length ||
        syncedColumns.some(
          (col, idx) => col.name !== columns[idx]?.name || col.selected !== columns[idx]?.selected
        );

      if (needsUpdate) {
        setColumns(syncedColumns);
        onChange({
          enabled: true,
          columns: syncedColumns,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableColumns, config?.columns]);

  const handleColumnToggle = (index: number, selected: boolean) => {
    const newColumns = [...columns];
    newColumns[index].selected = selected;
    setColumns(newColumns);
    onChange({
      enabled: true,
      columns: newColumns,
    });
  };

  const handleBadgeToggle = (columnName: string) => {
    const columnIndex = columns.findIndex((col) => col.name === columnName);
    if (columnIndex >= 0) {
      // Toggle existing column
      handleColumnToggle(columnIndex, !columns[columnIndex].selected);
    } else {
      // Add new column if it doesn't exist
      const newColumn: ColumnFilterItem = {
        name: columnName,
        selected: true,
      };
      const newColumns = [...columns, newColumn];
      setColumns(newColumns);
      onChange({
        enabled: true,
        columns: newColumns,
      });
    }
  };

  const handleCommaSeparatedInputChange = (value: string) => {
    setCommaSeparatedInput(value);
    // Parse comma-separated values
    const parsedColumns = value
      .split(",")
      .map((col) => col.trim())
      .filter((col) => col.length > 0)
      .map((name) => ({
        name,
        selected: true, // All columns are selected by default
      }));

    setColumns(parsedColumns);
    onChange({
      enabled: true,
      columns: parsedColumns,
    });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Filter Columns</Label>
        <p className="text-xs text-gray-500">
          Select which columns to keep in the dataframe
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-sm">Columns</Label>

        {/* Badge view when column names are available */}
        {availableColumns.length > 0 ? (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
              {availableColumns.map((columnName) => {
                const column = columns.find((col) => col.name === columnName);
                const isSelected = column?.selected ?? false;
                return (
                  <Badge
                    key={columnName}
                    variant={isSelected ? "default" : "outline"}
                    className="cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => handleBadgeToggle(columnName)}
                  >
                    {columnName}
                  </Badge>
                );
              })}
            </div>
            <p className="text-xs text-gray-500">
              {columns.filter((c) => c.selected).length} of {availableColumns.length}{" "}
              columns selected. Click badges to toggle selection.
            </p>
          </div>
        ) : (
          /* Comma-separated input when no column names available */
          <div className="space-y-3">
            <Input
              value={commaSeparatedInput}
              onChange={(e) =>
                handleCommaSeparatedInputChange(e.target.value)
              }
              placeholder="Enter column names separated by commas (e.g., col1, col2, col3)"
              className="w-full"
            />
            {columns.length > 0 && (
              <>
                <div className="flex flex-wrap gap-2 p-2 border rounded bg-gray-50">
                  {columns.map((column) => (
                    <Badge key={column.name} variant="default">
                      {column.name}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  {columns.length} column{columns.length !== 1 ? "s" : ""} added
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
