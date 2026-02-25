import React, { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Save, HelpCircle, Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/hover-card";
import { SetStateNodeData, ChatInputNodeData } from "@/views/AIAgents/Workflows/types/nodes";
import { SchemaField } from "@/views/AIAgents/Workflows/types/schemas";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { useNodes } from "reactflow";

type SetStateDialogProps = BaseNodeDialogProps<
  SetStateNodeData,
  SetStateNodeData
>;

interface StateEntry {
  key: string;
  value: string;
}

export const SetStateDialog: React.FC<SetStateDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const nodes = useNodes();

  const [name, setName] = useState(data.name);
  const [states, setStates] = useState<StateEntry[]>([]);

  // Get all stateful parameters from chat input nodes
  const statefulParams = useMemo(() => {
    const params: string[] = [];
    
    nodes.forEach((node) => {
      if (node.type === "chatInputNode") {
        const nodeData = node.data as ChatInputNodeData;
        if (nodeData?.inputSchema) {
          const inputSchema = nodeData.inputSchema as Record<string, SchemaField>;
          Object.entries(inputSchema).forEach(([key, field]) => {
            if (field?.stateful && key !== "conversation_history") {
              params.push(key);
            }
          });
        }
      }
    });
    
    return params;
  }, [nodes]); // Re-run when nodes change

  useEffect(() => {
    if (isOpen) {
      setName(data.name);
      // Migrate legacy single state to array format, or use existing states
      if (data.states && data.states.length > 0) {
        setStates([...data.states]);
      } else if (data.stateKey && data.stateValue) {
        // Migrate legacy format
        setStates([{ key: data.stateKey, value: data.stateValue }]);
      } else {
        setStates([{ key: "", value: "" }]);
      }
    }
  }, [isOpen, data]);

  const addStateEntry = () => {
    setStates([...states, { key: "", value: "" }]);
  };

  const removeStateEntry = (index: number) => {
    setStates(states.filter((_, i) => i !== index));
  };

  const updateStateEntry = (index: number, field: "key" | "value", value: string) => {
    const updated = [...states];
    updated[index] = { ...updated[index], [field]: value };
    setStates(updated);
  };

  const handleSave = () => {
    // Filter out empty entries
    const validStates = states.filter((s) => s.key.trim() !== "");
    const updatedData = {
      ...data,
      name,
      states: validStates,
      // Clear legacy fields
      stateKey: undefined,
      stateValue: undefined,
    };
    onUpdate(updatedData);
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={states.length === 0 || states.every((s) => !s.key.trim())}
          >
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        states,
      }}
    >
      <div className="space-y-4">
        <div>
          <Label>Node Name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label>State Entries</Label>
            <HoverCard>
              <HoverCardTrigger>
                <HelpCircle className="h-4 w-4 text-gray-500" />
              </HoverCardTrigger>
              <HoverCardContent className="w-80">
                <div className="space-y-2">
                  <p className="text-sm font-medium">
                    State Entries Guidelines:
                  </p>
                  <ul className="text-xs space-y-1">
                    <li>
                      • Add multiple state entries to update several parameters at once
                    </li>
                    <li>
                      • Select stateful parameters from chat input nodes
                    </li>
                    <li>
                      • Use {"{{variable}}"} syntax for dynamic values
                    </li>
                    <li>
                      • Values will persist across workflow executions
                    </li>
                  </ul>
                </div>
              </HoverCardContent>
            </HoverCard>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addStateEntry}
            className="flex items-center gap-1"
          >
            <Plus className="h-3 w-3" />
            Add State
          </Button>
        </div>

        {states.length === 0 && (
          <div className="text-sm text-gray-500 text-center py-4 border border-dashed rounded-md">
            No state entries. Click "Add State" to add one.
          </div>
        )}

        <div className="space-y-4">
          {states.map((state, index) => (
            <div
              key={index}
              className="p-4 border border-gray-200 rounded-md space-y-3 bg-gray-50"
            >
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">
                  State Entry {index + 1}
                </Label>
                {states.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeStateEntry(index)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-xs">State Key</Label>
                {statefulParams.length > 0 ? (
                  <Select
                    value={state.key}
                    onValueChange={(value) =>
                      updateStateEntry(index, "key", value)
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select a stateful parameter" />
                    </SelectTrigger>
                    <SelectContent>
                      {statefulParams.map((param) => (
                        <SelectItem key={param} value={param}>
                          {param}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <>
                    <Input
                      value={state.key}
                      onChange={(e) =>
                        updateStateEntry(index, "key", e.target.value)
                      }
                      placeholder="Enter state key (must match a stateful parameter)"
                      className="w-full"
                    />
                    {index === 0 && (
                      <p className="text-xs text-gray-500">
                        No stateful parameters found. Mark parameters as "stateful" in the Start node.
                      </p>
                    )}
                  </>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-xs">State Value</Label>
                <DraggableInput
                  id={`state-value-${index}`}
                  value={state.value}
                  onChange={(e) =>
                    updateStateEntry(index, "value", e.target.value)
                  }
                  placeholder="Enter value or drag variable from JSON viewer"
                  className="w-full"
                />
                <div className="text-xs text-gray-400">
                  Use {"{{variable}}"} for dynamic values
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </NodeConfigPanel>
  );
};
