import React from "react";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { ChangeDtypeStepConfig, ChangeDtypeTarget } from "../preprocessingConfig";

interface ChangeDtypeStepProps {
  config: ChangeDtypeStepConfig | undefined;
  onChange: (config: ChangeDtypeStepConfig) => void;
  availableColumns?: string[];
}

export const ChangeDtypeStep: React.FC<ChangeDtypeStepProps> = ({
  config,
  onChange,
  availableColumns = [],
}) => {
  const columnName = config?.columnName || "";
  const dtype = config?.dtype || "string";

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Change Column Data Type</Label>
        <p className="text-xs text-muted-foreground">
          Convert a column to a different data type.
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-sm">Column</Label>
        {availableColumns.length > 0 ? (
          <Select
            value={columnName}
            onValueChange={(value) => onChange({ columnName: value, dtype })}
          >
            <SelectTrigger className="w-[240px]">
              <SelectValue placeholder="Select column" />
            </SelectTrigger>
            <SelectContent>
              {availableColumns.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <RichInput
            type="text"
            placeholder="Enter column name"
            value={columnName}
            onChange={(e) => onChange({ columnName: e.target.value, dtype })}
            className="w-[240px]"
          />
        )}
      </div>

      <div className="space-y-2">
        <Label className="text-sm">New data type</Label>
        <Select
          value={dtype}
          onValueChange={(value) =>
            onChange({ columnName, dtype: value as ChangeDtypeTarget })
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="int">Integer</SelectItem>
            <SelectItem value="float">Float</SelectItem>
            <SelectItem value="string">String</SelectItem>
            <SelectItem value="bool">Boolean</SelectItem>
            <SelectItem value="datetime">Datetime</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
};
