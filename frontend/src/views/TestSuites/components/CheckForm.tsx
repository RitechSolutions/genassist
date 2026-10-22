import React from "react";
import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group";
import { Ban, Check, Plus, X } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { cn } from "@/helpers/utils";
import type {
  CheckContext,
  CheckGrader,
  CheckKind,
  CheckLevel,
  CheckMatch,
  CheckToolRef,
  ScenarioCheck,
} from "@/interfaces/testEvaluation.interface";
import {
  CHECK_LEVELS,
  CONTEXTS,
  EMBEDDING_TYPES,
  EVERY_TURN_KINDS,
  GRADERS,
  GROUNDS,
  MATCH_MODES,
  MENTION_MODES,
  NLI_MODELS,
  PASS_SCORE,
  type CheckConversation,
  checkMissing,
  checkSentence,
  chosenConversations,
  findCheckTurn,
  isAiGraded,
  isPerTurn,
  isStepType,
  retarget,
  stepTypeLabel,
  targetFields,
  targetOf,
  toolRefs,
} from "../helpers/checks";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { CheckKindPicker } from "./CheckKindPicker";
import { ConversationChecklist } from "./ConversationChecklist";

const ANY = "__any__";
const EVALUATION_GRADER = "__evaluation__";
const REPLY_ONLY = "__reply__";
const TYPE_PREFIX = "type:";

interface CheckFormProps {
  check: ScenarioCheck;
  onChange: (check: ScenarioCheck) => void;
  onDone: () => void;
  onRemove: () => void;
  conversations: CheckConversation[];
  /** False while the dataset's turns load, so no pick reads as gone. */
  conversationsReady?: boolean;
  /** The dataset's turns could not be loaded. */
  conversationsFailed?: boolean;
  /** Bumped to bring the form into view again, as when saving points at it. */
  reveal?: number;
  catalog: EvaluationCatalog;
  /** Told about rows the saved check could not keep, so saving waits for them too. */
  onProblem?: (problem: string | null) => void;
  /** The AI graders a check graded by AI can pick from. */
  providers?: LLMProviderMinimal[];
}

type Update = (patch: Partial<ScenarioCheck>) => void;
type Tool = EvaluationCatalog["agents"][number]["tools"][number];

// A wrapping label names the select or input inside it; each field has its own row.
const Field: React.FC<{ label: string; hint?: string; children: React.ReactNode; className?: string }> = ({
  label,
  hint,
  children,
  className,
}) => (
  <label className={cn("block space-y-1.5", className)}>
    <span className="block text-sm font-medium leading-none">{label}</span>
    {children}
    {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
  </label>
);

const numberOrNull = (value: string): number | null => {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const SCORE_HINTS: Record<CheckGrader | "ai", string> = {
  ai: "From 0 to 1. The AI grader scores how well the reply did.",
  nli: "From 0 to 1. Each part of the reply must be supported at least this much.",
  similarity: "From 0 to 1. How alike the reply and its source must be.",
};

/** The score a check passes at, 0.5 unless changed, and the AI grader that scores it when it is graded by AI. */
const GradingFields: React.FC<{ check: ScenarioCheck; update: Update; providers: LLMProviderMinimal[] }> = ({
  check,
  update,
  providers,
}) => (
  <>
    {isAiGraded(check) && (
      <Field label="AI grader">
        <Select
          value={check.llm_provider_id ?? EVALUATION_GRADER}
          onValueChange={(id) => update({ llm_provider_id: id === EVALUATION_GRADER ? null : id })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={EVALUATION_GRADER}>The evaluation's AI grader</SelectItem>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
              </SelectItem>
            ))}
            {check.llm_provider_id && !providers.some((provider) => provider.id === check.llm_provider_id) && (
              <SelectItem value={check.llm_provider_id}>A grader that is no longer listed</SelectItem>
            )}
          </SelectContent>
        </Select>
      </Field>
    )}
    <Field label="Passes at score" hint={SCORE_HINTS[check.grader ?? "ai"]}>
      <Input
        type="number"
        min={0}
        max={1}
        step={0.05}
        value={check.pass_score ?? ""}
        placeholder={String(PASS_SCORE)}
        onChange={(event) => update({ pass_score: numberOrNull(event.target.value) })}
        className="sm:w-40"
      />
    </Field>
  </>
);

const AI_GRADER = "__ai__";
const GRADER_HINTS: Partial<Record<CheckGrader, string>> = {
  nli: "A model on the server checks each part of the reply against the source. No AI grader is used.",
  similarity: "Embeddings measure how alike the reply and its source are. No AI grader is used.",
};

/** Who decides whether a reply sticks to its source: the AI grader, or as NLI and Provenance did. */
const GraderFields: React.FC<{ check: ScenarioCheck; update: Update }> = ({ check, update }) => {
  const embedding = check.embedding ?? {};
  const type = embedding.type ?? "huggingface";
  const setEmbedding = (patch: Record<string, string>) => update({ embedding: { ...embedding, ...patch } });
  const nliModels =
    check.nli_model && !NLI_MODELS.some((model) => model.value === check.nli_model)
      ? [...NLI_MODELS, { value: check.nli_model, label: check.nli_model }]
      : NLI_MODELS;
  return (
    <>
      <Field label="Graded by" hint={check.grader ? GRADER_HINTS[check.grader] : undefined}>
        <Select
          value={check.grader ?? AI_GRADER}
          onValueChange={(value) => update({ grader: value === AI_GRADER ? null : (value as CheckGrader) })}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {GRADERS.map((grader) => (
              <SelectItem key={grader.value ?? AI_GRADER} value={grader.value ?? AI_GRADER}>
                {grader.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {check.grader === "nli" && (
        <>
          <Field label="NLI model">
            <Select value={check.nli_model ?? NLI_MODELS[0].value} onValueChange={(nli_model) => update({ nli_model })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {nliModels.map((model) => (
                  <SelectItem key={model.value} value={model.value}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <SwitchRow
            label="Fail when the reply contradicts the source"
            checked={Boolean(check.fail_on_contradiction)}
            onChange={(fail_on_contradiction) => update({ fail_on_contradiction })}
          />
        </>
      )}
      {check.grader === "similarity" && (
        <>
          <Field label="Embedding model">
            <Select value={type} onValueChange={(value) => setEmbedding({ type: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EMBEDDING_TYPES.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          {type === "bedrock" ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Model id">
                <Input value={embedding.model_id ?? ""} onChange={(event) => setEmbedding({ model_id: event.target.value })} />
              </Field>
              <Field label="Region">
                <Input
                  value={embedding.region_name ?? ""}
                  onChange={(event) => setEmbedding({ region_name: event.target.value })}
                  placeholder="e.g. us-east-1"
                />
              </Field>
            </div>
          ) : (
            <Field label="Model name">
              <Input
                value={embedding.model_name ?? ""}
                onChange={(event) => setEmbedding({ model_name: event.target.value })}
                placeholder={type === "openai" ? "text-embedding-3-small" : "all-MiniLM-L6-v2"}
              />
            </Field>
          )}
        </>
      )}
    </>
  );
};

const ExtraInstructionField: React.FC<{ check: ScenarioCheck; update: Update }> = ({ check, update }) => (
  <Field label="Also tell the AI grader (optional)">
    <Textarea
      value={check.rubric ?? ""}
      onChange={(event) => update({ rubric: event.target.value })}
      placeholder="e.g. Prices and dates must match exactly"
      size="hint"
    />
  </Field>
);

/** What an AI grader reads, with the path when it is a value in the run. */
const SourceFields: React.FC<{
  check: ScenarioCheck;
  update: Update;
  label: string;
  options: { value: CheckContext; label: string }[];
  /** The choice that means nothing more, when there is one. */
  none?: string;
}> = ({ check, update, label, options, none }) => (
  <>
    <Field label={label}>
      <Select
        value={check.context ?? (none ? REPLY_ONLY : options[0].value)}
        onValueChange={(value) => update({ context: value === REPLY_ONLY ? null : (value as CheckContext) })}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {none && <SelectItem value={REPLY_ONLY}>{none}</SelectItem>}
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
    {check.context === "run_value" && (
      <Field label="Where the value is">
        <Input
          value={check.context_path ?? ""}
          onChange={(event) => update({ context_path: event.target.value })}
          placeholder="e.g. trace.nodes.<step id>.output"
        />
      </Field>
    )}
  </>
);

/** The tools the other rows picked, so no tool is picked twice. */
const pickedElsewhere = (refs: CheckToolRef[], index: number) =>
  new Set(refs.flatMap((ref, i) => (i !== index && ref.tool ? [ref.tool] : [])));

/** One tool picker, without the tools other rows picked; a picked tool keeps its name, so one the version lacks still reads. */
const ToolSelect: React.FC<{
  value: CheckToolRef;
  tools: Tool[];
  taken: Set<string>;
  loading: boolean;
  label: string;
  onChange: (ref: CheckToolRef) => void;
}> = ({ value, tools, taken, loading, label, onChange }) => (
  <Select
    value={value.tool ?? ""}
    onValueChange={(id) => {
      const tool = tools.find((item) => item.id === id);
      onChange({ tool: tool?.id ?? null, tool_name: tool?.name ?? null });
    }}
  >
    <SelectTrigger aria-label={label}>
      <SelectValue placeholder={loading ? "Loading tools…" : (value.tool_name ?? "Pick a tool")} />
    </SelectTrigger>
    <SelectContent>
      {tools
        .filter((tool) => tool.id === value.tool || !taken.has(tool.id))
        .map((tool) => (
          <SelectItem key={tool.id} value={tool.id}>
            {tool.label}
          </SelectItem>
        ))}
    </SelectContent>
  </Select>
);

const RemoveTool: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <Button type="button" variant="ghost" size="icon" aria-label="Remove tool" onClick={onClick}>
    <X className="h-4 w-4" />
  </Button>
);

/** Rows of tool pickers, for the tools that may be used or may not. */
const ToolList: React.FC<{
  refs: CheckToolRef[];
  tools: Tool[];
  loading: boolean;
  label: string;
  addLabel: string;
  onChange: (refs: CheckToolRef[]) => void;
}> = ({ refs, tools, loading, label, addLabel, onChange }) => (
  <div className="space-y-2">
    <Label className="block text-sm">{label}</Label>
    {refs.map((ref, index) => (
      <div key={index} className="flex items-center gap-2">
        <ToolSelect
          value={ref}
          tools={tools}
          taken={pickedElsewhere(refs, index)}
          loading={loading}
          label={`${label} ${index + 1}`}
          onChange={(picked) => onChange(refs.map((entry, i) => (i === index ? picked : entry)))}
        />
        <RemoveTool onClick={() => onChange(refs.filter((_, i) => i !== index))} />
      </div>
    ))}
    {/* Gone once every tool has a row. */}
    {refs.length < tools.length && (
      <Button
        type="button"
        variant="outline"
        size="sm"
        icon={<Plus className="h-4 w-4" />}
        onClick={() => onChange([...refs, {}])}
      >
        {addLabel}
      </Button>
    )}
  </div>
);

type ValueRow = [string, string];

/** A tool's values as rows to edit, objects as their JSON. */
const rowsFrom = (args?: Record<string, unknown>): ValueRow[] =>
  Object.entries(args ?? {}).map(([key, value]) => [key, typeof value === "string" ? value : JSON.stringify(value)]);

// A row without a name is still being typed, so it is not a value yet.
const argsFrom = (rows: ValueRow[]): Record<string, string> => Object.fromEntries(rows.filter(([key]) => key.trim()));

/** The values a tool is called with, a name and a value to a row. */
const ValueRows: React.FC<{ rows: ValueRow[]; about?: string; onChange: (rows: ValueRow[]) => void }> = ({
  rows,
  about,
  onChange,
}) => {
  const of = about ? ` of ${about}` : "";
  return (
    <div className="space-y-2">
      <Label className="block text-sm">Values it is called with (optional)</Label>
      {rows.map(([key, value], index) => (
        <div key={index} className="flex items-center gap-2">
          <Input
            value={key}
            onChange={(event) =>
              onChange(rows.map((entry, i) => (i === index ? [event.target.value, entry[1]] : entry)))
            }
            placeholder="Name, e.g. region"
            aria-label={`Value ${index + 1} name${of}`}
          />
          <span className="text-muted-foreground">=</span>
          <Input
            value={value}
            onChange={(event) =>
              onChange(rows.map((entry, i) => (i === index ? [entry[0], event.target.value] : entry)))
            }
            placeholder="Value, e.g. united-kingdom"
            aria-label={`Value ${index + 1}${of}`}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Remove value${of}`}
            onClick={() => onChange(rows.filter((_, i) => i !== index))}
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
        onClick={() => onChange([...rows, ["", ""]])}
      >
        Add value
      </Button>
    </div>
  );
};

type ResultChoice = "anything" | "not_empty" | "contains";

/** What a tool's call should return. */
const ResultFields: React.FC<{ value: CheckToolRef; onChange: (patch: Partial<CheckToolRef>) => void }> = ({
  value,
  onChange,
}) => {
  const result: ResultChoice =
    value.result_contains != null ? "contains" : value.result_not_empty ? "not_empty" : "anything";
  return (
    <>
      <Field label="What it returns">
        <Select
          value={result}
          onValueChange={(choice) =>
            onChange({
              result_not_empty: choice === "not_empty",
              result_contains: choice === "contains" ? (value.result_contains ?? "") : null,
            })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="anything">Anything</SelectItem>
            <SelectItem value="not_empty">A result, not empty</SelectItem>
            <SelectItem value="contains">A result that contains…</SelectItem>
          </SelectContent>
        </Select>
      </Field>
      {result === "contains" && (
        <Field label="The result contains">
          <Input
            value={value.result_contains ?? ""}
            onChange={(event) => onChange({ result_contains: event.target.value })}
            placeholder="e.g. saved"
          />
        </Field>
      )}
    </>
  );
};

/** The tool a check is about, with its values and result; with Should, others can be added, any one of which counts. */
const ToolChoices: React.FC<{
  check: ScenarioCheck;
  update: Update;
  tools: Tool[];
  loading: boolean;
  /** The check's own tool's value rows as typed. */
  mainRows: ValueRow[];
  setMainRows: (rows: ValueRow[]) => void;
}> = ({ check, update, tools, loading, mainRows, setMainRows }) => {
  const should = check.expect === "should";
  const refs = toolRefs(check).map((ref, index) => (index === 0 ? { ...ref, rows: mainRows } : ref));
  // The first is the check's own tool and the rest its others, so removing the first moves the next up.
  // A Should not shows only its own; the others wait in case it turns back to Should.
  const save = (next: CheckToolRef[]) => {
    const [first, ...others] = next;
    const rows = first?.rows ?? rowsFrom(first?.args);
    setMainRows(rows);
    update({
      tool: first?.tool ?? null,
      tool_name: first?.tool_name ?? null,
      args: argsFrom(rows),
      result_not_empty: Boolean(first?.result_not_empty),
      result_contains: first?.result_contains ?? null,
      ...(should ? { tools: others } : {}),
    });
  };
  const change = (index: number, patch: Partial<CheckToolRef>) =>
    save(refs.map((ref, i) => (i === index ? { ...ref, ...patch } : ref)));
  return (
    <div className="space-y-2">
      <Label className="block text-sm">Tool</Label>
      {refs.map((ref, index) => (
        <React.Fragment key={index}>
          {index > 0 && <div className="px-3 text-xs text-muted-foreground">or</div>}
          {/* Each tool with what its own call should have. */}
          <div className="space-y-3 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <ToolSelect
                value={ref}
                tools={tools}
                taken={pickedElsewhere(refs, index)}
                loading={loading}
                label={index ? `Tool ${index + 1}` : "Tool"}
                onChange={(picked) => change(index, picked)}
              />
              {refs.length > 1 && <RemoveTool onClick={() => save(refs.filter((_, i) => i !== index))} />}
            </div>
            <ValueRows
              rows={ref.rows ?? rowsFrom(ref.args)}
              about={refs.length > 1 ? `tool ${index + 1}` : undefined}
              onChange={(rows) => change(index, { rows, args: argsFrom(rows) })}
            />
            {should && <ResultFields value={ref} onChange={(patch) => change(index, patch)} />}
          </div>
        </React.Fragment>
      ))}
      {/* Gone once every tool has a row. */}
      {should && refs.length < tools.length && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          icon={<Plus className="h-4 w-4" />}
          onClick={() => save([...refs, {}])}
        >
          Or another tool
        </Button>
      )}
    </div>
  );
};

// The fewest and the most calls belong together, so they share a row.
const CountFields: React.FC<{ check: ScenarioCheck; update: Update; label: string }> = ({ check, update, label }) => (
  <div className="space-y-2">
    <Label className="block text-sm">{label}</Label>
    <div className="grid w-full grid-cols-2 gap-3 sm:max-w-xs">
      <Field label="At least">
        <Input
          type="number"
          min={0}
          step={1}
          value={check.min_calls ?? ""}
          placeholder="Any"
          onChange={(event) => update({ min_calls: numberOrNull(event.target.value) })}
        />
      </Field>
      <Field label="At most">
        <Input
          type="number"
          min={0}
          step={1}
          value={check.max_calls ?? ""}
          placeholder="Any"
          onChange={(event) => update({ max_calls: numberOrNull(event.target.value) })}
        />
      </Field>
    </div>
  </div>
);

const EXPECTS = [
  {
    value: "should",
    label: "Should",
    icon: Check,
    on: "data-[state=on]:bg-green-100 data-[state=on]:text-green-800 dark:data-[state=on]:bg-green-950 dark:data-[state=on]:text-green-300",
  },
  {
    value: "should_not",
    label: "Should not",
    icon: Ban,
    on: "data-[state=on]:bg-red-100 data-[state=on]:text-red-800 dark:data-[state=on]:bg-red-950 dark:data-[state=on]:text-red-300",
  },
] as const;

/** Should or Should not, in the colors the list of checks marks them with. */
const ExpectField: React.FC<{ value: ScenarioCheck["expect"]; onChange: (expect: ScenarioCheck["expect"]) => void }> = ({
  value,
  onChange,
}) => (
  <ToggleGroupPrimitive.Root
    type="single"
    value={value}
    // Clicking the picked half again keeps it picked.
    onValueChange={(expect) => expect && onChange(expect as ScenarioCheck["expect"])}
    aria-label="Should or should not"
    className="grid grid-cols-2 gap-1 rounded-full border bg-background p-1"
  >
    {EXPECTS.map(({ value: expect, label, icon: Icon, on }) => (
      <ToggleGroupPrimitive.Item
        key={expect}
        value={expect}
        className={cn(
          "flex h-8 items-center justify-center gap-2 rounded-full text-sm font-medium text-muted-foreground transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=off]:hover:text-foreground",
          on,
        )}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        {label}
      </ToggleGroupPrimitive.Item>
    ))}
  </ToggleGroupPrimitive.Root>
);

const SwitchRow: React.FC<{ label: string; checked: boolean; onChange: (checked: boolean) => void }> = ({
  label,
  checked,
  onChange,
}) => (
  <div className="flex items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2">
    <div className="text-sm">{label}</div>
    <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
  </div>
);

const AgentField: React.FC<{ check: ScenarioCheck; update: Update; catalog: EvaluationCatalog }> = ({
  check,
  update,
  catalog,
}) => (
  <Field label="Agent">
    <Select
      value={check.agent ?? ANY}
      onValueChange={(id) => {
        const agent = catalog.agents.find((item) => item.id === id);
        // A tool the agent doesn't have could never be called by it.
        const has = (ref: CheckToolRef) => !agent || agent.tools.some((tool) => tool.id === ref.tool);
        update({
          agent: agent?.id ?? null,
          agent_name: agent?.label ?? null,
          ...(has({ tool: check.tool }) ? {} : { tool: null, tool_name: null }),
          tools: (check.tools ?? []).filter(has),
        });
      }}
    >
      <SelectTrigger>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ANY}>Any agent</SelectItem>
        {catalog.agents.map((agent) => (
          <SelectItem key={agent.id} value={agent.id}>
            {agent.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </Field>
);

const ToolFields: React.FC<{
  check: ScenarioCheck;
  update: Update;
  catalog: EvaluationCatalog;
  tools: Tool[];
  mainRows: ValueRow[];
  setMainRows: (rows: ValueRow[]) => void;
}> = ({ check, update, catalog, tools, mainRows, setMainRows }) => {
  const several = toolRefs(check).length > 1;
  return (
    <>
      <AgentField check={check} update={update} catalog={catalog} />
      <ToolChoices
        check={check}
        update={update}
        tools={tools}
        loading={catalog.loading}
        mainRows={mainRows}
        setMainRows={setMainRows}
      />
      {/* Over every tool of the check. */}
      {check.expect === "should" && (
        <>
          <SwitchRow
            label="It must succeed"
            checked={Boolean(check.succeeds)}
            onChange={(succeeds) => update({ succeeds })}
          />
          <CountFields
            check={check}
            update={update}
            label={several ? "How many calls in all (optional)" : "How many calls (optional)"}
          />
        </>
      )}
    </>
  );
};

const StepField: React.FC<{ check: ScenarioCheck; update: Update; catalog: EvaluationCatalog }> = ({
  check,
  update,
  catalog,
}) => {
  const types = [...new Set(catalog.actionNodes.map((step) => step.type).filter(Boolean))];
  const value = isStepType(check) ? `${TYPE_PREFIX}${check.step_type}` : check.step ?? "";
  return (
    <Field label="Step">
      <Select
        value={value}
        onValueChange={(picked) => {
          if (picked.startsWith(TYPE_PREFIX)) {
            const type = picked.slice(TYPE_PREFIX.length);
            update({ step: null, step_type: type, step_name: stepTypeLabel(type) });
            return;
          }
          const step = catalog.actionNodes.find((item) => item.id === picked);
          update({ step: step?.id ?? null, step_name: step?.label ?? null, step_type: null });
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
          {types.map((type) => (
            <SelectItem key={type} value={`${TYPE_PREFIX}${type}`}>
              Any step of type "{stepTypeLabel(type)}"
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
};

const RouteFields: React.FC<{ check: ScenarioCheck; update: Update; catalog: EvaluationCatalog }> = ({
  check,
  update,
  catalog,
}) => {
  const router = catalog.routers.find((item) => item.id === check.router);
  // Any router offers every router's branches, once each.
  const branches = router
    ? router.branches.map((branch) => ({ ...branch, from: router.label }))
    : catalog.routers.flatMap((item) => item.branches.map((branch) => ({ ...branch, from: item.label })));
  const key = (branch: { value: string; label?: string | null }) => `${branch.value}|${branch.label ?? ""}`;
  const unique = [...new Map(branches.map((branch) => [key(branch), branch])).values()];
  const current = unique.find((branch) => branch.value === check.branch && (branch.label ?? null) === (check.branch_label ?? null))
    ?? unique.find((branch) => branch.value === check.branch);
  return (
    <>
      <Field label="Router">
        <Select
          value={check.router ?? ANY}
          onValueChange={(id) => {
            const picked = catalog.routers.find((item) => item.id === id);
            update({ router: picked?.id ?? null, router_name: picked?.label ?? null, branch: null, branch_label: null });
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder={catalog.loading ? "Loading routers…" : "Pick a router"} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any router</SelectItem>
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
          value={current ? key(current) : ""}
          onValueChange={(picked) => {
            const branch = unique.find((item) => key(item) === picked);
            update({ branch: branch?.value ?? null, branch_label: branch?.label ?? branch?.value ?? null });
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder={check.branch_label ?? check.branch ?? "Pick a branch"} />
          </SelectTrigger>
          <SelectContent>
            {unique.map((branch) => (
              <SelectItem key={key(branch)} value={key(branch)}>
                {branch.label ?? branch.value}
                {branch.destination ? ` → ${branch.destination}` : ""}
                {router ? "" : ` (${branch.from})`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
    </>
  );
};

/** The chosen conversations, or the picked turn, from the dataset's conversations listed in the form. */
const TargetField: React.FC<{
  check: ScenarioCheck;
  conversations: CheckConversation[];
  ready: boolean;
  failed: boolean;
  update: Update;
}> = ({ check, conversations, ready, failed, update }) => {
  if (failed) {
    return <p className="text-xs text-destructive">The dataset's conversations could not be loaded. Try again under Dataset.</p>;
  }
  if (!ready) return <p className="text-xs text-muted-foreground">Loading the dataset's conversations…</p>;
  if (check.level === "conversation") {
    return (
      <ConversationChecklist
        mode="conversations"
        conversations={conversations}
        chosen={chosenConversations(check)}
        // Any the dataset lost stay chosen until they are removed.
        onChoose={(keys) => update({ conversation_ids: keys, conversation_id: null })}
      />
    );
  }
  const found = findCheckTurn(check, conversations);
  return (
    <div className="space-y-1.5">
      <ConversationChecklist
        mode="turn"
        conversations={conversations}
        pickedTurn={"problem" in found ? null : found.turn.caseId}
        onPickTurn={(conversation, turn) => update(targetFields({ level: "turn", conversation, turn }))}
      />
      {"problem" in found && (check.case_id || check.turn_index != null) && (
        <p className="text-xs text-amber-700 dark:text-amber-400">{found.problem}</p>
      )}
    </div>
  );
};

export const CheckForm: React.FC<CheckFormProps> = ({
  check,
  onChange,
  onDone,
  onRemove,
  conversations,
  conversationsReady = true,
  conversationsFailed = false,
  reveal = 0,
  catalog,
  onProblem,
  providers = [],
}) => {
  const update: Update = (patch) => onChange({ ...check, ...patch });
  const missing = checkMissing(check);
  // Chosen conversations and one turn need the dataset's conversations to pick from.
  const noConversations = conversationsReady && conversations.length === 0;
  const agentTools = check.agent
    ? catalog.agents.find((agent) => agent.id === check.agent)?.tools ?? []
    : catalog.agents.flatMap((agent) => agent.tools);
  const tools = [...new Map(agentTools.map((tool) => [tool.id, tool])).values()];
  const stateKeys = [...new Set(catalog.stateKeys.map((item) => item.key))];
  // Rows stay as typed, so an empty or repeated name doesn't merge two rows while editing.
  const [args, setArgRows] = React.useState<ValueRow[]>(() => rowsFrom(check.args));
  // The check's own tool's rows, and with Should each other tool's.
  const rowSets =
    check.kind !== "tool_called"
      ? []
      : [args, ...(check.expect === "should" ? (check.tools ?? []).map((ref) => ref.rows ?? rowsFrom(ref.args)) : [])];
  const repeats = (rows: ValueRow[]) => {
    const names = rows.map(([key]) => key.trim());
    return names.some((key, index) => key && names.indexOf(key) !== index);
  };
  const argProblem = rowSets.some((rows) => rows.some(([key, value]) => !key.trim() && value.trim()))
    ? "Name each value."
    : rowSets.some(repeats)
      ? "Give each value a different name."
      : null;
  const problem = missing ?? argProblem;

  React.useEffect(() => {
    onProblem?.(argProblem);
    return () => onProblem?.(null);
  }, [argProblem, onProblem]);

  // Each place keeps its pick, so choosing it again gives it back.
  const picks = React.useRef<Partial<Record<CheckLevel, Partial<ScenarioCheck>>>>({});
  const setLevel = (level: CheckLevel) => {
    if (level === check.level) return;
    picks.current[check.level] = targetOf(check);
    update(retarget(check, level, conversations, picks.current[level]));
  };
  // Should not means never, which covers every turn; going back to Should gives How often back.
  const whenBeforeNever = React.useRef<ScenarioCheck["when"] | null>(null);
  const setExpect = (expect: ScenarioCheck["expect"]) => {
    if (expect === check.expect) return;
    // These are graded on every turn either way.
    if (EVERY_TURN_KINDS.has(check.kind)) {
      update({ expect });
      return;
    }
    if (expect === "should_not") {
      whenBeforeNever.current = check.when;
      update({ expect, when: "anywhere" });
      return;
    }
    update({ expect, when: whenBeforeNever.current ?? check.when });
    whenBeforeNever.current = null;
  };

  // How often it held before a kind graded on every turn was picked, given back after.
  const whenBeforeEveryTurn = React.useRef<ScenarioCheck["when"] | null>(null);
  const setKind = (kind: CheckKind) => {
    // Each kind reads match its own way: words are mentioned or exact, the expected reply also by meaning.
    const match: CheckMatch | null =
      kind === "reply_matches" ? check.match ?? "meaning" : kind === "reply_mentions" && check.match === "exact" ? "exact" : null;
    const readable = kind === "reply_meets" ? CONTEXTS : kind === "reply_grounded" ? GROUNDS : [];
    const context = readable.some((option) => option.value === check.context) ? check.context : null;
    const source = { match, context, context_path: context === "run_value" ? check.context_path : null };
    const everyTurn = EVERY_TURN_KINDS.has(kind);
    const wasEveryTurn = EVERY_TURN_KINDS.has(check.kind);
    let when = check.when;
    if (everyTurn && !wasEveryTurn) {
      whenBeforeEveryTurn.current = check.when;
      when = "every_turn";
    } else if (!everyTurn && wasEveryTurn) {
      when = whenBeforeEveryTurn.current ?? "anywhere";
      whenBeforeEveryTurn.current = null;
    }
    update({ kind, ...source, when });
  };

  // An opened form takes focus and comes into view, also each time "Show me" points at it.
  const formRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    formRef.current?.scrollIntoView({ block: "nearest", behavior: reveal ? "smooth" : "auto" });
    formRef.current?.focus({ preventScroll: true });
  }, [reveal]);

  const showsHowOften = check.level !== "turn" && check.expect === "should" && !EVERY_TURN_KINDS.has(check.kind);
  // Only these tools holds over the conversation's calls together, or turn by turn.
  const together = check.kind === "only_tools" ? "Across the whole conversation" : "At least once";

  return (
    <div
      ref={formRef}
      tabIndex={-1}
      role="group"
      aria-label="Edit check"
      // Text fields have no fill of their own, so they get the white the selects have.
      className="space-y-4 rounded-lg border border-primary/40 bg-primary/5 p-4 outline-none [&_input]:bg-background [&_textarea]:bg-background"
    >
      <CheckKindPicker value={check.kind} onChange={setKind} />

      <ExpectField value={check.expect} onChange={setExpect} />

      <Field label="Applies to">
        <Select value={check.level} onValueChange={(level) => setLevel(level as CheckLevel)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CHECK_LEVELS.map((level) => (
              <SelectItem
                key={level.value}
                value={level.value}
                disabled={level.value !== "every_conversation" && noConversations}
              >
                {level.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      {noConversations && (
        <p className="-mt-2 text-xs text-muted-foreground">
          The dataset has no conversations yet, so this check applies to all of them.
        </p>
      )}

      {check.level !== "every_conversation" && (
        <TargetField
          check={check}
          conversations={conversations}
          ready={conversationsReady}
          failed={conversationsFailed}
          update={update}
        />
      )}

      {showsHowOften && (
        <Field label="How often">
          <Select value={check.when} onValueChange={(when) => update({ when: when as ScenarioCheck["when"] })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="anywhere">{together}</SelectItem>
              <SelectItem value="every_turn">On every turn</SelectItem>
            </SelectContent>
          </Select>
        </Field>
      )}

      {check.kind === "reply_mentions" && (
        <>
          <Field label="How">
            <Select
              value={check.match === "exact" ? "exact" : "contains"}
              onValueChange={(match) => update({ match: match === "exact" ? "exact" : null })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MENTION_MODES.map((mode) => (
                  <SelectItem key={mode.value} value={mode.value}>
                    {mode.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={check.match === "exact" ? "The whole reply" : "Words to look for"}>
            <Input
              value={check.text ?? ""}
              onChange={(event) => update({ text: event.target.value })}
              placeholder="e.g. RingGo"
            />
          </Field>
        </>
      )}

      {check.kind === "reply_matches" && (
        <>
          <Field label="How closely">
            <Select value={check.match ?? ""} onValueChange={(match) => update({ match: match as CheckMatch })}>
              <SelectTrigger>
                <SelectValue placeholder="Pick how closely" />
              </SelectTrigger>
              <SelectContent>
                {MATCH_MODES.map((mode) => (
                  <SelectItem key={mode.value} value={mode.value}>
                    {mode.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          {check.match === "meaning" && (
            <>
              <ExtraInstructionField check={check} update={update} />
              <GradingFields check={check} update={update} providers={providers} />
            </>
          )}
        </>
      )}

      {check.kind === "reply_meets" && (
        <>
          <Field label="Rule, in plain words">
            <Textarea
              value={check.rubric ?? ""}
              onChange={(event) => update({ rubric: event.target.value })}
              placeholder="e.g. Ask for the licence plate before creating a ticket"
              size="hint"
            />
          </Field>
          {isPerTurn(check) && (
            <SourceFields check={check} update={update} label="The AI grader also reads" options={CONTEXTS} none="Only the reply" />
          )}
          <GradingFields check={check} update={update} providers={providers} />
        </>
      )}

      {check.kind === "reply_grounded" && (
        <>
          <SourceFields check={check} update={update} label="Sticks to" options={GROUNDS} />
          <GraderFields check={check} update={update} />
          {!check.grader && <ExtraInstructionField check={check} update={update} />}
          <GradingFields check={check} update={update} providers={providers} />
        </>
      )}

      {check.kind === "tool_called" && (
        <ToolFields
          check={check}
          update={update}
          catalog={catalog}
          tools={tools}
          mainRows={args}
          setMainRows={setArgRows}
        />
      )}

      {check.kind === "only_tools" && (
        <>
          <AgentField check={check} update={update} catalog={catalog} />
          <ToolList
            refs={check.tools ?? []}
            tools={tools}
            loading={catalog.loading}
            label={check.expect === "should" ? "The tools it may use (none means no tool at all)" : "The tools it should not use"}
            addLabel="Add a tool"
            onChange={(refs) => update({ tools: refs })}
          />
          {check.expect === "should" && (
            <>
              <CountFields check={check} update={update} label="How many calls of these tools (optional)" />
              <SwitchRow
                label="Count only calls that succeeded"
                checked={Boolean(check.succeeds)}
                onChange={(succeeds) => update({ succeeds })}
              />
            </>
          )}
        </>
      )}

      {check.kind === "step_runs" && <StepField check={check} update={update} catalog={catalog} />}

      {check.kind === "route_taken" && <RouteFields check={check} update={update} catalog={catalog} />}

      {check.kind === "state_equals" && (
        <>
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
        </>
      )}

      {check.kind === "value_equals" && (
        <>
          <Field
            label="Where the value is"
            hint="A dotted path into the turn: outputs (what the workflow returned), inputs, or trace.nodes, trace.session and trace.output."
          >
            <Input
              value={check.path ?? ""}
              onChange={(event) => update({ path: event.target.value })}
              placeholder="e.g. outputs.status"
            />
          </Field>
          <Field label="Should be">
            <Input
              value={check.value ?? ""}
              onChange={(event) => update({ value: event.target.value })}
              placeholder="Empty: the turn's expected reply"
            />
          </Field>
        </>
      )}

      {/* What the check says, once it is complete; until then, what it still needs. */}
      <div className="flex flex-col gap-3 border-t pt-3 sm:flex-row sm:items-center sm:justify-between">
        <p className={cn("min-w-0 text-sm sm:flex-1", problem && "text-muted-foreground")}>{problem ?? checkSentence(check)}</p>
        <div className="flex shrink-0 justify-end gap-2">
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
