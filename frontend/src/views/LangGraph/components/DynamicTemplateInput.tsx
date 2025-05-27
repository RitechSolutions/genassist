import React, { useState, useEffect, useCallback } from "react";
import { Textarea } from "@/components/textarea";
import { Badge } from "@/components/badge";
import { ScrollArea } from "@/components/scroll-area";
import { Button } from "@/components/button";
import { Save } from "lucide-react";
import { createSimpleSchema, NodeSchema } from "../types/schemas";

interface DynamicTemplateInputProps {
  initialTemplate?: string;
  onChange?: (data: {
    template: string;
    fields: string[];
    inputSchema: NodeSchema;
  }) => void;
  showProcessedOutput?: boolean;
  inputValues?: Record<string, string>;
  height?: string;
  placeholder?: string;
  readOnly?: boolean;
}

const DynamicTemplateInput: React.FC<DynamicTemplateInputProps> = ({
  initialTemplate = "",
  onChange,
  showProcessedOutput = false,
  inputValues = {},
  height = "100px",
  placeholder = "Enter your template with {{placeholders}}",
  readOnly = false,
}) => {
  const [template, setTemplate] = useState(initialTemplate);
  const [dynamicFields, setDynamicFields] = useState<string[]>([]);
  const [processedOutput, setProcessedOutput] = useState("");
  const [isDirty, setIsDirty] = useState(false);

  // Extract dynamic fields from the template
  const extractDynamicFields = useCallback((templateText: string) => {
    const regex = /\{\{([^{}]+)\}\}/g;
    const fields: string[] = [];
    let match;

    while ((match = regex.exec(templateText)) !== null) {
      fields.push(match[1]);
    }

    return [...new Set(fields)]; // Deduplicate fields
  }, []);

  // Process the template with input values
  const processTemplate = useCallback(
    (templateText: string, values: Record<string, string>) => {
      let processed = templateText;

      Object.entries(values).forEach(([key, value]) => {
        const regex = new RegExp(`\\{${key}\\}`, "g");
        processed = processed.replace(regex, value || `{${key}}`);
      });

      return processed;
    },
    []
  );

  // Create schemas based on the extracted fields
  const createSchemas = useCallback((fields: string[]) => {
    // Create input schema from dynamic fields
    const inputSchema = createSimpleSchema(
      fields.reduce(
        (acc, field) => ({
          ...acc,
          [field]: {
            type: "string",
            required: true,
            description: `The ${field} for the template`,
          },
        }),
        {}
      )
    );
    return { inputSchema };
  }, []);

  // Save changes and notify parent
  const saveChanges = useCallback(() => {
    const fields = extractDynamicFields(template);
    setDynamicFields(fields);

    const { inputSchema } = createSchemas(fields);

    // Process the template with the current input values
    if (showProcessedOutput) {
      const processed = processTemplate(template, inputValues);
      setProcessedOutput(processed);
    }

    // Notify parent component
    if (onChange) {
      onChange({
        template,
        fields,
        inputSchema,
      });
    }

    setIsDirty(false);
  }, [
    template,
    inputValues,
    extractDynamicFields,
    processTemplate,
    onChange,
    createSchemas,
    showProcessedOutput,
  ]);

  // Initialize on mount and when initialTemplate changes
  useEffect(() => {
    setTemplate(initialTemplate);
    saveChanges();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTemplate]);

  // Mark as dirty when template changes
  useEffect(() => {
    if (template !== initialTemplate) {
      setIsDirty(true);
    }
  }, [template, initialTemplate]);

  return (
    <div className="space-y-4">
      {/* Template Input */}
      <div className="space-y-2">
        <div className="flex justify-between">
          <label className="text-sm font-medium">Template</label>
          {isDirty && !readOnly && (
            <Button
              variant="ghost"
              size="icon"
              onClick={saveChanges}
              className="h-6 w-6 text-blue-500"
              title="Save changes"
            >
              <Save className="h-4 w-4" />
            </Button>
          )}
        </div>
        <Textarea
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          placeholder={placeholder}
          className={`min-h-[${height}] text-sm`}
          readOnly={readOnly}
        />
      </div>

      {/* Dynamic Fields */}
      {dynamicFields.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Dynamic Fields</label>
          <div className="flex flex-wrap gap-2">
            {dynamicFields.map((field) => (
              <Badge key={field} variant="outline" className="bg-blue-50">
                {field}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Processed Output */}
      {showProcessedOutput && processedOutput && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Processed Output</label>
          <ScrollArea className="h-20 border rounded-md p-2 bg-gray-50">
            <div className="text-sm whitespace-pre-wrap">{processedOutput}</div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
};

export default DynamicTemplateInput;
