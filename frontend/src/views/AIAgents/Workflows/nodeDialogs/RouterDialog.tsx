import React, { useState, useEffect } from "react";
import { RouterNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";

const CONDITION_OPTIONS = [
  "equal",
  "not_equal",
  "contains",
  "not_contain",
  "starts_with",
  "not_starts_with",
  "ends_with",
  "not_ends_with",
  "regex",
] as const;

type ConditionType = (typeof CONDITION_OPTIONS)[number];

type RouterDialogProps = BaseNodeDialogProps<RouterNodeData, RouterNodeData>;

export const RouterDialog: React.FC<RouterDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [compareCondition, setCompareCondition] =
    useState<ConditionType>("contains");
  const [firstValue, setFirstValue] = useState("");

  const [secondValue, setSecondValue] = useState("");

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setFirstValue(data.first_value ?? "");
      setCompareCondition(
        (data.compare_condition as ConditionType) ?? "contains"
      );
      setSecondValue(data.second_value ?? "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name: name,
      first_value: firstValue,
      compare_condition: compareCondition,
      second_value: secondValue,
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
        first_value: firstValue,
        compare_condition: compareCondition,
        second_value: secondValue,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="node-name">Node Name</Label>
        <Input
          id="node-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter the name of this node"
          className="w-full"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="path_name">First Value</Label>
        <DraggableInput
          id="path_name"
          value={firstValue}
          onChange={(e) => setFirstValue(e.target.value)}
          placeholder="first value to compare"
          className="w-full"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="compare_condition">Compare Condition</Label>
        <Select
          value={compareCondition}
          onValueChange={(value) => setCompareCondition(value as ConditionType)}
        >
          <SelectTrigger id="compare_condition">
            <SelectValue placeholder="Select condition" />
          </SelectTrigger>
          <SelectContent>
            {CONDITION_OPTIONS.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt.replace(/_/g, " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="value_condition">Second Value</Label>
        <DraggableInput
          id="value_condition"
          value={secondValue}
          onChange={(e) => setSecondValue(e.target.value)}
          placeholder="second value to compare"
          className="w-full"
        />
      </div>
    </NodeConfigPanel>
  );
};
