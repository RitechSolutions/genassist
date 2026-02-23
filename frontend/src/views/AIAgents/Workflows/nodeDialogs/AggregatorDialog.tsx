import React, { useState, useEffect } from "react";
import { AggregatorNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Save, Info } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Switch } from "@/components/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableInput } from "../components/custom/DraggableInput";
import { useWorkflowExecution } from "../context/WorkflowExecutionContext";
import { BaseNodeDialogProps } from "./base";

const AGGREGATION_STRATEGY_OPTIONS = [
  "list",
  "merge",
  "first",
  "last",
] as const;

type AggregationStrategyType = (typeof AGGREGATION_STRATEGY_OPTIONS)[number];

type AggregatorDialogProps = BaseNodeDialogProps<
  AggregatorNodeData,
  AggregatorNodeData
>;

export const AggregatorDialog: React.FC<AggregatorDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const { edges } = useWorkflowExecution();

  const [name, setName] = useState(data.name || "");
  const [aggregationStrategy, setAggregationStrategy] =
    useState<AggregationStrategyType>("list");
  const [timeoutSeconds, setTimeoutSeconds] = useState(15);
  const [forwardTemplate, setForwardTemplate] = useState("");
  const [requireAllInputs, setRequireAllInputs] = useState(true);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "");
      setAggregationStrategy(
        (data.aggregationStrategy as AggregationStrategyType) ?? "list"
      );
      setTimeoutSeconds(data.timeoutSeconds ?? 15);
      setRequireAllInputs(data.requireAllInputs ?? true);

      // Auto-generate default forward template from direct predecessor nodes
      const directSources =
        edges?.filter((e) => e.target === props.nodeId)?.map((e) => e.source) ??
        [];

      const autoTemplate = directSources.length
        ? directSources.map((id) => `{{node_outputs.${id}}}`).join(", ")
        : "";

      setForwardTemplate(data.forwardTemplate ?? autoTemplate);
    }
  }, [isOpen, data, edges, props.nodeId]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      aggregationStrategy,
      timeoutSeconds,
      forwardTemplate,
      requireAllInputs,
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
        aggregationStrategy,
        timeoutSeconds,
        forwardTemplate,
        requireAllInputs,
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
        <Label htmlFor="aggregation-strategy">Aggregation Strategy</Label>
        <Select
          value={aggregationStrategy}
          onValueChange={(value) =>
            setAggregationStrategy(value as AggregationStrategyType)
          }
        >
          <SelectTrigger id="aggregation-strategy">
            <SelectValue placeholder="Select aggregation strategy" />
          </SelectTrigger>
          <SelectContent>
            {AGGREGATION_STRATEGY_OPTIONS.map((strategy) => (
              <SelectItem key={strategy} value={strategy}>
                {strategy.charAt(0).toUpperCase() + strategy.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {aggregationStrategy === "list" && "Combine all results into a list"}
          {aggregationStrategy === "merge" &&
            "Merge all results into a single object"}
          {aggregationStrategy === "first" && "Use the first result received"}
          {aggregationStrategy === "last" && "Use the last result received"}
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="timeout-seconds">Timeout (seconds)</Label>
        <Input
          id="timeout-seconds"
          type="number"
          min="1"
          max="300"
          value={timeoutSeconds}
          onChange={(e) => setTimeoutSeconds(parseInt(e.target.value))}
          placeholder="15"
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          Maximum time to wait for all inputs before proceeding
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="forward-template">Forward Template</Label>
        <DraggableInput
          id="forward-template"
          value={forwardTemplate}
          onChange={(e) => setForwardTemplate(e.target.value)}
          placeholder="Enter forward template (optional)"
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          Template for forwarding aggregated results to downstream nodes
        </p>
      </div>

      <TooltipProvider>
        <div className="flex items-center gap-2 w-full !mt-6">
          <Label htmlFor="require-all-inputs">Require complete results</Label>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex rounded-full text-muted-foreground hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <Info className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-balance">
              When enabled, all connected branches must complete before results
              are merged. When disabled, available results are merged immediately
              without waiting for remaining branches.
            </TooltipContent>
          </Tooltip>
          <div className="flex-1" />
          <Switch
            id="require-all-inputs"
            checked={requireAllInputs}
            onCheckedChange={setRequireAllInputs}
          />
        </div>
      </TooltipProvider>

    </NodeConfigPanel>
  );
};
