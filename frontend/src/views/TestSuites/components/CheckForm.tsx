import React from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { cn } from "@/helpers/utils";
import type { CheckKind, CheckLevel, ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import {
  CHECK_KINDS,
  CHECK_LEVELS,
  type CheckConversation,
  checkMissing,
  checkSentence,
  targetFields,
} from "../helpers/checks";
import { turnLabel } from "../helpers/datasetConversations";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";

const ANY_AGENT = "__any__";

interface CheckFormProps {
  check: ScenarioCheck;
  onChange: (check: ScenarioCheck) => void;
  onDone: () => void;
  onRemove: () => void;
  conversations: CheckConversation[];
  catalog: EvaluationCatalog;
  /** Told about rows the saved check could not keep, so saving waits for them too. */
  onProblem?: (problem: string | null) => void;
}

// A wrapping label names the select or input inside it.
const Field: React.FC<{ label: string; children: React.ReactNode; className?: string }> = ({
  label,
  children,
  className,
}) => (
  <label className={cn("block space-y-1", className)}>
    <span className="block text-xs font-medium leading-none">{label}</span>
    {children}
  </label>
);

const preview = (message: string): string => (message.length > 60 ? `${message.slice(0, 60)}…` : message);

export const CheckForm: React.FC<CheckFormProps> = ({
  check,
  onChange,
  onDone,
  onRemove,
  conversations,
  catalog,
  onProblem,
}) => {
  const update = (patch: Partial<ScenarioCheck>) => onChange({ ...check, ...patch });
  const missing = checkMissing(check);
  const conversation = conversations.find((item) => item.key === check.conversation_id);
  const agentTools = check.agent
    ? catalog.agents.find((agent) => agent.id === check.agent)?.tools ?? []
    : catalog.agents.flatMap((agent) => agent.tools);
  const tools = [...new Map(agentTools.map((tool) => [tool.id, tool])).values()];
  const router = catalog.routers.find((item) => item.id === check.router);
  const stateKeys = [...new Set(catalog.stateKeys.map((item) => item.key))];
  // Rows stay as typed, so an empty or repeated name doesn't merge two rows while editing.
  const [args, setArgRows] = React.useState<[string, string][]>(() => Object.entries(check.args ?? {}));
  const argNames = args.map(([key]) => key.trim());
  const argProblem =
    check.kind !== "tool_called"
      ? null
      : args.some(([key, value]) => !key.trim() && value.trim())
        ? "Name each value."
        : argNames.some((key, index) => key && argNames.indexOf(key) !== index)
          ? "Give each value a different name."
          : null;
  const problem = missing ?? argProblem;

  React.useEffect(() => {
    onProblem?.(argProblem);
    return () => onProblem?.(null);
  }, [argProblem, onProblem]);

  const setLevel = (level: CheckLevel) => {
    const first = conversations[0];
    update(
      targetFields({
        level,
        conversation: level === "every_conversation" ? undefined : conversation ?? first,
        turn: level === "turn" ? (conversation ?? first)?.turns[0] : undefined,
      }),
    );
  };

  const setConversation = (key: string) => {
    const picked = conversations.find((item) => item.key === key);
    update(targetFields({ level: check.level, conversation: picked, turn: picked?.turns[0] }));
  };

  const setTurn = (caseId: string) => {
    const turn = conversation?.turns.find((item) => item.caseId === caseId);
    update(targetFields({ level: "turn", conversation, turn }));
  };

  const setArgs = (rows: [string, string][]) => {
    setArgRows(rows);
    update({ args: Object.fromEntries(rows.filter(([key]) => key.trim())) });
  };

  return (
    <div className="space-y-4 rounded-lg border border-primary/40 bg-primary/5 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="inline-flex rounded-full border bg-background p-0.5">
          {(["should", "should_not"] as const).map((expect) => (
            <button
              key={expect}
              type="button"
              aria-pressed={check.expect === expect}
              // "Never" covers every turn, so Should not has no When to keep.
              onClick={() => update(expect === "should_not" ? { expect, when: "anywhere" } : { expect })}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                check.expect === expect ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {expect === "should" ? "Should" : "Should not"}
            </button>
          ))}
        </div>
        <Field label="What" className="min-w-[220px] flex-1">
          <Select value={check.kind} onValueChange={(kind) => update({ kind: kind as CheckKind })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHECK_KINDS.map((kind) => (
                <SelectItem key={kind.value} value={kind.value}>
                  {kind.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Where">
          <Select value={check.level} onValueChange={(level) => setLevel(level as CheckLevel)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHECK_LEVELS.map((level) => (
                <SelectItem
                  key={level.value}
                  value={level.value}
                  disabled={level.value !== "every_conversation" && conversations.length === 0}
                >
                  {level.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        {check.level === "every_conversation" && check.expect === "should" && (
          <Field label="When">
            <Select value={check.when} onValueChange={(when) => update({ when: when as ScenarioCheck["when"] })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anywhere">At some point</SelectItem>
                <SelectItem value="every_turn">On every turn</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        )}
        {check.level !== "every_conversation" && (
          <Field label="Conversation">
            <Select value={check.conversation_id ?? ""} onValueChange={setConversation}>
              <SelectTrigger>
                <SelectValue placeholder="Pick a conversation" />
              </SelectTrigger>
              <SelectContent>
                {conversations.map((item) => (
                  <SelectItem key={item.key} value={item.key}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        )}
        {check.level === "turn" && conversation && (
          <Field label="Turn" className="sm:col-span-2">
            <Select value={check.case_id ?? ""} onValueChange={setTurn}>
              <SelectTrigger>
                <SelectValue placeholder="Pick a turn" />
              </SelectTrigger>
              <SelectContent>
                {conversation.turns.map((turn) => (
                  <SelectItem key={turn.caseId} value={turn.caseId}>
                    {turnLabel(turn.position)}: {preview(turn.message)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        )}
      </div>

      {check.kind === "reply_mentions" && (
        <Field label="Words to look for">
          <Input
            value={check.text ?? ""}
            onChange={(event) => update({ text: event.target.value })}
            placeholder="e.g. RingGo"
          />
        </Field>
      )}

      {check.kind === "reply_meets" && (
        <Field label="Rule, in plain words">
          <Textarea
            value={check.rubric ?? ""}
            onChange={(event) => update({ rubric: event.target.value })}
            placeholder="e.g. Ask for the licence plate before creating a ticket"
            size="hint"
          />
        </Field>
      )}

      {check.kind === "tool_called" && (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Agent">
              <Select
                value={check.agent ?? ANY_AGENT}
                onValueChange={(id) => {
                  const agent = catalog.agents.find((item) => item.id === id);
                  // A tool the agent doesn't have could never be called by it.
                  const keepsTool = !agent || agent.tools.some((tool) => tool.id === check.tool);
                  update({
                    agent: agent?.id ?? null,
                    agent_name: agent?.label ?? null,
                    ...(keepsTool ? {} : { tool: null, tool_name: null }),
                  });
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY_AGENT}>Any agent</SelectItem>
                  {catalog.agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Tool">
              <Select
                value={check.tool ?? ""}
                onValueChange={(id) => {
                  const tool = tools.find((item) => item.id === id);
                  update({ tool: tool?.id ?? null, tool_name: tool?.name ?? null });
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder={catalog.loading ? "Loading tools…" : "Pick a tool"} />
                </SelectTrigger>
                <SelectContent>
                  {tools.map((tool) => (
                    <SelectItem key={tool.id} value={tool.id}>
                      {tool.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <div className="space-y-2">
            <Label className="text-xs">Values it is called with (optional)</Label>
            {args.map(([key, value], index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  value={key}
                  onChange={(event) =>
                    setArgs(args.map((entry, i) => (i === index ? [event.target.value, entry[1]] : entry)))
                  }
                  placeholder="Name, e.g. region"
                />
                <span className="text-muted-foreground">=</span>
                <Input
                  value={value}
                  onChange={(event) =>
                    setArgs(args.map((entry, i) => (i === index ? [entry[0], event.target.value] : entry)))
                  }
                  placeholder="Value, e.g. united-kingdom"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Remove value"
                  onClick={() => setArgs(args.filter((_, i) => i !== index))}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setArgs([...args, ["", ""]])}
            >
              Add value
            </Button>
          </div>
        </div>
      )}

      {check.kind === "step_runs" && (
        <Field label="Step">
          <Select
            value={check.step ?? ""}
            onValueChange={(id) => {
              const step = catalog.actionNodes.find((item) => item.id === id);
              update({ step: step?.id ?? null, step_name: step?.label ?? null });
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder={catalog.loading ? "Loading steps…" : "Pick a step"} />
            </SelectTrigger>
            <SelectContent>
              {catalog.actionNodes.map((step) => (
                <SelectItem key={step.id} value={step.id}>
                  {step.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}

      {check.kind === "route_taken" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Router">
            <Select
              value={check.router ?? ""}
              onValueChange={(id) => {
                const picked = catalog.routers.find((item) => item.id === id);
                update({ router: picked?.id ?? null, router_name: picked?.label ?? null, branch: null, branch_label: null });
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder={catalog.loading ? "Loading routers…" : "Pick a router"} />
              </SelectTrigger>
              <SelectContent>
                {catalog.routers.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Branch">
            <Select
              value={check.branch ?? ""}
              onValueChange={(value) => {
                const branch = router?.branches.find((item) => item.value === value);
                update({ branch: branch?.value ?? null, branch_label: branch?.label ?? null });
              }}
              disabled={!router}
            >
              <SelectTrigger>
                <SelectValue placeholder="Pick a branch" />
              </SelectTrigger>
              <SelectContent>
                {(router?.branches ?? []).map((branch) => (
                  <SelectItem key={branch.value} value={branch.value}>
                    {branch.label ?? branch.value}
                    {branch.destination ? ` → ${branch.destination}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      )}

      {check.kind === "state_equals" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Value name">
            <Input
              value={check.key ?? ""}
              onChange={(event) => update({ key: event.target.value })}
              placeholder="e.g. conversation_mode"
              list={`state-keys-${check.id}`}
            />
            <datalist id={`state-keys-${check.id}`}>
              {stateKeys.map((key) => (
                <option key={key} value={key} />
              ))}
            </datalist>
          </Field>
          <Field label="Should be">
            <Input
              value={check.value ?? ""}
              onChange={(event) => update({ value: event.target.value })}
              placeholder="e.g. refund"
            />
          </Field>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
        <p className={cn("text-sm", problem ? "text-destructive" : "text-muted-foreground")}>
          {problem ?? checkSentence(check)}
        </p>
        <div className="flex gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
            Remove
          </Button>
          <Button type="button" size="sm" onClick={onDone} disabled={Boolean(problem)}>
            Done
          </Button>
        </div>
      </div>
    </div>
  );
};
