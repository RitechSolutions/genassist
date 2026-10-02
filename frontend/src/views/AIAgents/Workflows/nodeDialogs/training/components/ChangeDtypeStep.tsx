import React from "react";
import { Label } from "@/components/label";
import { Badge } from "@/components/badge";
import { RichInput } from "@/components/richInput";
import { Button } from "@/components/button";
import { X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  ChangeDtypeItem,
  ChangeDtypeStepConfig,
  ChangeDtypeTarget,
} from "../preprocessingConfig";

interface ChangeDtypeStepProps {
  config: ChangeDtypeStepConfig | undefined;
  onChange: (config: ChangeDtypeStepConfig) => void;
  availableColumns?: string[];
}

const DTYPE_OPTIONS: { value: ChangeDtypeTarget; label: string }[] = [
  { value: "int", label: "Integer" },
  { value: "float", label: "Float" },
  { value: "string", label: "String" },
  { value: "bool", label: "Boolean" },
  { value: "datetime", label: "Datetime" },
];

export const ChangeDtypeStep: React.FC<ChangeDtypeStepProps> = ({
  config,
  onChange,
  availableColumns = [],
}) => {
  const conversions = config?.conversions || [];

  const updateConversions = (next: ChangeDtypeItem[]) =>
    onChange({ conversions: next });

  const toggleColumn = (columnName: string) => {
    const exists = conversions.some((c) => c.columnName === columnName);
    updateConversions(
      exists
        ? conversions.filter((c) => c.columnName !== columnName)
        : [...conversions, { columnName, dtype: "string" }]
    );
  };

  const updateDtypeForColumn = (columnName: string, dtype: ChangeDtypeTarget) => {
    updateConversions(
      conversions.map((c) => (c.columnName === columnName ? { ...c, dtype } : c))
    );
  };

  const addManualRow = () => {
    updateConversions([...conversions, { columnName: "", dtype: "string" }]);
  };

  const updateManualRow = (index: number, patch: Partial<ChangeDtypeItem>) => {
    updateConversions(
      conversions.map((c, i) => (i === index ? { ...c, ...patch } : c))
    );
  };

  const removeRowAt = (index: number) => {
    updateConversions(conversions.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Change Column Data Type</Label>
        <p className="text-xs text-muted-foreground">
          Convert one or more columns to a different data type.
        </p>
      </div>

      {availableColumns.length > 0 ? (
        <>
          <div className="space-y-2">
            <Label className="text-sm">Columns to convert</Label>
            <div className="flex flex-wrap gap-2 max-h-64 overflow-y-auto p-2 border rounded">
              {availableColumns.map((columnName) => (
                <Badge
                  key={columnName}
                  variant={
                    conversions.some((c) => c.columnName === columnName)
                      ? "default"
                      : "outline"
                  }
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                  onClick={() => toggleColumn(columnName)}
                >
                  {columnName}
                </Badge>
              ))}
            </div>
          </div>

          {conversions.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm">New data type per column</Label>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {conversions.map((item) => (
                  <div
                    key={item.columnName}
                    className="flex items-center justify-between p-3 border rounded hover:bg-muted gap-4"
                  >
                    <Label className="font-medium text-sm truncate">
                      {item.columnName}
                    </Label>
                    <Select
                      value={item.dtype}
                      onValueChange={(value) =>
                        updateDtypeForColumn(item.columnName, value as ChangeDtypeTarget)
                      }
                    >
                      <SelectTrigger className="w-[160px] flex-shrink-0">
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent>
                        {DTYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="space-y-2">
          <Label className="text-sm">Columns to convert</Label>
          <div className="space-y-2">
            {conversions.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <RichInput
                  type="text"
                  placeholder="Column name"
                  value={item.columnName}
                  onChange={(e) =>
                    updateManualRow(index, { columnName: e.target.value })
                  }
                  className="flex-1"
                />
                <Select
                  value={item.dtype}
                  onValueChange={(value) =>
                    updateManualRow(index, { dtype: value as ChangeDtypeTarget })
                  }
                >
                  <SelectTrigger className="w-[160px] flex-shrink-0">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    {DTYPE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 text-red-600 dark:text-red-400 hover:text-red-700"
                  onClick={() => removeRowAt(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
          <Button type="button" size="sm" variant="outline" onClick={addManualRow}>
            + Add column
          </Button>
        </div>
      )}
    </div>
  );
};
