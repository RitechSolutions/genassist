import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import { RichInput } from "@/components/richInput";
import { Checkbox } from "@/components/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Upload, Mic, Square } from "lucide-react";
import { Button } from "@/components/button";
import { getValueFromPath } from "../utils/helpers";
import { SchemaType } from "../types/schemas";
import { GenericTestInputField } from "./GenericTestDialog";

const SCHEMA_TYPES: SchemaType[] = ["string", "number", "boolean", "object", "array", "any"];

interface TestInputFieldsProps {
  inputFields: GenericTestInputField[];
  formData: Record<string, string>;
  fieldTypes: Record<string, SchemaType>;
  availableData: Record<string, unknown> | null;
  hasWorkflowContext?: boolean;
  isLoading: boolean;
  onInputChange: (id: string, value: string) => void;
  onTypeChange: (id: string, newType: SchemaType) => void;
}

export const TestInputFields: React.FC<TestInputFieldsProps> = ({
  inputFields,
  formData,
  fieldTypes,
  availableData,
  hasWorkflowContext = false,
  isLoading,
  onInputChange,
  onTypeChange,
}) => {
  if (inputFields.length === 0) {
    if (hasWorkflowContext) {
      return (
        <div className="space-y-3">
          <Label>Workflow Context</Label>
          <div className="text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
            Values from upstream nodes (<code className="text-xs">source</code>,{" "}
            <code className="text-xs">session</code>) are applied automatically
            from your workflow test data. No manual input is required for dragged
            variables like{" "}
            <code className="text-xs">{`{{source.variable_name}}`}</code>.
          </div>
        </div>
      );
    }

    return (
      <div className="text-sm text-gray-500 italic">
        No variables found in node configuration or inputSchema
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {hasWorkflowContext && (
        <div className="text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
          Upstream <code className="text-xs">source</code> /{" "}
          <code className="text-xs">session</code> values are included automatically.
          Only custom parameters below need manual input.
        </div>
      )}
      <Label>Input Variables</Label>
      {inputFields.map((field) => {
        const currentType = fieldTypes[field.id] || "string";
        const isPrefilled = availableData && getValueFromPath(availableData, field.id) !== undefined;

        return (
          <div key={field.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor={field.id}>
                {field.label}
                {field.required && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </Label>
              <div className="flex items-center space-x-2">
                <select
                  value={currentType}
                  onChange={(e) =>
                    onTypeChange(field.id, e.target.value as SchemaType)
                  }
                  className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-300"
                  disabled={isLoading}
                >
                  {SCHEMA_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  {field.source || "config"}
                </span>
                {isPrefilled && (
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-200">
                    Prefilled
                  </span>
                )}
              </div>
            </div>
            {currentType === "boolean" ? (
              <div className="flex items-center space-x-2">
                <Checkbox
                  id={field.id}
                  checked={formData[field.id] === "true"}
                  onCheckedChange={(checked) =>
                    onInputChange(
                      field.id,
                      checked ? "true" : "false"
                    )
                  }
                  disabled={isLoading}
                />
                <Label
                  htmlFor={field.id}
                  className="text-sm font-normal"
                >
                  {field.placeholder || `Enable ${field.label}`}
                </Label>
              </div>
            ) : currentType === "object" || currentType === "array" ? (
              <div className="space-y-2">
                <RichTextarea
                  id={field.id}
                  placeholder={
                    field.placeholder ||
                    `Enter ${
                      currentType === "object"
                        ? "JSON object"
                        : "JSON array"
                    }`
                  }
                  value={formData[field.id] || ""}
                  onChange={(e) =>
                    onInputChange(field.id, e.target.value)
                  }
                  disabled={isLoading}
                  className={`flex-1 font-mono text-xs ${
                    isPrefilled ? "border-blue-300 bg-blue-50" : ""
                  }`}
                  rows={3}
                />
                <p className="text-xs text-gray-500">
                  {currentType === "object"
                    ? 'Enter a valid JSON object (e.g., {"key": "value"})'
                    : 'Enter a valid JSON array (e.g., ["item1", "item2"])'}
                </p>
              </div>
            ) : field.options && field.options.length > 0 ? (
              <Select
                value={formData[field.id] || ""}
                onValueChange={(val) => onInputChange(field.id, val)}
                disabled={isLoading}
              >
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder={field.placeholder || `Select ${field.label}`} />
                </SelectTrigger>
                <SelectContent className="z-[1300]">
                  {field.options.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <RichInput
                id={field.id}
                type={currentType === "number" ? "number" : field.type === "date" ? "date" : "text"}
                placeholder={field.placeholder}
                value={formData[field.id] || ""}
                onChange={(e) =>
                  onInputChange(field.id, e.target.value)
                }
                disabled={isLoading}
                className={`flex-1 ${
                  isPrefilled ? "border-blue-300 bg-blue-50" : ""
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

interface STTAudioInputProps {
  isLoading: boolean;
  isRecording: boolean;
  audioFileName: string | null;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

export const STTAudioInput: React.FC<STTAudioInputProps> = ({
  isLoading,
  isRecording,
  audioFileName,
  fileInputRef,
  onFileUpload,
  onStartRecording,
  onStopRecording,
}) => (
  <div className="space-y-3">
    <Label>Audio Input</Label>
    <div className="flex gap-2">
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        onChange={onFileUpload}
        className="hidden"
      />
      <Button
        variant="outline"
        onClick={() => fileInputRef.current?.click()}
        disabled={isLoading || isRecording}
        className="flex-1"
      >
        <Upload className="h-4 w-4 mr-2" />
        Upload Audio
      </Button>
      {!isRecording ? (
        <Button
          variant="outline"
          onClick={onStartRecording}
          disabled={isLoading}
          className="flex-1"
        >
          <Mic className="h-4 w-4 mr-2" />
          Record
        </Button>
      ) : (
        <Button
          variant="destructive"
          onClick={onStopRecording}
          className="flex-1"
        >
          <Square className="h-4 w-4 mr-2" />
          Stop Recording
        </Button>
      )}
    </div>
    {audioFileName && (
      <div className="text-sm text-green-600 bg-green-50 border border-green-200 rounded-md px-3 py-2">
        {audioFileName}
      </div>
    )}
    {isRecording && (
      <div className="flex items-center gap-2 text-sm text-red-600">
        <span className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
        Recording...
      </div>
    )}
  </div>
);
