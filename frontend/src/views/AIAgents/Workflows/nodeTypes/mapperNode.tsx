import React, { useState, useCallback, useEffect } from "react";
import { Position, NodeProps, useUpdateNodeInternals } from "reactflow";
import { MapperNodeData } from "../types/nodes";
import { HandleTooltip } from "../components/HandleTooltip";
import { createSimpleSchema, NodeSchema } from "../types/schemas";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Plus, Trash2 } from "lucide-react";

const MapperNode: React.FC<NodeProps<MapperNodeData>> = ({
  id,
  data,
  selected,
}) => {
  const [mappings, setMappings] = useState<Array<{ inputField: string; outputField: string }>>(
    data.mappings || [{ inputField: "", outputField: "" }]
  );
  const updateNodeInternals = useUpdateNodeInternals();

  // Update node data when mappings change
  useEffect(() => {
    if (data.updateNodeData) {
      // Create input schema based on unique input fields
      const inputFields = new Set(mappings.map(m => m.inputField).filter(Boolean));
      const inputSchema = createSimpleSchema(
        Object.fromEntries(
          Array.from(inputFields).map(field => [
            field,
            { type: 'string', required: true, description: `Input field: ${field}` }
          ])
        )
      );

      // Create output schema based on unique output fields
      const outputFields = new Set(mappings.map(m => m.outputField).filter(Boolean));
      const outputSchema = createSimpleSchema(
        Object.fromEntries(
          Array.from(outputFields).map(field => [
            field,
            { type: 'string', required: true, description: `Output field: ${field}` }
          ])
        )
      );

      data.updateNodeData(id, {
        ...data,
        mappings,
        inputSchema,
        outputSchema,
      });
    }
    updateNodeInternals(id);
  }, [mappings, id, data, updateNodeInternals]);

  // Add new mapping
  const addMapping = useCallback(() => {
    setMappings([...mappings, { inputField: "", outputField: "" }]);
  }, [mappings]);

  // Remove mapping
  const removeMapping = useCallback((index: number) => {
    setMappings(mappings.filter((_, i) => i !== index));
  }, [mappings]);

  // Update mapping
  const updateMapping = useCallback((index: number, field: 'inputField' | 'outputField', value: string) => {
    const newMappings = [...mappings];
    newMappings[index] = { ...newMappings[index], [field]: value };
    setMappings(newMappings);
  }, [mappings]);

  return (
    <div
      className={`bg-white border-2 rounded-md w-80 ${
        selected ? "border-blue-500" : "border-gray-200"
      }`}
    >
      {/* Header */}
      <div
        className="flex justify-between items-center p-3 border-b bg-gradient-to-r from-blue-50 to-indigo-50 cursor-move"
        style={{ touchAction: "none" }}
        data-draggable="true"
      >
        <div className="font-semibold">Field Mapper</div>
      </div>

      {/* Content */}
      <div className="p-4" style={{ pointerEvents: "all" }}>
        <div className="space-y-3">
          {mappings.map((mapping, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={mapping.inputField}
                onChange={(e) => updateMapping(index, 'inputField', e.target.value)}
                placeholder="Input field"
                className="flex-1"
              />
              <div className="text-gray-500">→</div>
              <Input
                value={mapping.outputField}
                onChange={(e) => updateMapping(index, 'outputField', e.target.value)}
                placeholder="Output field"
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeMapping(index)}
                className="h-8 w-8"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={addMapping}
          className="mt-3 w-full"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Mapping
        </Button>
      </div>

      {/* Input Handle */}
      <HandleTooltip
        type="target"
        position={Position.Left}
        id="input"
        nodeId={id}
        text={
          data.inputSchema
            ? JSON.stringify(data.inputSchema, null, 2)
            : "No input schema defined"
        }
      />

      {/* Output Handle */}
      <HandleTooltip
        type="source"
        position={Position.Right}
        id="output"
        nodeId={id}
        text={
          data.outputSchema
            ? JSON.stringify(data.outputSchema, null, 2)
            : "No output schema defined"
        }
      />
    </div>
  );
};

export default MapperNode; 