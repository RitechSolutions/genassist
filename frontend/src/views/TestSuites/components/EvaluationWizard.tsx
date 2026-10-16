import React, { useEffect, useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { JsonInput } from "@/components/JsonInput";
import { Switch } from "@/components/switch";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { ChevronLeft, ChevronRight, Check, Database, Workflow, Settings, SlidersHorizontal, ClipboardCheck } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type {
  ActionRuleDraft,
  JudgeRuleDraft,
  RouteRuleDraft,
  ScenarioCheck,
  ToolUsageRule,
} from "@/interfaces/testEvaluation.interface";
import { WorkflowVersionPicker } from "./WorkflowVersionPicker";
import { newEvaluationDefaults } from "../helpers/evaluationForm";
import {
  methodDefaults,
  methodSettingsComplete,
  remapToolRuleNames,
  type GradingSourceSelection,
  type MethodSettingsValue,
} from "../helpers/methodSettings";
import { useDatasetCases, useEvaluationCatalog, useRuleConversations } from "../hooks/useEvaluationData";
import { MethodPicker, MethodSettings } from "./LegacyMethodsPanel";

export type { GradingSourceSelection } from "../helpers/methodSettings";

type WizardStep = "workflow" | "basics" | "data" | "validation" | "configure";

const STEPS: { key: WizardStep; label: string; icon: React.ElementType }[] = [
  { key: "workflow", label: "Workflow", icon: Workflow },
  { key: "basics", label: "Basics", icon: ClipboardCheck },
  { key: "data", label: "Data Source", icon: Database },
  { key: "validation", label: "Validation", icon: Settings },
  { key: "configure", label: "Configure", icon: SlidersHorizontal },
];


export interface EvaluationWizardData {
  name: string;
  description: string;
  suiteId: string;
  workflowId: string;
  metrics: string[];
  inputMetadataText: string;
  useMemory: boolean;
  nliModelName: string;
  nliMinEntailScore: string;
  nliFailOnContradiction: boolean;
  nliEvidenceSource: GradingSourceSelection;
  nliEvidenceField: string;
  provMode: "embeddings" | "llm";
  provContextSource: GradingSourceSelection;
  provContextField: string;
  provEmbeddingType: "openai" | "huggingface" | "bedrock";
  provEmbeddingModelName: string;
  provMinScore: string;
  provFailOnViolation: boolean;
  provLlmProviderId: string;
  provLlmJudgeSystemPromptSuffix: string;
  toolRules: ToolUsageRule[];
  notContainsText: string;
  fieldEqualsField: string;
  fieldEqualsExpected: string;
  routeRules: RouteRuleDraft[];
  actionRules: ActionRuleDraft[];
  judgeRules: JudgeRuleDraft[];
  judgeProviderId: string;
  /** Edited in the evaluation editor; the wizard keeps them as they are. */
  checks: ScenarioCheck[];
  checksProviderId: string;
}

interface EvaluationWizardProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: EvaluationWizardData) => Promise<void>;
  suites: TestSuite[];
  workflows: WorkflowMinimal[];
  providers: LLMProviderMinimal[];
  initialData?: Partial<EvaluationWizardData>;
  mode?: "create" | "edit";
  /**
   * When set (e.g. creating from a workflow's page), the workflow is pinned to
   * this id and shown read-only instead of the picker.
   */
  lockedWorkflowId?: string;
}

export const EvaluationWizard: React.FC<EvaluationWizardProps> = ({
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
  const [step, setStep] = useState<WizardStep>("workflow");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Which workflow group's version list is expanded (only one at a time; collapsed
  // by default so the list stays short).

  // Form state
  const defaults = newEvaluationDefaults(lockedWorkflowId);
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [suiteId, setSuiteId] = useState(initialData?.suiteId ?? "none");
  const [workflowId, setWorkflowId] = useState(
    lockedWorkflowId ?? initialData?.workflowId ?? defaults.workflowId,
  );
  const [metrics, setMetrics] = useState<string[]>(initialData?.metrics ?? defaults.metrics);
  const [inputMetadataText, setInputMetadataText] = useState(initialData?.inputMetadataText ?? "{}");
  const [isMetadataValid, setIsMetadataValid] = useState(true);
  const [useMemory, setUseMemory] = useState(initialData?.useMemory ?? defaults.useMemory);

  const [methods, setMethods] = useState<MethodSettingsValue>(() => methodDefaults(initialData, providers));
  const patchMethods = (patch: Partial<MethodSettingsValue>) =>
    setMethods((previous) => ({ ...previous, ...patch }));

  // Tool Usage, Route and Action are all rule-based: they share the node catalogue
  // and the dataset's conversations for specific-turn targeting.
  const needsCatalog =
    metrics.includes("tool_used") ||
    metrics.includes("route_taken") ||
    metrics.includes("action_taken");

  // Fall back to the dataset's default workflow when none is explicitly chosen,
  // so the tool catalogue still loads.
  const selectedSuite = suites.find((s) => s.id === suiteId);
  const effectiveWorkflowId =
    workflowId && workflowId !== "none" ? workflowId : selectedSuite?.workflow_id;
  // Only edits of an evaluation saved without a workflow keep the dataset-default option.
  const offersDatasetDefault = mode === "edit" && initialData?.workflowId === "none";
  const missingWorkflow = workflowId === "none" && !selectedSuite?.workflow_id;

  const catalog = useEvaluationCatalog(effectiveWorkflowId, needsCatalog);
  const conversations = useRuleConversations(useDatasetCases(suiteId, needsCatalog).cases);

  // When the catalogue loads, rewrite any legacy tool/agent NAMES (from an old
  // evaluation) to canonical ids so they aren't later saved as if they were ids.
  useEffect(() => {
    const remapped = remapToolRuleNames(methods.toolRules, catalog.agents);
    if (remapped !== methods.toolRules) patchMethods({ toolRules: remapped });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog.agents]);

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  const canProceed = (): boolean => {
    switch (step) {
      case "workflow":
        return workflowId.length > 0 && !missingWorkflow;
      case "basics":
        return name.trim().length > 0;
      case "data":
        return suiteId !== "none" && isMetadataValid && !missingWorkflow;
      case "validation":
        return metrics.length > 0;
      case "configure":
        return methodSettingsComplete(metrics, methods, { agents: catalog.agents, routers: catalog.routers });
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStepIndex < STEPS.length - 1) {
      setStep(STEPS[currentStepIndex + 1].key);
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setStep(STEPS[currentStepIndex - 1].key);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        suiteId,
        workflowId,
        metrics,
        inputMetadataText,
        useMemory,
        ...methods,
        checks: initialData?.checks ?? [],
        checksProviderId: initialData?.checksProviderId ?? "",
      });
      // Reset form on successful create
      if (mode === "create") {
        resetForm();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetForm = () => {
    setStep("workflow");
    setName("");
    setDescription("");
    setSuiteId("none");
    setWorkflowId(defaults.workflowId);
    setMetrics(defaults.metrics);
    setInputMetadataText("{}");
    setIsMetadataValid(true);
    setUseMemory(defaults.useMemory);
    setMethods(methodDefaults(undefined, providers));
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  const renderStepContent = () => {
    switch (step) {
      case "workflow":
        return (
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Select Workflow *</Label>
              <p className="text-xs text-muted-foreground">
                Pick the workflow this evaluation runs against. Expand a workflow to
                choose a version; the one marked Current is what a plain run executes.
              </p>
            </div>

            {lockedWorkflowId ? (
              <div className="rounded-lg border bg-muted px-4 py-3 text-sm">
                {workflows.find((wf) => wf.id === lockedWorkflowId)?.name ?? "This workflow"}
              </div>
            ) : (
              <WorkflowVersionPicker
                workflows={workflows}
                selectedWorkflowId={workflowId}
                onSelect={setWorkflowId}
                leadingOption={
                  offersDatasetDefault ? (
                    <button
                      type="button"
                      onClick={() => setWorkflowId("none")}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                        workflowId === "none"
                          ? "bg-primary/10 font-semibold text-primary"
                          : "font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Database className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">Use dataset's default workflow</span>
                      {workflowId === "none" && <Check className="ml-auto h-4 w-4 shrink-0" />}
                    </button>
                  ) : undefined
                }
              />
            )}
            {missingWorkflow && (
              <p className="text-xs text-destructive">
                This evaluation's dataset has no default workflow. Choose a workflow to continue.
              </p>
            )}
          </div>
        );

      case "basics":
        return (
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Evaluation Name *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. FAQ Regression Test"
                className="mt-1.5"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Give your evaluation a descriptive name
              </p>
            </div>
            <div>
              <Label className="text-sm font-medium">Description</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this evaluation tests..."
                size="hint"
                className="mt-1.5"
              />
            </div>
          </div>
        );

      case "data":
        return (
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Dataset *</Label>
              <Select value={suiteId} onValueChange={setSuiteId}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue placeholder="Select a dataset" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Select dataset</SelectItem>
                  {suites
                    .filter((s): s is TestSuite & { id: string } => Boolean(s.id))
                    .map((suite) => (
                      <SelectItem key={suite.id} value={suite.id}>
                        {suite.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                Choose the dataset containing your test cases
              </p>
              {suiteId !== "none" && missingWorkflow && (
                <p className="text-xs text-destructive mt-1">
                  This dataset has no default workflow. Go back to the Workflow step and choose one.
                </p>
              )}
            </div>
            <JsonInput
              value={inputMetadataText}
              onChange={setInputMetadataText}
              onValidChange={(valid) => setIsMetadataValid(valid)}
              label="Extra Metadata (JSON)"
              description="Optional metadata to pass with each test case"
              placeholder="{}"
              rows={8}
              allowEmpty
            />
            <div className="flex items-center justify-between rounded-lg border px-4 py-3">
              <div>
                <div className="text-sm font-medium">Replay conversations with memory</div>
                <div className="text-xs text-muted-foreground">
                  Later turns see earlier ones. Turn this off to run every turn on its own.
                </div>
              </div>
              <Switch checked={useMemory} onCheckedChange={setUseMemory} />
            </div>
          </div>
        );

      case "validation":
        return (
          <div className="space-y-5">
            <div>
              <Label className="text-sm font-medium">Validation Methods *</Label>
              <p className="text-xs text-muted-foreground">
                Select at least one method to validate your agent's outputs
              </p>
            </div>
            <MethodPicker metrics={metrics} onChange={setMetrics} />
          </div>
        );

      case "configure":
        return (
          <MethodSettings
            metrics={metrics}
            settings={methods}
            onChange={patchMethods}
            providers={providers}
            catalog={catalog}
            conversations={conversations}
            hasWorkflow={Boolean(effectiveWorkflowId)}
            showEmptyState
          />
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[960px] p-0 overflow-hidden">
        <div className="h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>{mode === "create" ? "Create Evaluation" : "Edit Evaluation"}</DialogTitle>
            {/* Step indicator */}
            <div className="flex items-center gap-2 mt-4">
              {STEPS.map((s, index) => {
                const Icon = s.icon;
                const isActive = s.key === step;
                const isCompleted = index < currentStepIndex;
                const isClickable = index <= currentStepIndex || (index === currentStepIndex + 1 && canProceed());

                return (
                  <React.Fragment key={s.key}>
                    <button
                      type="button"
                      onClick={() => isClickable && setStep(s.key)}
                      disabled={!isClickable}
                      className={cn(
                        "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                        isActive && "bg-primary text-primary-foreground",
                        isCompleted && !isActive && "bg-primary/20 text-primary",
                        !isActive && !isCompleted && "bg-muted text-muted-foreground",
                        isClickable && !isActive && "hover:bg-gray-200 cursor-pointer",
                        !isClickable && "opacity-50 cursor-not-allowed"
                      )}
                    >
                      {isCompleted && !isActive ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <Icon className="h-3 w-3" />
                      )}
                      <span className="hidden sm:inline">{s.label}</span>
                    </button>
                    {index < STEPS.length - 1 && (
                      <div
                        className={cn(
                          "flex-1 h-0.5 rounded-full max-w-8",
                          index < currentStepIndex ? "bg-primary" : "bg-muted"
                        )}
                      />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
            {renderStepContent()}
          </div>

          <DialogFooter className="border-t px-6 py-4 shrink-0 flex justify-between">
            <div>
              {currentStepIndex > 0 && (
                <Button variant="outline" size="icon" onClick={handleBack} aria-label="Back">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              {currentStepIndex < STEPS.length - 1 ? (
                <Button onClick={handleNext} disabled={!canProceed()}>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              ) : (
                <Button onClick={handleSubmit} disabled={!canProceed() || isSubmitting}>
                  {isSubmitting
                    ? "Creating..."
                    : mode === "create"
                    ? "Create Evaluation"
                    : "Save Changes"}
                </Button>
              )}
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EvaluationWizard;
