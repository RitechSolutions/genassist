import React, { useEffect, useState } from "react";
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

const parseColumnNames = (value: string): string[] =>
  value
    .split(",")
    .map((c) => c.trim())
    .filter((c) => c.length > 0);

const parseRowIndices = (value: string): number[] =>
  value
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0)
    .map((v) => parseInt(v, 10))
    .filter((n) => !isNaN(n));

const sameList = <T,>(a: T[], b: T[]) =>
  a.length === b.length && a.every((v, i) => v === b[i]);

/**
 * The text a comma-separated input shows. It keeps whatever the user typed
 * (e.g. a trailing "0, " while they're about to type the next index) instead
 * of re-rendering from the parsed list on every keystroke, which would strip
 * the comma before the next value could be typed. It only resyncs from the
 * config when the config changes to something the current text doesn't
 * already mean (e.g. a step loaded from saved code).
 */
function useListText<T>(
  list: T[],
  parse: (value: string) => T[]
): [string, (value: string) => void] {
  const [text, setText] = useState(list.join(", "));
  useEffect(() => {
    if (!sameList(parse(text), list)) {
      setText(list.join(", "));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.join("\u0000")]);
  return [text, setText];
}

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
  const [columnText, setColumnText] = useListText(columns, parseColumnNames);
  const [rowText, setRowText] = useListText(rowIndices, parseRowIndices);

  const toggleColumn = (columnName: string) => {
    const next = columns.includes(columnName)
      ? columns.filter((c) => c !== columnName)
      : [...columns, columnName];
    onChange({ target: "column", columns: next, rowIndices });
  };

  const handleRowIndicesChange = (value: string) => {
    setRowText(value);
    onChange({ target: "row", columns, rowIndices: parseRowIndices(value) });
  };

  const handleColumnNamesChange = (value: string) => {
    setColumnText(value);
    onChange({ target: "column", columns: parseColumnNames(value), rowIndices });
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
              value={columnText}
              onChange={(e) => handleColumnNamesChange(e.target.value)}
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
            value={rowText}
            onChange={(e) => handleRowIndicesChange(e.target.value)}
            className="w-full"
          />
        </div>
      )}
    </div>
  );
};
