import React from "react";
import { Label } from "@/components/label";
import { Badge } from "@/components/badge";
import { RichInput } from "@/components/richInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DropColumnOrRowStepConfig } from "../preprocessingConfig";

interface DropColumnOrRowStepProps {
  config: DropColumnOrRowStepConfig | undefined;
  onChange: (config: DropColumnOrRowStepConfig) => void;
  availableColumns?: string[];
}

export const DropColumnOrRowStep: React.FC<DropColumnOrRowStepProps> = ({
  config,
  onChange,
  availableColumns = [],
}) => {
  const target = config?.target || "column";
  const columns = config?.columns || [];
  const rowIndices = config?.rowIndices || [];

  const toggleColumn = (columnName: string) => {
    const next = columns.includes(columnName)
      ? columns.filter((c) => c !== columnName)
      : [...columns, columnName];
    onChange({ target: "column", columns: next, rowIndices });
  };

  const handleRowIndicesChange = (value: string) => {
    const parsed = value
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v.length > 0)
      .map((v) => parseInt(v, 10))
      .filter((n) => !isNaN(n));
    onChange({ target: "row", columns, rowIndices: parsed });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Remove Column/Row</Label>
        <p className="text-xs text-muted-foreground">
          Remove specific columns, or specific rows by their index.
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-sm">Target</Label>
        <Select
          value={target}
          onValueChange={(value) =>
            onChange({
              target: value as "column" | "row",
              columns,
              rowIndices,
            })
          }
        >
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="Select" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="column">Column(s)</SelectItem>
            <SelectItem value="row">Row(s) by index</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {target === "column" ? (
        <div className="space-y-2">
          <Label className="text-sm">Columns to remove</Label>
          {availableColumns.length > 0 ? (
            <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
              {availableColumns.map((columnName) => (
                <Badge
                  key={columnName}
                  variant={columns.includes(columnName) ? "default" : "outline"}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => toggleColumn(columnName)}
                >
                  {columnName}
                </Badge>
              ))}
            </div>
          ) : (
            <RichInput
              type="text"
              placeholder="Enter column names separated by commas"
              value={columns.join(", ")}
              onChange={(e) =>
                onChange({
                  target: "column",
                  columns: e.target.value
                    .split(",")
                    .map((c) => c.trim())
                    .filter((c) => c.length > 0),
                  rowIndices,
                })
              }
              className="w-full"
            />
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <Label className="text-sm">Row indices to remove</Label>
          <RichInput
            type="text"
            placeholder="e.g. 0, 5, 12"
            value={rowIndices.join(", ")}
            onChange={(e) => handleRowIndicesChange(e.target.value)}
            className="w-full"
          />
        </div>
      )}
    </div>
  );
};
