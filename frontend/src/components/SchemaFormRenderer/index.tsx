import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { FileUploader } from "@/components/FileUploader";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  DataSourceConfig,
  DataSourceField,
} from "@/interfaces/dataSource.interface";

interface SchemaFormRendererProps {
  schema: DataSourceConfig;
  connectionData: Record<string, string | number | boolean>;
  onChange: (fieldName: string, value: string | number | boolean) => void;
  showAdvanced: boolean;
  advancedOnly?: boolean;
}

export function SchemaFormRenderer({
  schema,
  connectionData,
  onChange,
  showAdvanced,
  advancedOnly = false,
}: SchemaFormRendererProps) {
  const isFieldVisible = (field: DataSourceField): boolean => {
    if (!field.conditional) return true;
    return connectionData[field.conditional.field] === field.conditional.value;
  };

  const renderField = (field: DataSourceField) => {
    const value = connectionData[field.name] ?? field.default;

    switch (field.type) {
      case "select":
        return (
          <Select
            value={value as string}
            onValueChange={(val) => onChange(field.name, val)}
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
            onChange={(e) => onChange(field.name, parseFloat(e.target.value))}
            placeholder={field.placeholder || field.label}
          />
        );

      case "password":
        return (
          <Input
            type="password"
            value={value as string}
            onChange={(e) => onChange(field.name, e.target.value)}
            placeholder={field.label}
          />
        );

      case "boolean":
        return (
          <Switch
            checked={Boolean(value)}
            onCheckedChange={(checked) => onChange(field.name, checked)}
          />
        );

      case "files":
        return (
          <FileUploader
            label=""
            initialServerFilePath={(value as string) || ""}
            initialOriginalFileName={
              (connectionData[`${field.name}_original_filename`] as string) ||
              ""
            }
            onUploadComplete={(result) => {
              onChange(field.name, result.file_path ?? result.file_url);
              onChange(
                `${field.name}_original_filename`,
                result.original_filename
              );
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
          />
        );
    }
  };

  const regularFields = schema.fields.filter(
    (f) => f.required && isFieldVisible(f)
  );
  const advancedFields = schema.fields.filter(
    (f) => !f.required && isFieldVisible(f)
  );

  const fieldsToRender = advancedOnly
    ? advancedFields
    : [...regularFields, ...(showAdvanced ? advancedFields : [])];

  return (
    <div className="space-y-4">
      {fieldsToRender.map((field) => (
        <div key={field.name} className="space-y-2">
          {field.type === "boolean" ? (
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor={field.name}>{field.label}</Label>
              {renderField(field)}
            </div>
          ) : (
            <>
              <Label htmlFor={field.name}>
                {field.label}
                {field.required && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </Label>
              {renderField(field)}
            </>
          )}
          {field.description && (
            <p className="text-sm text-muted-foreground">{field.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}
