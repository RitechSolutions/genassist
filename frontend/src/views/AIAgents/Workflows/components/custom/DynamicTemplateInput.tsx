import React, { useState, useEffect, useCallback } from "react";
import { Textarea } from "@/components/textarea";
import { Badge } from "@/components/badge";
import { ScrollArea } from "@/components/scroll-area";
import { createSimpleSchema, NodeSchema } from "../../types/schemas";

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

  // Memoized callbacks for performance
  const extractDynamicFields = useCallback((templateText: string) => {
    const regex = /\{\{([^{}]+)\}\}/g;
    const fields: string[] = [];
    let match;
    while ((match = regex.exec(templateText)) !== null) {
      fields.push(match[1]);
    }
    return [...new Set(fields)];
  }, []);

  const createSchemas = useCallback((fields: string[]) => {
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

  // Effect to sync state with the initialTemplate prop
  useEffect(() => {
    setTemplate(initialTemplate);
  }, [initialTemplate]);

  // Effect to process changes and notify parent component
  useEffect(() => {
    // Debounce the update to prevent excessive processing on every keystroke
    const handler = setTimeout(() => {
      const fields = extractDynamicFields(template);
      setDynamicFields(fields);

      const { inputSchema } = createSchemas(fields);

      if (showProcessedOutput) {
        const processed = processTemplate(template, inputValues);
        setProcessedOutput(processed);
      }

      if (onChange) {
        onChange({
          template,
          fields,
          inputSchema,
        });
      }
    }, 300); // 300ms debounce delay

    // Cleanup function to clear the timeout
    return () => {
      clearTimeout(handler);
    };
  }, [
    template,
    inputValues,
    onChange,
    showProcessedOutput,
    extractDynamicFields,
    createSchemas,
    processTemplate,
  ]);

  return (
    <div className="space-y-4">
      {/* Template Input */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Template</label>
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
