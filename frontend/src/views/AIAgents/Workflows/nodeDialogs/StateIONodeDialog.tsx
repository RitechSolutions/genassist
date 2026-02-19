import React, { useEffect, useMemo, useState } from "react";
import { StateIONodeData } from "../types/nodes";
import { BaseNodeDialogProps } from "./base";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save, Plus, Trash } from "lucide-react";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { useNodes } from "reactflow";
import { NodeSchema, SchemaField } from "../types/schemas";
import { valueToString } from "../utils/helpers";
import { DraggableInput } from "../components/custom/DraggableInput";

type Props = BaseNodeDialogProps<StateIONodeData, StateIONodeData>;

interface PersistentParamRow {
  key: string;
  schema: SchemaField;
}

interface ExtraVariableRow {
  id: string;
  key: string;
  value: string;
}

export const StateIONodeDialog: React.FC<Props> = (props) => {
  const { isOpen, onClose, data, onUpdate, nodeId } = props;

  const [name, setName] = useState(data.name || "");
  const [persistentValues, setPersistentValues] = useState<
    Record<string, string>
  >({});
  const [extraVariables, setExtraVariables] = useState<ExtraVariableRow[]>([]);

  const { state: executionState } = useWorkflowExecution();
  const reactFlowNodes = useNodes();

  // Collect all parameters from input schemas that have shouldPersist = true
  const persistentParams: PersistentParamRow[] = useMemo(() => {
    const results: Record<string, PersistentParamRow> = {};

    reactFlowNodes.forEach((node) => {
      const nodeData = node.data as { inputSchema?: NodeSchema } | undefined;
      const inputSchema: NodeSchema | undefined = nodeData?.inputSchema;
      if (!inputSchema) return;

      Object.entries(inputSchema).forEach(([key, field]) => {
        if ((field as SchemaField).shouldPersist) {
          if (!results[key]) {
            results[key] = { key, schema: field as SchemaField };
          }
        }
      });
    });

    return Object.values(results);
  }, [reactFlowNodes]);

  // Initialise form state when dialog opens or data changes
  useEffect(() => {
    if (!isOpen) return;

    setName(data.name || "");

    const configured = data.stateVariables || {};
    const session = executionState.session || {};

    const nextPersistentValues: Record<string, string> = {};
    persistentParams.forEach(({ key }) => {
      if (configured[key] !== undefined) {
        nextPersistentValues[key] = configured[key];
      } else if (session[key] !== undefined) {
        nextPersistentValues[key] = valueToString(session[key]);
      } else {
        nextPersistentValues[key] = "";
      }
    });

    setPersistentValues(nextPersistentValues);

    // Extra variables are any configured variables that are not known persistent params
    const persistentKeys = new Set(persistentParams.map((p) => p.key));
    const extras: ExtraVariableRow[] = Object.entries(configured)
      .filter(([key]) => !persistentKeys.has(key))
      .map(([key, value]) => ({
        id: `${key}-${Math.random().toString(36).slice(2)}`,
        key,
        value,
      }));
    setExtraVariables(extras);
  }, [isOpen, data, executionState.session, persistentParams]);

  const handlePersistentValueChange = (key: string, value: string) => {
    setPersistentValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleExtraKeyChange = (id: string, newKey: string) => {
    setExtraVariables((prev) =>
      prev.map((row) => (row.id === id ? { ...row, key: newKey } : row)),
    );
  };

  const handleExtraValueChange = (id: string, newValue: string) => {
    setExtraVariables((prev) =>
      prev.map((row) => (row.id === id ? { ...row, value: newValue } : row)),
    );
  };

  const handleAddExtra = () => {
    setExtraVariables((prev) => [
      ...prev,
      {
        id: `extra-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        key: "",
        value: "",
      },
    ]);
  };

  const handleRemoveExtra = (id: string) => {
    setExtraVariables((prev) => prev.filter((row) => row.id !== id));
  };

  const handleSave = () => {
    const finalStateVariables: Record<string, string> = {};

    // Include persistent variables with non-empty values
    Object.entries(persistentValues).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        finalStateVariables[key] = value;
      }
    });

    // Include extra variables with non-empty key and value
    extraVariables.forEach(({ key, value }) => {
      const trimmedKey = key.trim();
      if (trimmedKey && value !== "") {
        finalStateVariables[trimmedKey] = value;
      }
    });

    onUpdate({
      ...data,
      name,
      stateVariables: finalStateVariables,
    });
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        stateVariables: {
          ...persistentValues,
          ...Object.fromEntries(
            extraVariables
              .filter((row) => row.key.trim() && row.value !== "")
              .map((row) => [row.key.trim(), row.value]),
          ),
        },
      }}
    >
      <div className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="name">Node Name</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="State I/O"
            className="w-full"
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-semibold">
              Persistent parameters
            </Label>
            <span className="text-xs text-gray-500">
              Read-only keys from parameters with persistence enabled
            </span>
          </div>

          {persistentParams.length === 0 ? (
            <p className="text-xs text-gray-500 italic">
              No parameters in this workflow have persistence enabled yet.
              Toggle &quot;Should be persisted in the state?&quot; on parameters
              to see them here.
            </p>
          ) : (
            <div className="space-y-3 border-l-2 border-gray-200 pl-3">
              {persistentParams.map(({ key, schema }) => (
                <div key={key} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-gray-600 flex-1">
                      {key}
                      {schema.required && (
                        <span className="ml-1 text-red-500">*</span>
                      )}
                    </Label>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {schema.type}
                    </span>
                  </div>
                  {schema.description && (
                    <p className="text-[11px] text-gray-400">
                      {schema.description}
                    </p>
                  )}
                  <DraggableInput
                    value={persistentValues[key] ?? ""}
                    onChange={(e) =>
                      handlePersistentValueChange(key, e.target.value)
                    }
                    placeholder="Current state value (if any) will be used when empty"
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-semibold">
              Additional state variables
            </Label>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleAddExtra}
            >
              <Plus className="h-3 w-3 mr-1" />
              Add variable
            </Button>
          </div>

          {extraVariables.length === 0 ? (
            <p className="text-xs text-gray-500 italic">
              Define custom state keys here that don&apos;t come from input
              parameters.
            </p>
          ) : (
            <div className="space-y-3 border-l-2 border-dashed border-gray-200 pl-3">
              {extraVariables.map((row) => (
                <div key={row.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <DraggableInput
                      value={row.key}
                      onChange={(e) =>
                        handleExtraKeyChange(row.id, e.target.value)
                      }
                      placeholder="state key"
                      className="text-sm flex-1"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveExtra(row.id)}
                      className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50"
                    >
                      <Trash className="h-4 w-4" />
                    </Button>
                  </div>
                  <DraggableInput
                    value={row.value}
                    onChange={(e) =>
                      handleExtraValueChange(row.id, e.target.value)
                    }
                    placeholder="value"
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </NodeConfigPanel>
  );
};

