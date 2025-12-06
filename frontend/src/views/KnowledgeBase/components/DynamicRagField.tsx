import React from "react";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

interface DynamicRagFieldProps {
  field: FieldSchema;
  value: unknown;
  onChange: (name: string, value: unknown) => void;
  disabled?: boolean;
}

export const DynamicRagField: React.FC<DynamicRagFieldProps> = ({
  field,
  value,
  onChange,
  disabled = false,
}) => {
  const handleChange = (newValue: unknown) => {
    onChange(field.name, newValue);
  };

  const renderField = () => {
    switch (field.type) {
      case "text":
        return (
          <Input
            type="text"
            value={(value as string) || ""}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.description || `Enter ${field.label}`}
            disabled={disabled}
          />
        );

      case "number":
        return (
          <Input
            type="number"
            value={String((value as number) || field.default || "")}
            onChange={(e) => {
              const numValue = parseFloat(e.target.value);
              handleChange(isNaN(numValue) ? "" : numValue);
            }}
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.description || `Enter ${field.label}`}
            disabled={disabled}
          />
        );

      case "boolean":
        return (
          <div className="flex items-center space-x-2">
            <Switch
              checked={Boolean(value)}
              onCheckedChange={handleChange}
              disabled={disabled}
            />
            <span className="text-sm text-gray-500">
              {Boolean(value) ? "Enabled" : "Disabled"}
            </span>
          </div>
        );

      case "select":
        return (
          <Select
            value={(value as string) || (field.default as string) || ""}
            onValueChange={handleChange}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder={`Select ${field.label}`} />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );

      default:
        return (
          <Input
            type="text"
            value={(value as string) || ""}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={field.description || `Enter ${field.label}`}
            disabled={disabled}
          />
        );
    }
  };

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name} className="text-sm font-medium">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </Label>
      {renderField()}
      {field.description && (
        <p className="text-xs text-gray-500">{field.description}</p>
      )}
    </div>
  );
};
