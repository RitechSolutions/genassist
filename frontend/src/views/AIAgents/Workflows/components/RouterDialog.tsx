import React, { useState, useEffect } from "react";
import { RouterNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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

interface RouterDialogProps {
  isOpen: boolean;
  onClose: () => void;
  data: RouterNodeData;
  onUpdate: (data: RouterNodeData) => void;
}

export const RouterDialog: React.FC<RouterDialogProps> = ({
  isOpen,
  onClose,
  data,
  onUpdate,
}) => {
  const [pathName, setPathName] = useState("");
  const [compareCondition, setCompareCondition] =
    useState<ConditionType>("contains");
  const [valueCondition, setValueCondition] = useState("");

  useEffect(() => {
    if (isOpen) {
      setPathName(data.path_name ?? "");
      setCompareCondition(
        (data.compare_condition as ConditionType) ?? "contains"
      );
      setValueCondition(data.value_condition ?? "");
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      path_name: pathName,
      compare_condition: compareCondition,
      value_condition: valueCondition,
    });
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Configure Router Path</DialogTitle>
          <DialogDescription>
            Set the conditions for this routing path. The input for this node
            will be compared against these values.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 flex flex-col space-y-4 p-1 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="path_name">Path Name</Label>
            <Input
              id="path_name"
              value={pathName}
              onChange={(e) => setPathName(e.target.value)}
              placeholder="e.g., path_true"
              readOnly
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="compare_condition">Compare Condition</Label>
            <Select
              value={compareCondition}
              onValueChange={(value) =>
                setCompareCondition(value as ConditionType)
              }
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
            <Label htmlFor="value_condition">Value Condition</Label>
            <Input
              id="value_condition"
              value={valueCondition}
              onChange={(e) => setValueCondition(e.target.value)}
              placeholder="e.g., success"
            />
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
