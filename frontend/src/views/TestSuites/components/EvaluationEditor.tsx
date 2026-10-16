import React, { useEffect, useId, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { JsonInput } from "@/components/JsonInput";
import { Switch } from "@/components/switch";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/collapsible";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import toast from "react-hot-toast";
import { cn } from "@/helpers/utils";
import { extractErrorMessage } from "@/helpers/apiError";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type { ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import { newEvaluationDefaults } from "../helpers/evaluationForm";
import {
  methodDefaults,
  methodSettingsComplete,
  remapToolRuleNames,
  type MethodSettingsValue,
} from "../helpers/methodSettings";
import { useDatasetCases, useEvaluationCatalog, useRuleConversations } from "../hooks/useEvaluationData";
import {
  CHECKS_TECHNIQUE,
  type CheckConversation,
  type CheckTarget,
  checkConversations,
  checkCounts,
  checkMissing,
  newCheck,
} from "../helpers/checks";
import { turnLabel } from "../helpers/datasetConversations";
import type { EvaluationWizardData } from "./EvaluationWizard";
import { WorkflowVersionPicker } from "./WorkflowVersionPicker";
import { ChecksList } from "./ChecksList";
import { MethodPicker, MethodSettings } from "./LegacyMethodsPanel";

export interface EvaluationEditorProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: EvaluationWizardData, options?: { run?: boolean }) => Promise<void>;
  suites: TestSuite[];
  workflows: WorkflowMinimal[];
  providers: LLMProviderMinimal[];
  initialData?: Partial<EvaluationWizardData>;
  mode?: "create" | "edit";
  /** Pins the workflow, e.g. when creating from a workflow's page. */
  lockedWorkflowId?: string;
}

const Section: React.FC<{ title: string; description?: string; action?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  description,
  action,
  children,
}) => (
  <section className="space-y-3">
    <div className="flex items-end justify-between gap-3">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
    {children}
  </section>
);

export const EvaluationEditor: React.FC<EvaluationEditorProps> = ({
  isOpen,
  onOpenChange,
  onSubmit,
  suites,
  workflows,
  providers,
  initialData,
  mode = "create",
  lockedWorkflowId,
}) => {
  const defaults = newEvaluationDefaults(lockedWorkflowId);
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [suiteId, setSuiteId] = useState(initialData?.suiteId ?? "none");
  const [workflowId, setWorkflowId] = useState(lockedWorkflowId ?? initialData?.workflowId ?? defaults.workflowId);
  const [inputMetadataText, setInputMetadataText] = useState(initialData?.inputMetadataText ?? "{}");
  const [isMetadataValid, setIsMetadataValid] = useState(true);
  const [useMemory, setUseMemory] = useState(initialData?.useMemory ?? defaults.useMemory);
  const [checks, setChecks] = useState<ScenarioCheck[]>(initialData?.checks ?? []);
  const [checksProviderId, setChecksProviderId] = useState(initialData?.checksProviderId ?? "");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formProblem, setFormProblem] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<string[]>(
    (initialData?.metrics ?? []).filter((metric) => metric !== CHECKS_TECHNIQUE),
  );
  const [methods, setMethods] = useState<MethodSettingsValue>(() => methodDefaults(initialData, providers));
  const [advancedOpen, setAdvancedOpen] = useState(metrics.length > 0);
  const [workflowPickerOpen, setWorkflowPickerOpen] = useState(false);
  const [submitting, setSubmitting] = useState<"save" | "run" | null>(null);

  const selectedSuite = suites.find((suite) => suite.id === suiteId);
  const effectiveWorkflowId = workflowId && workflowId !== "none" ? workflowId : selectedSuite?.workflow_id ?? undefined;
  const missingWorkflow = !effectiveWorkflowId;
  const catalog = useEvaluationCatalog(effectiveWorkflowId, isOpen);
  const { cases, ready: casesReady } = useDatasetCases(suiteId, isOpen);
  const conversations = useMemo(() => checkConversations(cases), [cases]);
  const ruleConversations = useRuleConversations(cases);
  const fieldId = useId();

  // Older evaluations may name tools and agents; they become ids once the catalog loads, as in the wizard.
  useEffect(() => {
    setMethods((previous) => {
      const toolRules = remapToolRuleNames(previous.toolRules, catalog.agents);
      return toolRules === previous.toolRules ? previous : { ...previous, toolRules };
    });
  }, [catalog.agents]);
  const workflow = workflows.find((item) => item.id === effectiveWorkflowId);
  const usesJudge = checks.some((check) => check.kind === "reply_meets");
  // Providers often load after the editor opens, so the first one is the default at use time.
  const graderId = checksProviderId || providers[0]?.id || "";

  const addCheck = (target?: CheckTarget) => {
    const check = newCheck(target);
    setChecks((previous) => [...previous, check]);
    setEditingId(check.id);
  };

  const blocker = (): string | null => {
    if (!name.trim()) return "Add a name.";
    if (suiteId === "none") return "Pick a dataset.";
    if (missingWorkflow) return "Pick a workflow.";
    if (!isMetadataValid) return "Fix the starting inputs.";
    if (checks.length === 0 && metrics.length === 0) return "Add at least one check.";
    const incomplete = checks.find((check) => checkMissing(check));
    if (incomplete) return `A check is not complete: ${checkMissing(incomplete)}`;
    if (formProblem) return `A check is not complete: ${formProblem}`;
    if (usesJudge && !graderId) return "Pick an AI grader for the rules in plain words.";
    if (!methodSettingsComplete(metrics, methods, { agents: catalog.agents, routers: catalog.routers })) {
      return "Finish the settings of the older methods.";
    }
    return null;
  };
  const blocked = blocker();

  const reset = () => {
    setName("");
    setDescription("");
    setSuiteId("none");
    setWorkflowId(defaults.workflowId);
    setInputMetadataText("{}");
    setIsMetadataValid(true);
    setUseMemory(defaults.useMemory);
    setChecks([]);
    setChecksProviderId("");
    setEditingId(null);
    setMetrics([]);
    setMethods(methodDefaults(undefined, providers));
    setAdvancedOpen(false);
  };

  // A new evaluation starts empty after the dialog closes; a failed save keeps what was entered.
  const [wasOpen, setWasOpen] = useState(isOpen);
  if (wasOpen !== isOpen) {
    setWasOpen(isOpen);
    if (!isOpen && mode === "create") reset();
  }

  const submit = async (run: boolean) => {
    setSubmitting(run ? "run" : "save");
    try {
      await onSubmit(
        {
          name,
          description,
          suiteId,
          // Nothing picked means the dataset's workflow, which the picker already shows.
          workflowId: workflowId || effectiveWorkflowId || "",
          metrics: checks.length ? [...metrics, CHECKS_TECHNIQUE] : metrics,
          inputMetadataText,
          useMemory,
          ...methods,
          checks,
          checksProviderId: usesJudge ? graderId : "",
        },
        { run },
      );
    } catch (error) {
      toast.error(extractErrorMessage(error, "Could not save the evaluation."));
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[1180px] p-0 overflow-hidden">
        <div className="flex h-[90vh] flex-col">
          <DialogHeader className="shrink-0 border-b px-6 pb-4 pt-6">
            <DialogTitle>{mode === "create" ? "New evaluation" : "Edit evaluation"}</DialogTitle>
            <DialogDescription>
              Pick a workflow and a dataset, then say what should and should not happen in its conversations.
            </DialogDescription>
          </DialogHeader>

          <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="min-h-0 space-y-8 overflow-y-auto px-6 py-5">
              <Section title="Basics">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor={`${fieldId}-name`} className="text-xs">Name *</Label>
                    <Input
                      id={`${fieldId}-name`}
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder="e.g. Parker refunds"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor={`${fieldId}-dataset`} className="text-xs">Dataset *</Label>
                    <Select value={suiteId} onValueChange={setSuiteId}>
                      <SelectTrigger id={`${fieldId}-dataset`}>
                        <SelectValue placeholder="Pick a dataset" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Pick a dataset</SelectItem>
                        {suites
                          .filter((suite): suite is TestSuite & { id: string } => Boolean(suite.id))
                          .map((suite) => (
                            <SelectItem key={suite.id} value={suite.id}>
                              {suite.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`${fieldId}-description`} className="text-xs">Description</Label>
                  <Textarea
                    id={`${fieldId}-description`}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="What this evaluation tests"
                    size="compact"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <Label className="text-xs">Workflow *</Label>
                    {lockedWorkflowId ? (
                      <div className="rounded-md border bg-muted px-3 py-2 text-sm">{workflow?.name ?? "This workflow"}</div>
                    ) : (
                      <Popover open={workflowPickerOpen} onOpenChange={setWorkflowPickerOpen}>
                        <PopoverTrigger asChild>
                          <Button variant="outline" className="w-full justify-between rounded-md font-normal">
                            <span className="truncate">
                              {workflow ? `${workflow.name} · v${workflow.version}` : "Pick a workflow"}
                            </span>
                            <ChevronDown className="h-4 w-4 opacity-60" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="max-h-[360px] w-[420px] overflow-y-auto p-2" align="start">
                          <WorkflowVersionPicker
                            workflows={workflows}
                            selectedWorkflowId={workflowId}
                            onSelect={(id) => {
                              setWorkflowId(id);
                              setWorkflowPickerOpen(false);
                            }}
                          />
                        </PopoverContent>
                      </Popover>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                    <div>
                      <div className="text-sm font-medium">Replay with memory</div>
                      <div className="text-xs text-muted-foreground">Later turns see earlier ones.</div>
                    </div>
                    <Switch checked={useMemory} onCheckedChange={setUseMemory} aria-label="Replay with memory" />
                  </div>
                </div>
                <Collapsible>
                  <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
                    <ChevronRight className="h-3.5 w-3.5" />
                    Starting inputs
                  </CollapsibleTrigger>
                  <CollapsibleContent className="pt-2">
                    <JsonInput
                      value={inputMetadataText}
                      onChange={setInputMetadataText}
                      onValidChange={setIsMetadataValid}
                      label="Inputs every conversation starts with (JSON)"
                      description="For example a region. A turn can still set its own."
                      placeholder="{}"
                      rows={5}
                      allowEmpty
                    />
                  </CollapsibleContent>
                </Collapsible>
              </Section>

              <Section
                title={`Checks${checks.length ? ` (${checks.length})` : ""}`}
                description="What should or should not happen. Add one for a single conversation or turn from the list on the right."
                action={
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    icon={<Plus className="h-4 w-4" />}
                    onClick={() => addCheck()}
                  >
                    Add check
                  </Button>
                }
              >
                {checks.length === 0 ? (
                  <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                    No checks yet. Start with one that holds for every conversation, such as a word the reply should never use.
                  </div>
                ) : (
                  <ChecksList
                    checks={checks}
                    conversations={conversations}
                    conversationsReady={casesReady || suiteId === "none"}
                    catalog={catalog}
                    onChange={setChecks}
                    editingId={editingId}
                    onEdit={setEditingId}
                    onFormProblem={setFormProblem}
                  />
                )}
                {usesJudge && (
                  <div className="space-y-1">
                    <Label htmlFor={`${fieldId}-grader`} className="text-xs">AI grader for the rules in plain words</Label>
                    <Select value={graderId} onValueChange={setChecksProviderId}>
                      <SelectTrigger id={`${fieldId}-grader`} className="sm:w-[360px]">
                        <SelectValue placeholder="Pick a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </Section>

              <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
                <CollapsibleTrigger className="flex items-center gap-1.5 text-sm font-semibold">
                  {advancedOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  Advanced: older methods{metrics.length ? ` (${metrics.length})` : ""}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 pt-3">
                  <p className="text-xs text-muted-foreground">
                    The methods evaluations used before checks. They still work and run alongside the checks.
                  </p>
                  <MethodPicker metrics={metrics} onChange={setMetrics} />
                  <MethodSettings
                    metrics={metrics}
                    settings={methods}
                    onChange={(patch) => setMethods((previous) => ({ ...previous, ...patch }))}
                    providers={providers}
                    catalog={catalog}
                    conversations={ruleConversations}
                    hasWorkflow={!missingWorkflow}
                  />
                </CollapsibleContent>
              </Collapsible>
            </div>

            <aside className="hidden min-h-0 overflow-y-auto border-l bg-muted/30 px-4 py-5 lg:block">
              <ConversationsColumn
                conversations={conversations}
                checks={checks}
                datasetPicked={suiteId !== "none"}
                onAdd={addCheck}
              />
            </aside>
          </div>

          <DialogFooter className="shrink-0 items-center border-t px-6 py-4 sm:justify-between">
            <p className="text-sm text-muted-foreground">{blocked}</p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button variant="outline" onClick={() => submit(false)} disabled={Boolean(blocked) || submitting !== null}>
                {submitting === "save" ? "Saving…" : mode === "create" ? "Create" : "Save"}
              </Button>
              <Button onClick={() => submit(true)} disabled={Boolean(blocked) || submitting !== null}>
                {submitting === "run" ? "Starting…" : mode === "create" ? "Create and run" : "Save and run"}
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const countLabel = (count: number): string => (count ? `${count} check${count === 1 ? "" : "s"}` : "");

const ConversationsColumn: React.FC<{
  conversations: CheckConversation[];
  checks: ScenarioCheck[];
  datasetPicked: boolean;
  onAdd: (target: CheckTarget) => void;
}> = ({ conversations, checks, datasetPicked, onAdd }) => {
  const [open, setOpen] = useState<string | null>(null);
  // Counted once per change, not once per turn on every keystroke.
  const counts = useMemo(() => checkCounts(checks, conversations), [checks, conversations]);

  if (!datasetPicked) {
    return <p className="text-sm text-muted-foreground">Pick a dataset to see its conversations.</p>;
  }
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">Conversations</h3>
        <p className="text-xs text-muted-foreground">Add a check for one conversation, or open it to pick a turn.</p>
      </div>
      {conversations.map((conversation) => {
        const expanded = open === conversation.key;
        const own = counts.byConversation.get(conversation.key) ?? 0;
        const inTurns = conversation.turns.reduce((total, turn) => total + (counts.byTurn.get(turn.caseId) ?? 0), 0);
        return (
          <div key={conversation.key} className="rounded-lg border bg-background">
            <div className="flex items-start gap-2 px-3 py-2.5">
              <button
                type="button"
                className="flex min-w-0 flex-1 items-start gap-1.5 text-left"
                onClick={() => setOpen(expanded ? null : conversation.key)}
              >
                {expanded ? (
                  <ChevronDown className="mt-0.5 h-4 w-4 shrink-0" />
                ) : (
                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{conversation.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {conversation.turns.length} turn{conversation.turns.length === 1 ? "" : "s"}
                    {own + inTurns ? ` · ${countLabel(own + inTurns)}` : ""}
                  </span>
                </span>
              </button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                aria-label="Add a check for this conversation"
                onClick={() => onAdd({ level: "conversation", conversation })}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {expanded && (
              <div className="space-y-1 border-t px-3 py-2">
                {conversation.turns.map((turn) => {
                  const count = counts.byTurn.get(turn.caseId) ?? 0;
                  return (
                    <div key={turn.caseId} className="flex items-start gap-2 py-1">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium">
                          {turnLabel(turn.position)}
                          {count ? <span className="text-muted-foreground"> · {countLabel(count)}</span> : null}
                        </div>
                        <div className={cn("text-xs text-muted-foreground", "line-clamp-2")}>{turn.message}</div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        aria-label={`Add a check for ${turnLabel(turn.position)}`}
                        onClick={() => onAdd({ level: "turn", conversation, turn })}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default EvaluationEditor;
