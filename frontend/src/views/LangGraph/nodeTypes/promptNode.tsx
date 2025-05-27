import React, { useEffect, useState, useCallback } from "react";
import { Position, NodeProps, useUpdateNodeInternals } from "reactflow";
import { PromptNodeData, NodeHandler } from "../types/nodes";
import { Button } from "@/components/button";
import { FileText, Save } from "lucide-react";
import { HandleTooltip } from "../components/HandleTooltip";
import DynamicTemplateInput from "../components/DynamicTemplateInput";
import { createSimpleSchema, NodeSchema } from "../types/schemas";
import { extractDynamicVariables } from "../utils/apiHelpers";
import { getNodeColors } from "../utils/nodeColors";

const PromptNode: React.FC<NodeProps<PromptNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const [dynamicFields, setDynamicFields] = useState<string[]>([]);
  const [includeHistory, setIncludeHistory] = useState(data.includeHistory || false);
  const updateNodeInternals = useUpdateNodeInternals();
  const colors = getNodeColors('promptNode');

  // Initialize handlers if they don't exist
  useEffect(() => {
    if (!data.handlers) {
      // Create handlers for each dynamic field
      const handlers: NodeHandler[] = [
        {
          id: 'output',
          type: 'source' as const,
          compatibility: 'text',
        }
      ];

      // Add input handlers for each dynamic field
      const variables = extractDynamicVariables(data.template || "Hello, {{user_query}}!");
      variables.forEach((field) => {
        handlers.push({
          id: `input_${field}`,
          type: 'target' as const,
          compatibility: 'text',
        });
      });

      data.updateNodeData?.(id, {
        ...data,
        handlers,
        template: data.template || "Hello, {{user_query}}!",
        includeHistory,
      });
    }
  }, []);

  // Handle template changes
  const handleTemplateChange = useCallback(
    (templateData: {
      template: string;
      fields: string[];
      inputSchema: NodeSchema;
      outputSchema: NodeSchema;
    }) => {
      // Extract variables from both {{value}} and @value formats
      const variables = extractDynamicVariables(templateData.template);
      setDynamicFields(Array.from(variables));

      // Update node internals to refresh handles
      updateNodeInternals(id);
      
      // Create handlers for each dynamic field
      const handlers: NodeHandler[] = [
        {
          id: 'output',
          type: 'source' as const,
          compatibility: 'text',
        }
      ];

      // Add input handlers for each dynamic field
      variables.forEach((field) => {
        handlers.push({
          id: `input_${field}`,
          type: 'target' as const,
          compatibility: 'text',
        });
      });

      // Update node data
      if (data.updateNodeData) {
        data.updateNodeData(id, {
          ...data,
          template: templateData.template,
          handlers,
          includeHistory,
        });
      }
    },
    [id, updateNodeInternals, data, includeHistory]
  );

  // Handle history checkbox change
  const handleHistoryChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.checked;
    setIncludeHistory(newValue);
    if (data.updateNodeData) {
      data.updateNodeData(id, {
        ...data,
        includeHistory: newValue,
      });
    }
  }, [id, data]);

  return (
    <div
      className={`border-2 rounded-md bg-white shadow-md w-[400px] ${
        selected ? "border-blue-500" : "border-gray-200"
      }`}
    >
      {/* Node header */}
      <div className={`px-4 py-2 border-b ${colors.header} flex justify-between items-center`}>
        <div className="flex items-center">
          <FileText className={`h-4 w-4 text-white mr-2`} />
          <div className="text-sm font-medium text-white">Prompt Template</div>
        </div>
       
      </div>

      {/* Content - Non-draggable area */}
      <div className="p-4" style={{ pointerEvents: "all" }}>
        <DynamicTemplateInput
          initialTemplate={data.template || "Hello, {{user_query}}!"}
          onChange={handleTemplateChange}
          height="120px"
        />
        <div className="mt-3 flex items-center">
          <input
            type="checkbox"
            id="includeHistory"
            checked={includeHistory}
            onChange={handleHistoryChange}
            className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
          />
          <label htmlFor="includeHistory" className="ml-2 text-sm text-gray-700">
            Include conversation history
          </label>
        </div>
      </div>

      {/* Render all handlers */}
      {data.handlers?.filter(handler => handler.type === 'source').map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.type === 'source' ? Position.Right : Position.Left}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          style={{ top: `${(index+1) * (100/data.handlers.length)}%` }}
        />
      ))}
      {data.handlers?.filter(handler => handler.type === 'target').map((handler, index) => (
        <HandleTooltip
          key={handler.id}
          type={handler.type}
          position={handler.type === 'source' ? Position.Right : Position.Left}
          id={handler.id}
          nodeId={id}
          compatibility={handler.compatibility}
          style={{ top: `${(index+1) * (100/data.handlers.length)}%` }}
        />
      ))}
    </div>
  );
};

export default PromptNode;
