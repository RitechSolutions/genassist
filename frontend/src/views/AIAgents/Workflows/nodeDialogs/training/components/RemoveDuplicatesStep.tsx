import React from "react";
import { Label } from "@/components/label";
import { Badge } from "@/components/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { RemoveDuplicatesStepConfig } from "../preprocessingConfig";

interface RemoveDuplicatesStepProps {
  config: RemoveDuplicatesStepConfig | undefined;
  onChange: (config: RemoveDuplicatesStepConfig) => void;
  availableColumns?: string[];
}

export const RemoveDuplicatesStep: React.FC<RemoveDuplicatesStepProps> = ({
  config,
  onChange,
  availableColumns = [],
}) => {
  const subsetColumns = config?.subsetColumns || [];
  const keep = config?.keep || "first";

  const toggleColumn = (columnName: string) => {
    const next = subsetColumns.includes(columnName)
      ? subsetColumns.filter((c) => c !== columnName)
      : [...subsetColumns, columnName];
    onChange({ subsetColumns: next, keep });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Remove Duplicate Rows</Label>
        <p className="text-xs text-muted-foreground">
          Drops rows that are exact duplicates. Optionally restrict the
          duplicate check to a subset of columns - leave empty to compare
          every column.
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-sm">Which row to keep</Label>
        <Select
          value={keep}
          onValueChange={(value) =>
            onChange({ subsetColumns, keep: value as "first" | "last" })
          }
        >
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="Select" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="first">Keep first occurrence</SelectItem>
            <SelectItem value="last">Keep last occurrence</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {availableColumns.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm">
            Columns to compare (optional - none selected means all columns)
          </Label>
          <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
            {availableColumns.map((columnName) => (
              <Badge
                key={columnName}
                variant={subsetColumns.includes(columnName) ? "default" : "outline"}
                className="cursor-pointer hover:opacity-80 transition-opacity"
                onClick={() => toggleColumn(columnName)}
              >
                {columnName}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
