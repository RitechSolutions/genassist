import React from "react";
import {
  FilterOperator,
  LoopCollect,
  LoopMode,
  LoopNodeData,
  LoopOnError,
} from "../types/nodes";
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
import {
  DEFAULT_FILTER_OPERATOR,
  FILTER_OPERATOR_GROUPS,
  FILTER_OPERATORS,
  filterOperatorIsText,
  filterOperatorNeedsValue,
} from "../nodeTypes/router/filterConditions";
import {
  DEFAULT_LOOP_MODE,
  defaultMaxIterations,
  LOOP_COLLECT_LABELS,
  LOOP_MAX_DELAY_SECONDS,
  LOOP_MAX_ITERATIONS_CAP,
  LOOP_MODE_LABELS,
  LOOP_ON_ERROR_LABELS,
  maxIterationsForMode,
  normalizeMaxIterations,
  normalizeSeconds,
  normalizeWholeNumber,
} from "../nodeTypes/router/loopConfig";

type LoopDialogProps = BaseNodeDialogProps<LoopNodeData, LoopNodeData>;

export const LoopDialog: React.FC<LoopDialogProps> = (props) => {
  const { onClose, data, nodeId } = props;

  const { values, setField, setValues, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      mode: data.mode ?? DEFAULT_LOOP_MODE,
      items: data.items ?? "",
      // Numbers are kept as text while editing so a field can be cleared and retyped.
      batchSize: String(data.batchSize || 1),
      maxIterations: String(data.maxIterations || defaultMaxIterations(data.mode)),
      stopField: data.stopField ?? "",
      stopOperator: data.stopOperator ?? DEFAULT_FILTER_OPERATOR,
      stopValue: data.stopValue ?? "",
      stopCaseSensitive: data.stopCaseSensitive ?? false,
      onError: data.onError ?? ("stop" as LoopOnError),
      delaySeconds: String(data.delaySeconds ?? 0),
      delayBackoff: data.delayBackoff ?? false,
      timeLimitSeconds: String(data.timeLimitSeconds ?? 0),
      collect: data.collect ?? ("all" as LoopCollect),
    }),
    (edits) => ({
      ...edits,
      batchSize: normalizeWholeNumber(edits.batchSize, 1, 1),
      maxIterations: normalizeMaxIterations(edits.maxIterations, edits.mode),
      delaySeconds: normalizeSeconds(edits.delaySeconds, LOOP_MAX_DELAY_SECONDS),
      timeLimitSeconds: normalizeSeconds(edits.timeLimitSeconds),
    })
  );

  const isForEach = values.mode === "forEach";
  const needsValue = filterOperatorNeedsValue(values.stopOperator);
  const isText = filterOperatorIsText(values.stopOperator);
  const hasDelay = normalizeSeconds(values.delaySeconds) > 0;
  // The Loop publishes each pass's result on itself, so the condition need not name a body node.
  const passResultVariable = `{{node_outputs.${nodeId}.result}}`;

  const changeMode = (mode: LoopMode) =>
    setValues((prev) => ({
      ...prev,
      mode,
      maxIterations: String(
        maxIterationsForMode(Number(prev.maxIterations) || undefined, prev.mode, mode)
      ),
    }));

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
        <Label htmlFor="loop-mode">Mode</Label>
        <Select value={values.mode} onValueChange={(value) => changeMode(value as LoopMode)}>
          <SelectTrigger id="loop-mode">
            <SelectValue placeholder="Select mode" />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(LOOP_MODE_LABELS) as LoopMode[]).map((mode) => (
              <SelectItem key={mode} value={mode}>
                {LOOP_MODE_LABELS[mode]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {isForEach
            ? "Runs the loop body once for every item of a list."
            : "Runs the loop body again and again until the stop condition is met."}
        </p>
      </div>

      {isForEach && (
        <div className="space-y-2">
          <Label htmlFor="loop-items">Items</Label>
          <DraggableInput
            id="loop-items"
            value={values.items}
            onChange={(e) => setField("items", e.target.value)}
            placeholder="e.g. the list of tickets from an upstream node"
            className="w-full"
          />
          <p className="text-sm text-muted-foreground">
            The list to go through, usually a variable from an upstream node.
            A number repeats that many times; plain text is split on lines or
            commas. Inside the loop, the current item is {"{{source.item}}"}.
          </p>
        </div>
      )}

      {isForEach && (
        <div className="space-y-2">
          <Label htmlFor="loop-batch-size">Batch size</Label>
          <RichInput
            id="loop-batch-size"
            type="number"
            min={1}
            value={values.batchSize}
            onChange={(e) => setField("batchSize", e.target.value)}
            className="w-full"
          />
          <p className="text-sm text-muted-foreground">
            Items per pass. With more than one, {"{{source.item}}"} is a list
            of that many items.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="loop-max-iterations">Maximum iterations</Label>
        <RichInput
          id="loop-max-iterations"
          type="number"
          min={1}
          max={LOOP_MAX_ITERATIONS_CAP}
          value={values.maxIterations}
          onChange={(e) => setField("maxIterations", e.target.value)}
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          {isForEach
            ? `Items beyond this number are not processed. At most ${LOOP_MAX_ITERATIONS_CAP}.`
            : `The loop ends after this many passes even if the stop condition was never met. At most ${LOOP_MAX_ITERATIONS_CAP}.`}
        </p>
      </div>

      <div className="space-y-3 rounded-md border p-3">
        <div className="space-y-0.5">
          <Label htmlFor="loop-stop-field">
            {isForEach ? "Stop early when (optional)" : "Repeat until"}
          </Label>
          <p className="text-xs text-muted-foreground">
            Checked after every pass. Use the output of a node inside the loop,
            for example the verdict of a reviewing step, or{" "}
            <button
              type="button"
              className="underline underline-offset-2 hover:text-foreground"
              onClick={() => setField("stopField", passResultVariable)}
            >
              the result of the pass
            </button>
            .
          </p>
        </div>
        <DraggableInput
          id="loop-stop-field"
          value={values.stopField}
          onChange={(e) => setField("stopField", e.target.value)}
          placeholder="e.g. the result of a node inside the loop"
          className="w-full"
        />
        <Select
          value={values.stopOperator}
          onValueChange={(value) => setField("stopOperator", value as FilterOperator)}
        >
          <SelectTrigger id="loop-stop-operator" aria-label="Operator">
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
        {needsValue && (
          <DraggableInput
            id="loop-stop-value"
            aria-label="Value"
            value={values.stopValue}
            onChange={(e) => setField("stopValue", e.target.value)}
            placeholder={isText ? "e.g. approved" : "e.g. 0.8"}
            className="w-full"
          />
        )}
        {isText && (
          <div className="flex items-center justify-between space-x-3">
            <Label htmlFor="loop-stop-case-sensitive">Case sensitive</Label>
            <Switch
              id="loop-stop-case-sensitive"
              checked={values.stopCaseSensitive}
              onCheckedChange={(checked) => setField("stopCaseSensitive", Boolean(checked))}
            />
          </div>
        )}
        {!isForEach && !values.stopField.trim() && (
          <p className="text-xs text-muted-foreground">
            Without a condition the loop simply runs the maximum number of
            passes.
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="loop-on-error">When a pass fails</Label>
        <Select
          value={values.onError}
          onValueChange={(value) => setField("onError", value as LoopOnError)}
        >
          <SelectTrigger id="loop-on-error">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(LOOP_ON_ERROR_LABELS) as LoopOnError[]).map((option) => (
              <SelectItem key={option} value={option}>
                {LOOP_ON_ERROR_LABELS[option]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          Either way the workflow continues from Done, with the failures listed
          in the loop's errors. A failed pass is never counted as a result.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="loop-delay">Wait between passes (seconds)</Label>
        <RichInput
          id="loop-delay"
          type="number"
          min={0}
          max={LOOP_MAX_DELAY_SECONDS}
          step="0.5"
          value={values.delaySeconds}
          onChange={(e) => setField("delaySeconds", e.target.value)}
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          Useful for rate limits and retries. 0 means no wait; at most{" "}
          {LOOP_MAX_DELAY_SECONDS} seconds.
        </p>
        {hasDelay && (
          <div className="flex items-center justify-between rounded-md border p-3 space-x-3">
            <div className="space-y-0.5">
              <Label htmlFor="loop-delay-backoff">Double the wait after every pass</Label>
              <p className="text-xs text-muted-foreground">
                Backs off between retries, up to {LOOP_MAX_DELAY_SECONDS} seconds.
              </p>
            </div>
            <Switch
              id="loop-delay-backoff"
              checked={values.delayBackoff}
              onCheckedChange={(checked) => setField("delayBackoff", Boolean(checked))}
            />
          </div>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="loop-time-limit">Time limit (seconds)</Label>
        <RichInput
          id="loop-time-limit"
          type="number"
          min={0}
          value={values.timeLimitSeconds}
          onChange={(e) => setField("timeLimitSeconds", e.target.value)}
          className="w-full"
        />
        <p className="text-sm text-muted-foreground">
          No new pass starts once the loop has run this long; a pass already
          running is allowed to finish. 0 means no limit.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="loop-collect">Results to keep</Label>
        <Select
          value={values.collect}
          onValueChange={(value) => setField("collect", value as LoopCollect)}
        >
          <SelectTrigger id="loop-collect">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(LOOP_COLLECT_LABELS) as LoopCollect[]).map((option) => (
              <SelectItem key={option} value={option}>
                {LOOP_COLLECT_LABELS[option]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          What Done receives in results. Keep fewer when the loop only runs
          for its side effects or the list is large.
        </p>
      </div>
    </NodeConfigPanel>
  );
};
