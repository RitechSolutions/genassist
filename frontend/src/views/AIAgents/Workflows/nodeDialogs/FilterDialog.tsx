import React from "react";
import { FilterNodeData, FilterOperator } from "../types/nodes";
import { useNodeDialogState } from "./useNodeDialogState";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Switch } from "@/components/switch";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import {
  DEFAULT_FILTER_OPERATOR,
  FILTER_OPERATOR_GROUPS,
  FILTER_OPERATORS,
  filterOperatorIsText,
  filterOperatorNeedsValue,
} from "../nodeTypes/router/filterConditions";

type FilterDialogProps = BaseNodeDialogProps<FilterNodeData, FilterNodeData>;

export const FilterDialog: React.FC<FilterDialogProps> = (props) => {
  const { onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(props, () => ({
    name: data.name || "",
    field: data.field ?? "",
    operator: data.operator ?? DEFAULT_FILTER_OPERATOR,
    value: data.value ?? "",
    caseSensitive: data.caseSensitive ?? false,
    stopMessage: data.stopMessage ?? "",
  }));

  const needsValue = filterOperatorNeedsValue(values.operator);
  const isText = filterOperatorIsText(values.operator);

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
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="node-name">Node Name</Label>
        <RichInput
          id="node-name"
          value={values.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="filter-field">Field</Label>
        <DraggableInput
          id="filter-field"
          value={values.field}
          onChange={(e) => setField("field", e.target.value)}
          placeholder="e.g. the status or score from an upstream node"
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          The value to check, usually a variable from an upstream node.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="filter-operator">Operator</Label>
        <Select
          value={values.operator}
          onValueChange={(value) => setField("operator", value as FilterOperator)}
        >
          <SelectTrigger id="filter-operator">
            <SelectValue placeholder="Select operator" />
          </SelectTrigger>
          <SelectContent>
            {FILTER_OPERATOR_GROUPS.map(({ group, label }) => (
              <SelectGroup key={group}>
                <SelectLabel>{label}</SelectLabel>
                {FILTER_OPERATORS.filter((o) => o.group === group).map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
        {!isText && needsValue && (
          <p className="text-sm text-muted-foreground">
            Compares numbers. The condition is false if either side is not a
            number.
          </p>
        )}
        {!needsValue && (
          <p className="text-sm text-muted-foreground">
            A variable that resolved to nothing counts as empty.
          </p>
        )}
      </div>

      {needsValue && (
        <div className="space-y-2">
          <Label htmlFor="filter-value">Value</Label>
          <DraggableInput
            id="filter-value"
            value={values.value}
            onChange={(e) => setField("value", e.target.value)}
            placeholder={isText ? "e.g. active" : "e.g. 0.8"}
            className="w-full"
          />
        </div>
      )}

      {isText && (
        <div className="flex items-center justify-between rounded-md border p-3 space-x-3">
          <div className="space-y-0.5">
            <Label htmlFor="filter-case-sensitive">Case sensitive</Label>
            <p className="text-xs text-muted-foreground">
              When off, "Active" and "active" are treated as the same.
            </p>
          </div>
          <Switch
            id="filter-case-sensitive"
            checked={values.caseSensitive}
            onCheckedChange={(checked) => setField("caseSensitive", Boolean(checked))}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="filter-stop-message">Message when stopped</Label>
        <DraggableTextArea
          id="filter-stop-message"
          size="hint"
          value={values.stopMessage}
          onChange={(e) => setField("stopMessage", e.target.value)}
          placeholder="Optional. e.g. Sorry, I can only help with active accounts."
          className="w-full text-sm"
        />
        <p className="text-sm text-muted-foreground">
          When the condition is false the branch stops. If that ends the
          conversation's main path, this message is sent as the reply.
        </p>
      </div>
    </NodeConfigPanel>
  );
};
