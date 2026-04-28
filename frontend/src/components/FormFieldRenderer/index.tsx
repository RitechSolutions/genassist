import { Copy, Eraser } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { FileUploader } from "@/components/FileUploader";
import { TagsFieldInput } from "@/components/TagsFieldInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Button } from "@/components/button";
import { FieldSchema, FieldValue } from "@/interfaces/dynamicFormSchemas.interface";
import toast from "react-hot-toast";

interface FormFieldRendererProps {
  field: FieldSchema;
  value: FieldValue;
  onChange: (name: string, value: FieldValue) => void;
  disabled?: boolean;
  extras?: Record<string, FieldValue>;
}

export function FormFieldRenderer({
  field,
  value,
  onChange,
  disabled = false,
  extras,
}: FormFieldRendererProps) {
  const input = renderInput();

  return (
    <div className="space-y-2">
      {field.type === "boolean" ? (
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={field.name}>{field.label}</Label>
          {input}
        </div>
      ) : (
        <>
          <Label htmlFor={field.name}>
            {field.label}
            {field.required && <span className="text-red-500 ml-1">*</span>}
          </Label>
          {input}
        </>
      )}
      {field.description && (
        <p className="text-sm text-muted-foreground">{field.description}</p>
      )}
    </div>
  );

  function renderInput() {
    switch (field.type) {
      case "select":
        return (
          <Select
            value={(value ?? "") as string}
            onValueChange={(val) => onChange(field.name, val)}
            disabled={disabled}
          >
            <SelectTrigger className="w-full">
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

      case "number":
        return (
          <Input
            type="number"
            value={value as number}
            onChange={(e) => onChange(field.name, e.target.value === "" ? undefined : parseFloat(e.target.value))}
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.placeholder || field.label}
            disabled={disabled}
          />
        );

      case "password":
        return (
          <div className="flex flex-row items-center gap-2">
            <Input
              type="password"
              value={value as string}
              onChange={(e) => onChange(field.name, e.target.value)}
              placeholder={field.placeholder || field.label}
              disabled={disabled}
            />
            <Button
              variant="ghost"
              size="icon"
              disabled={disabled}
              onClick={(e) => {
                onChange(field.name, "");
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <Eraser className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              disabled={disabled}
              onClick={(e) => {
                navigator.clipboard.writeText(value as string);
                toast.success("Copied to clipboard");
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <Copy className="w-4 h-4" />
            </Button>
          </div>
        );

      case "boolean":
        return (
          <Switch
            checked={Boolean(value)}
            onCheckedChange={(checked) => onChange(field.name, checked)}
            disabled={disabled}
          />
        );

      case "tags":
        return (
          <TagsFieldInput
            id={field.name}
            value={value}
            fieldDefault={field.default}
            placeholder={field.placeholder || field.label}
            onChange={(next) => onChange(field.name, next)}
          />
        );

      case "files":
        return (
          <FileUploader
            label=""
            initialServerFilePath={(value as string) || ""}
            initialOriginalFileName={(extras?.original_filename as string) || ""}
            onUploadComplete={(result) => {
              onChange(field.name, result.file_path ?? result.file_url);
              onChange(`${field.name}_original_filename`, result.original_filename);
            }}
            onRemove={() => {
              onChange(field.name, "");
              onChange(`${field.name}_original_filename`, "");
            }}
            placeholder={field.placeholder || `Upload ${field.label}`}
          />
        );

      default:
        return (
          <Input
            type="text"
            value={value as string}
            onChange={(e) => onChange(field.name, e.target.value)}
            placeholder={field.placeholder || field.label}
            disabled={disabled}
          />
        );
    }
  }
}
