import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronLeft, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { JsonInput } from "@/components/JsonInput";
import { Switch } from "@/components/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import toast from "react-hot-toast";
import { cn } from "@/helpers/utils";
import { extractErrorMessage } from "@/helpers/apiError";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type { ScenarioCheck } from "@/interfaces/testEvaluation.interface";
import { newEvaluationDefaults, type EvaluationFormData } from "../helpers/evaluationForm";
import { methodDefaults, remapToolRuleNames, type MethodSettingsValue } from "../helpers/methodSettings";
import { groupWorkflowVersions } from "../helpers/workflowVersions";
import { useDatasetCases, useEvaluationCatalog } from "../hooks/useEvaluationData";
import { useCategories } from "../hooks/useCategories";
import {
  CHECKS_TECHNIQUE,
  checkConversations,
  checkMissing,
  isAiGraded,
  leftOutNote,
  newCheck,
} from "../helpers/checks";
import { CategoryPicker } from "./CategoryPicker";
import { ChecksList } from "./ChecksList";
import { LeftOutNote } from "./LeftOutNote";
import { RunAgainstVersionDialog } from "./RunAgainstVersionDialog";

export interface EvaluationEditorProps {
  onSubmit: (data: EvaluationFormData, options?: { run?: boolean; targetWorkflowId?: string }) => Promise<void>;
  onCancel: () => void;
  suites: TestSuite[];
  workflows: WorkflowMinimal[];
  providers: LLMProviderMinimal[];
  initialData?: Partial<EvaluationFormData>;
  mode?: "create" | "edit";
  /** Pins the workflow, e.g. when creating from a workflow's page. */
  lockedWorkflowId?: string;
  /** The version Save and run preselects, such as the one open in the builder. */
  runVersionId?: string;
}

type Place = "name" | "workflow" | "dataset" | "checks" | "grader" | "inputs";

const hasInputs = (text: string): boolean => Boolean(text.trim()) && text.trim() !== "{}";

// One field per row, as in the other forms.
const Field: React.FC<{
  id?: string;
  label: string;
  required?: boolean;
  hint?: React.ReactNode;
  children: React.ReactNode;
}> = ({ id, label, required, hint, children }) => (
  <div className="space-y-1.5">
    <Label htmlFor={id} className="text-sm font-medium">
      {label}
      {required && <span className="ml-0.5 text-destructive">*</span>}
    </Label>
    {children}
    {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
  </div>
);

// A titled part of the form, laid out like the knowledge base form.
const Section: React.FC<{
  title: React.ReactNode;
  description: React.ReactNode;
  sectionRef?: React.Ref<HTMLElement>;
  children?: React.ReactNode;
}> = ({ title, description, sectionRef, children }) => (
  <section ref={sectionRef} className="grid scroll-mt-6 grid-cols-1 gap-6 p-6 md:grid-cols-3">
    <div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
    {children && <div className="min-w-0 space-y-5 md:col-span-2">{children}</div>}
  </section>
);

/** Creates or edits an evaluation as a page: its workflow and dataset, its checks, and how it plays. */
export const EvaluationEditor: React.FC<EvaluationEditorProps> = ({
  onSubmit,
  onCancel,
  suites,
  workflows,
  providers,
  initialData,
  mode = "create",
  lockedWorkflowId,
  runVersionId,
}) => {
  const defaults = newEvaluationDefaults(lockedWorkflowId);
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [category, setCategory] = useState(initialData?.category ?? "");
  // A new evaluation's category follows its dataset until one is picked, "No category" included.
  const [categoryPicked, setCategoryPicked] = useState(mode === "edit" || Boolean(initialData?.category));
  const categories = useCategories();
  const [suiteId, setSuiteId] = useState(initialData?.suiteId ?? "none");
  const [workflowId, setWorkflowId] = useState(lockedWorkflowId ?? initialData?.workflowId ?? defaults.workflowId);
  const [inputMetadataText, setInputMetadataText] = useState(initialData?.inputMetadataText ?? "{}");
  const [isMetadataValid, setIsMetadataValid] = useState(true);
  const [useMemory, setUseMemory] = useState(initialData?.useMemory ?? defaults.useMemory);
  const [checks, setChecks] = useState<ScenarioCheck[]>(initialData?.checks ?? []);
  const [checksProviderId, setChecksProviderId] = useState(initialData?.checksProviderId ?? "");
  const [editingId, setEditingId] = useState<string | null>(null);
  // The check just added, shown above Add check until its form first closes.
  const [newId, setNewId] = useState<string | null>(null);
  const [formProblem, setFormProblem] = useState<string | null>(null);
  // Older methods are made into checks when the evaluation loads; any still here are kept as they are.
  const [metrics] = useState<string[]>(
    (initialData?.metrics ?? []).filter((metric) => metric !== CHECKS_TECHNIQUE),
  );
  const [methods, setMethods] = useState<MethodSettingsValue>(() => methodDefaults(initialData, providers));
  const olderMethods = initialData?.checksOlderMethods ?? null;
  const leftOut = leftOutNote(olderMethods);
  // Most evaluations start every conversation the same way, so the inputs stay folded unless some are set.
  const [inputsOpen, setInputsOpen] = useState(() => hasInputs(initialData?.inputMetadataText ?? ""));
  const [submitting, setSubmitting] = useState<"save" | "run" | null>(null);
  const [pickingVersion, setPickingVersion] = useState(false);
  // Bumped when saving points at a check, so its open form comes into view again.
  const [reveal, setReveal] = useState(0);

  const selectedSuite = suites.find((suite) => suite.id === suiteId);
  // A legacy evaluation without its own workflow runs its dataset's.
  const ownWorkflowId = workflowId && workflowId !== "none" ? workflowId : "";
  const effectiveWorkflowId = ownWorkflowId || selectedSuite?.workflow_id || undefined;
  const missingWorkflow = !effectiveWorkflowId;
  const datasetPicked = suiteId !== "none";
  // Checks are written for the workflow's steps and the dataset's conversations.
  const checksReady = !missingWorkflow && datasetPicked;
  const { cases, ready: casesReady, failed: casesFailed, retry: retryCases } = useDatasetCases(suiteId, true);
  const conversations = useMemo(() => checkConversations(cases), [cases]);
  const fieldId = useId();

  const nameRef = useRef<HTMLInputElement>(null);
  const workflowRef = useRef<HTMLButtonElement>(null);
  const datasetRef = useRef<HTMLButtonElement>(null);
  const checksRef = useRef<HTMLElement>(null);
  const graderRef = useRef<HTMLButtonElement>(null);
  const inputsRef = useRef<HTMLDivElement>(null);

  const groups = useMemo(() => groupWorkflowVersions(workflows), [workflows]);
  const workflow = workflows.find((item) => item.id === effectiveWorkflowId);
  const group = groups.find((item) => item.versions.some((version) => version.id === effectiveWorkflowId));
  // Runs start from the agent's live version, so its tools and steps are the ones to pick from.
  const liveVersion = group?.versions.find((version) => version.id === group.activeVersionId) ?? workflow;
  // In the builder, the version open there instead, when it is one of this workflow's.
  const runVersion = runVersionId ? group?.versions.find((version) => version.id === runVersionId) : undefined;
  const catalog = useEvaluationCatalog(runVersion?.id ?? liveVersion?.id ?? effectiveWorkflowId, true);

  // Older evaluations may name tools and agents; they become ids once the catalog loads.
  useEffect(() => {
    setMethods((previous) => {
      const toolRules = remapToolRuleNames(previous.toolRules, catalog.agents);
      return toolRules === previous.toolRules ? previous : { ...previous, toolRules };
    });
  }, [catalog.agents]);
  const usesJudge = checks.some(isAiGraded);
  // Providers often load after the editor opens, so the first one is the default at use time.
  const graderId = checksProviderId || providers[0]?.id || "";

  const addCheck = () => {
    const check = newCheck();
    setChecks((previous) => [...previous, check]);
    setEditingId(check.id);
    setNewId(check.id);
  };
  const editCheck = (id: string | null) => {
    setEditingId(id);
    if (id !== newId) setNewId(null);
  };

  // A dataset made for a workflow brings it along when none is picked yet, and its category until one is picked.
  const pickDataset = (id: string) => {
    setSuiteId(id);
    const dataset = suites.find((suite) => suite.id === id);
    const datasetWorkflow = dataset?.workflow_id;
    if (!ownWorkflowId && !lockedWorkflowId && datasetWorkflow && workflows.some((item) => item.id === datasetWorkflow)) {
      setWorkflowId(datasetWorkflow);
    }
    if (!categoryPicked) setCategory(dataset?.category ?? "");
  };

  // What still blocks saving, where it is, and the check it is about.
  const blocker = (): { text: string; place: Place; checkId?: string } | null => {
    if (!name.trim()) return { text: "Add a name.", place: "name" };
    if (missingWorkflow) return { text: "Pick a workflow.", place: "workflow" };
    if (!datasetPicked) return { text: "Pick a dataset.", place: "dataset" };
    if (checks.length === 0 && metrics.length === 0) return { text: "Add at least one check.", place: "checks" };
    const incomplete = checks.find((check) => checkMissing(check));
    if (incomplete) {
      return { text: `A check is not complete: ${checkMissing(incomplete)}`, place: "checks", checkId: incomplete.id };
    }
    if (formProblem) {
      return { text: `A check is not complete: ${formProblem}`, place: "checks", checkId: editingId ?? undefined };
    }
    if (usesJudge && !graderId) return { text: "Pick an AI grader for the checks graded by AI.", place: "grader" };
    if (!isMetadataValid) return { text: "Fix the starting inputs.", place: "inputs" };
    return null;
  };

  const focus = (element: HTMLElement | null) => {
    element?.scrollIntoView({ block: "center", behavior: "smooth" });
    element?.focus({ preventScroll: true });
  };

  const showPlace = (place: Place, checkId?: string) => {
    if (place === "name") focus(nameRef.current);
    if (place === "workflow") focus(workflowRef.current);
    if (place === "dataset") focus(datasetRef.current);
    if (place === "grader") focus(graderRef.current);
    if (place === "checks") {
      // An opened check form brings itself into view, also when it was open already.
      if (checkId) {
        editCheck(checkId);
        setReveal((count) => count + 1);
      } else checksRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    }
    if (place === "inputs") {
      setInputsOpen(true);
      window.requestAnimationFrame(() => focus(inputsRef.current?.querySelector("textarea") ?? null));
    }
  };

  // Something missing is said and shown when saving, as the other forms do.
  const readyToSave = (): boolean => {
    const problem = blocker();
    if (!problem) return true;
    toast.error(problem.text);
    showPlace(problem.place, problem.checkId);
    return false;
  };

  const submit = async (run: boolean, targetWorkflowId?: string) => {
    setSubmitting(run ? "run" : "save");
    try {
      await onSubmit(
        {
          name,
          description,
          category,
          suiteId,
          // A legacy evaluation without a workflow of its own keeps running its dataset's.
          workflowId: workflowId || effectiveWorkflowId || "",
          metrics: checks.length ? [...metrics, CHECKS_TECHNIQUE] : metrics,
          inputMetadataText,
          useMemory,
          ...methods,
          checks,
          checksProviderId: usesJudge ? graderId : "",
          // Saved here, so what was left out has been seen.
          checksOlderMethods: olderMethods ? { ...olderMethods, reviewed: true } : null,
        },
        { run, targetWorkflowId },
      );
    } catch (error) {
      toast.error(extractErrorMessage(error, "Could not save the evaluation."));
    } finally {
      setSubmitting(null);
    }
  };

  const conversationsHint = !datasetPicked ? null : casesFailed ? (
    <span className="text-destructive">
      Its conversations could not be loaded.
      <button type="button" className="ml-1 font-medium text-primary hover:underline" onClick={retryCases}>
        Try again
      </button>
    </span>
  ) : !casesReady ? (
    "Loading its conversations…"
  ) : conversations.length === 0 ? (
    "This dataset has no conversations yet."
  ) : (
    `${conversations.length} conversation${conversations.length === 1 ? "" : "s"}.`
  );

  const runLabel = mode === "create" ? "Create and run" : "Save and run";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={onCancel} className="shrink-0" aria-label="Back">
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold tracking-tight animate-fade-down">
            {mode === "create" ? "New Evaluation" : "Edit Evaluation"}
          </h1>
          {mode === "edit" && initialData?.name && (
            <p className="truncate text-sm text-muted-foreground">{initialData.name}</p>
          )}
        </div>
      </div>

      <div className="divide-y rounded-lg border bg-card dark:bg-zinc-900">
        <Section
          title="General"
          description="Name the evaluation, pick the workflow it tests and the dataset it plays, and choose how its conversations replay."
        >
          <Field id={`${fieldId}-name`} label="Name" required>
            <Input
              ref={nameRef}
              id={`${fieldId}-name`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Parker refunds"
            />
          </Field>
          <Field id={`${fieldId}-description`} label="Description">
            <Textarea
              id={`${fieldId}-description`}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this evaluation tests"
              size="description"
            />
          </Field>
          <Field
            id={`${fieldId}-category`}
            label="Category"
            hint="Groups evaluations and datasets so they are easier to find."
          >
            <CategoryPicker
              id={`${fieldId}-category`}
              value={category}
              onChange={(picked) => {
                setCategory(picked);
                setCategoryPicked(true);
              }}
              categories={categories}
            />
          </Field>
          <Field
            id={`${fieldId}-workflow`}
            label="Workflow"
            required
            // The version saved with it does not decide what runs, so it is not offered here.
            hint={workflow?.agent_id ? "You pick the version when you run it." : undefined}
          >
            {lockedWorkflowId ? (
              <div className="rounded-full border bg-muted px-3 py-2 text-sm">
                {workflow?.agent_name || workflow?.name || "This workflow"}
              </div>
            ) : (
              <Select
                value={group?.key ?? ""}
                onValueChange={(key) => {
                  const picked = groups.find((item) => item.key === key);
                  if (picked && picked.key !== group?.key) setWorkflowId(picked.activeVersionId ?? picked.versions[0].id);
                }}
              >
                <SelectTrigger ref={workflowRef} id={`${fieldId}-workflow`}>
                  <SelectValue placeholder="Pick a workflow" />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((item) => (
                    <SelectItem key={item.key} value={item.key}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </Field>
          <Field id={`${fieldId}-dataset`} label="Dataset" required hint={conversationsHint}>
            <Select value={datasetPicked ? suiteId : ""} onValueChange={pickDataset}>
              <SelectTrigger ref={datasetRef} id={`${fieldId}-dataset`}>
                <SelectValue placeholder="Pick a dataset" />
              </SelectTrigger>
              <SelectContent>
                {suites
                  .filter((suite): suite is TestSuite & { id: string } => Boolean(suite.id))
                  .map((suite) => (
                    <SelectItem key={suite.id} value={suite.id}>
                      {suite.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </Field>
          <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
            <div>
              <div className="text-sm font-medium">Replay with memory</div>
              <div className="text-xs text-muted-foreground">Later turns see earlier ones, as in a real conversation.</div>
            </div>
            <Switch checked={useMemory} onCheckedChange={setUseMemory} aria-label="Replay with memory" />
          </div>
          <div ref={inputsRef} className="space-y-2">
            <button
              type="button"
              onClick={() => setInputsOpen((open) => !open)}
              aria-expanded={inputsOpen}
              className="flex items-center gap-1.5 text-sm font-medium"
            >
              <ChevronDown
                className={cn("h-4 w-4 text-muted-foreground transition-transform", !inputsOpen && "-rotate-90")}
              />
              Starting inputs
              <span className="font-normal text-muted-foreground">(optional)</span>
            </button>
            {inputsOpen && (
              <JsonInput
                value={inputMetadataText}
                onChange={setInputMetadataText}
                onValidChange={setIsMetadataValid}
                description="Inputs every conversation starts with, for example a region. A turn can still set its own."
                placeholder="{}"
                rows={6}
                allowEmpty
              />
            )}
          </div>
        </Section>

        <Section
          sectionRef={checksRef}
          title={`Checks${checks.length ? ` (${checks.length})` : ""}`}
          description="What should and should not happen. A check can apply to all conversations, the ones you choose, or one turn."
        >
          {!checksReady ? (
            <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
              {missingWorkflow && !datasetPicked
                ? "Pick a workflow and a dataset first. Checks are written for their steps and conversations."
                : missingWorkflow
                  ? "Pick a workflow first. Checks are written for its steps."
                  : "Pick a dataset first. Checks are written for its conversations."}
            </div>
          ) : (
            <>
              {leftOut.length > 0 && <LeftOutNote items={leftOut} />}
              {metrics.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  This evaluation still has older methods that could not be made into checks. They keep running next to
                  its checks, and saving keeps them as they are.
                </p>
              )}
              {checks.length === 0 ? (
                <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                  No checks yet. Start with one that holds for all conversations, such as a word the reply should never use.
                </div>
              ) : (
                <ChecksList
                  checks={checks}
                  conversations={conversations}
                  conversationsReady={casesReady}
                  conversationsFailed={casesFailed}
                  reveal={reveal}
                  catalog={catalog}
                  onChange={setChecks}
                  editingId={editingId}
                  newId={newId}
                  onEdit={editCheck}
                  onFormProblem={setFormProblem}
                  providers={providers}
                />
              )}
              <Button type="button" variant="outline" icon={<Plus className="h-4 w-4" />} onClick={addCheck}>
                Add check
              </Button>
              {usesJudge && (
                <Field id={`${fieldId}-grader`} label="AI grader for the checks graded by AI">
                  <Select value={graderId} onValueChange={setChecksProviderId}>
                    <SelectTrigger ref={graderRef} id={`${fieldId}-grader`}>
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
                </Field>
              )}
            </>
          )}
        </Section>
      </div>

      {/* Flush with the card's right edge, as on the knowledge base form. */}
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="outline" onClick={() => readyToSave() && submit(false)} disabled={submitting !== null}>
          {submitting === "save" ? "Saving…" : mode === "create" ? "Create" : "Save"}
        </Button>
        <Button
          onClick={() => {
            if (!readyToSave()) return;
            if (workflow?.agent_id) setPickingVersion(true);
            else void submit(true);
          }}
          disabled={submitting !== null}
        >
          {submitting === "run" ? "Starting…" : runLabel}
        </Button>
      </div>

      {workflow?.agent_id && (
        <RunAgainstVersionDialog
          isOpen={pickingVersion}
          onOpenChange={setPickingVersion}
          agentId={workflow.agent_id}
          currentWorkflowId={effectiveWorkflowId}
          openWorkflowId={runVersion?.id}
          confirmLabel={runLabel}
          asRun={{
            title: runLabel,
            description: (
              <>
                {mode === "create" ? "Creates" : "Saves"}{" "}
                <span className="font-medium text-foreground">{name.trim()}</span> and runs it on the version you pick.
              </>
            ),
          }}
          onRun={(targetWorkflowId) => {
            setPickingVersion(false);
            void submit(true, targetWorkflowId);
          }}
        />
      )}
    </div>
  );
};

export default EvaluationEditor;
