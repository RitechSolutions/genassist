import React, { useState } from "react";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Badge } from "@/components/badge";
import { X } from "lucide-react";

interface OrdinalOrderEditorProps {
  columnName: string;
  order: string[];
  // Distinct values found in the column by the CSV analysis, if available.
  categories?: string[];
  categoriesTruncated?: boolean;
  onChange: (order: string[]) => void;
}

/**
 * Lets the user set the order of a column's values for ordinal encoding
 * (e.g. Low < Medium < High -> 0, 1, 2). Values found in the data but not yet
 * placed in the order are listed so none are left out - training fails with
 * a clear error on any value that has no position.
 */
export const OrdinalOrderEditor: React.FC<OrdinalOrderEditorProps> = ({
  columnName,
  order,
  categories = [],
  categoriesTruncated = false,
  onChange,
}) => {
  const [newValue, setNewValue] = useState("");

  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= order.length) return;
    const next = [...order];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const remove = (index: number) => onChange(order.filter((_, i) => i !== index));

  const add = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed || order.includes(trimmed)) return;
    onChange([...order, trimmed]);
  };

  const unplaced = categories.filter((value) => !order.includes(value));

  return (
    <div className="space-y-2 p-3 border rounded bg-muted/30">
      <p className="text-xs text-muted-foreground">
        Order the values of <span className="font-medium">{columnName}</span> from lowest to
        highest. Each value is encoded as its position (0, 1, 2, …).
      </p>

      {order.length === 0 ? (
        <p className="text-xs text-red-600 dark:text-red-400">
          No values in the order yet. Add the column's values below - training fails until
          every value has a position.
        </p>
      ) : (
        <ol className="space-y-1">
          {order.map((value, index) => (
            <li key={value} className="flex items-center gap-2 text-sm">
              <span className="w-6 text-right text-xs text-muted-foreground">{index}</span>
              <span className="flex-1 truncate">{value}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0"
                onClick={() => move(index, -1)}
                disabled={index === 0}
                title="Move up"
              >
                ↑
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0"
                onClick={() => move(index, 1)}
                disabled={index === order.length - 1}
                title="Move down"
              >
                ↓
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0 text-red-600 dark:text-red-400"
                onClick={() => remove(index)}
                title="Remove from order"
              >
                <X className="h-3 w-3" />
              </Button>
            </li>
          ))}
        </ol>
      )}

      {unplaced.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-amber-700 dark:text-amber-400">
            {unplaced.length} value(s) in the data have no position yet - click to add:
          </p>
          <div className="flex flex-wrap gap-1">
            {unplaced.map((value) => (
              <Badge
                key={value}
                variant="outline"
                className="cursor-pointer hover:opacity-80"
                onClick={() => add(value)}
              >
                + {value}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {categoriesTruncated && (
        <p className="text-xs text-muted-foreground">
          The column has more values than listed here; add any others manually.
        </p>
      )}

      <div className="flex items-center gap-2">
        <RichInput
          type="text"
          placeholder="Add a value"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(newValue);
              setNewValue("");
            }
          }}
          className="flex-1"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            add(newValue);
            setNewValue("");
          }}
          disabled={!newValue.trim()}
        >
          Add
        </Button>
      </div>
    </div>
  );
};
