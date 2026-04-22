import React, { useState } from "react";
import { Button } from "@/components/button";
import { SimpleInput as Input } from "@/components/ui/simpleInput";
import { SimpleTextarea as Textarea } from "@/components/ui/simpleTextarea";
import { Label } from "@/components/label";
import { JsonInput } from "@/components/JsonInput";
import { Checkbox } from "@/components/checkbox";
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
} from "@/components/ui/dialog";
import { ChevronLeft, ChevronRight, Check, Database, Workflow, Settings, ClipboardCheck } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";

const METRICS = [
  { value: "exact_match", label: "Exact Match", description: "Checks if output exactly matches expected" },
  { value: "contains", label: "Contains", description: "Checks if output contains expected text" },
  { value: "json_match", label: "JSON Match", description: "Compares JSON structure and values" },
  { value: "nli_eval", label: "NLI Evaluation", description: "Natural Language Inference check" },
  { value: "provenance_eval", label: "Provenance Evaluation", description: "Verifies output is grounded in context" },
];

const NLI_MODEL_OPTIONS = [
  { value: "cross-encoder/nli-deberta-v3-base", label: "DeBERTa v3 Base (NLI)" },
  { value: "cross-encoder/nli-roberta-base", label: "RoBERTa Base (NLI)" },
];

type WizardStep = "basics" | "data" | "validation" | "configure";

const STEPS: { key: WizardStep; label: string; icon: React.ElementType }[] = [
  { key: "basics", label: "Basics", icon: ClipboardCheck },
  { key: "data", label: "Data Source", icon: Database },
  { key: "validation", label: "Validation", icon: Settings },
  { key: "configure", label: "Configure", icon: Workflow },
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
  provMode: "embeddings" | "llm";
  provEmbeddingType: "openai" | "huggingface" | "bedrock";
  provEmbeddingModelName: string;
  provMinScore: string;
  provFailOnViolation: boolean;
  provLlmProviderId: string;
  provLlmJudgeSystemPromptSuffix: string;
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
}) => {
  const [step, setStep] = useState<WizardStep>("basics");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form state
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [suiteId, setSuiteId] = useState(initialData?.suiteId ?? "none");
  const [workflowId, setWorkflowId] = useState(initialData?.workflowId ?? "none");
  const [metrics, setMetrics] = useState<string[]>(initialData?.metrics ?? ["exact_match"]);
  const [inputMetadataText, setInputMetadataText] = useState(initialData?.inputMetadataText ?? "{}");
  const [isMetadataValid, setIsMetadataValid] = useState(true);
  const [useMemory, setUseMemory] = useState(initialData?.useMemory ?? false);

  // NLI config
  const [nliModelName, setNliModelName] = useState(
    initialData?.nliModelName ?? "cross-encoder/nli-deberta-v3-base"
  );
  const [nliMinEntailScore, setNliMinEntailScore] = useState(initialData?.nliMinEntailScore ?? "0.5");
  const [nliFailOnContradiction, setNliFailOnContradiction] = useState(
    initialData?.nliFailOnContradiction ?? false
  );

  // Provenance config
  const [provMode, setProvMode] = useState<"embeddings" | "llm">(initialData?.provMode ?? "embeddings");
  const [provEmbeddingType, setProvEmbeddingType] = useState<"openai" | "huggingface" | "bedrock">(
    initialData?.provEmbeddingType ?? "huggingface"
  );
  const [provEmbeddingModelName, setProvEmbeddingModelName] = useState(
    initialData?.provEmbeddingModelName ?? "all-MiniLM-L6-v2"
  );
  const [provMinScore, setProvMinScore] = useState(initialData?.provMinScore ?? "0.5");
  const [provFailOnViolation, setProvFailOnViolation] = useState(
    initialData?.provFailOnViolation ?? false
  );
  const [provLlmProviderId, setProvLlmProviderId] = useState(
    initialData?.provLlmProviderId ?? providers[0]?.id ?? ""
  );
  const [provLlmJudgeSystemPromptSuffix, setProvLlmJudgeSystemPromptSuffix] = useState(
    initialData?.provLlmJudgeSystemPromptSuffix ?? ""
  );

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  const canProceed = (): boolean => {
    switch (step) {
      case "basics":
        return name.trim().length > 0;
      case "data":
        return suiteId !== "none" && isMetadataValid;
      case "validation":
        return metrics.length > 0;
      case "configure":
        return true;
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
        nliModelName,
        nliMinEntailScore,
        nliFailOnContradiction,
        provMode,
        provEmbeddingType,
        provEmbeddingModelName,
        provMinScore,
        provFailOnViolation,
        provLlmProviderId,
        provLlmJudgeSystemPromptSuffix,
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
    setStep("basics");
    setName("");
    setDescription("");
    setSuiteId("none");
    setWorkflowId("none");
    setMetrics(["exact_match"]);
    setInputMetadataText("{}");
    setIsMetadataValid(true);
    setUseMemory(false);
    setNliModelName("cross-encoder/nli-deberta-v3-base");
    setNliMinEntailScore("0.5");
    setNliFailOnContradiction(false);
    setProvMode("embeddings");
    setProvEmbeddingType("huggingface");
    setProvEmbeddingModelName("all-MiniLM-L6-v2");
    setProvMinScore("0.5");
    setProvFailOnViolation(false);
    setProvLlmProviderId(providers[0]?.id ?? "");
    setProvLlmJudgeSystemPromptSuffix("");
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  const needsConfigStep = metrics.includes("nli_eval") || metrics.includes("provenance_eval");

  const renderStepContent = () => {
    switch (step) {
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
              <p className="text-xs text-gray-500 mt-1">
                Give your evaluation a descriptive name
              </p>
            </div>
            <div>
              <Label className="text-sm font-medium">Description</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this evaluation tests..."
                rows={3}
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
              <p className="text-xs text-gray-500 mt-1">
                Choose the dataset containing your test cases
              </p>
            </div>
            <div>
              <Label className="text-sm font-medium">Workflow</Label>
              <Select value={workflowId} onValueChange={setWorkflowId}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue placeholder="Select workflow version" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Use dataset default workflow</SelectItem>
                  {workflows
                    .filter((wf): wf is WorkflowMinimal => Boolean(wf.id))
                    .map((wf) => (
                      <SelectItem key={wf.id} value={wf.id}>
                        {wf.name} (v{wf.version})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <JsonInput
              value={inputMetadataText}
              onChange={setInputMetadataText}
              onValidChange={(valid) => setIsMetadataValid(valid)}
              label="Extra Metadata (JSON)"
              description="Optional metadata to pass with each test case"
              placeholder="{}"
              rows={3}
              allowEmpty
            />
            <div className="flex items-center justify-between rounded-lg border px-4 py-3">
              <div>
                <div className="text-sm font-medium">Use Memory</div>
                <div className="text-xs text-gray-500">
                  Generate unique thread ID per run for conversation memory
                </div>
              </div>
              <Switch checked={useMemory} onCheckedChange={setUseMemory} />
            </div>
          </div>
        );

      case "validation":
        return (
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Validation Methods *</Label>
              <p className="text-xs text-gray-500 mb-3">
                Select at least one method to validate your agent's outputs
              </p>
              <div className="space-y-2">
                {METRICS.map((metric) => (
                  <div
                    key={metric.value}
                    className={cn(
                      "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                      metrics.includes(metric.value)
                        ? "border-primary bg-primary/5"
                        : "hover:border-gray-300"
                    )}
                    onClick={() => {
                      setMetrics((prev) =>
                        prev.includes(metric.value)
                          ? prev.filter((m) => m !== metric.value)
                          : [...prev, metric.value]
                      );
                    }}
                  >
                    <Checkbox
                      id={`metric-${metric.value}`}
                      checked={metrics.includes(metric.value)}
                      onClick={(e) => e.stopPropagation()}
                      onCheckedChange={(checked) => {
                        setMetrics((prev) =>
                          checked
                            ? [...prev, metric.value]
                            : prev.filter((m) => m !== metric.value)
                        );
                      }}
                      className="mt-0.5"
                    />
                    <div className="flex-1">
                      <Label
                        htmlFor={`metric-${metric.value}`}
                        className="text-sm font-medium cursor-pointer"
                      >
                        {metric.label}
                      </Label>
                      <p className="text-xs text-gray-500 mt-0.5">{metric.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      case "configure":
        return (
          <div className="space-y-4">
            {!needsConfigStep && (
              <div className="text-center py-8 text-gray-500">
                <Settings className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">No additional configuration needed.</p>
                <p className="text-xs mt-1">
                  The selected validation methods don't require extra settings.
                </p>
              </div>
            )}

            {metrics.includes("nli_eval") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  NLI Evaluation Config
                </div>
                <p className="text-xs text-gray-500">
                  Uses workflow output as answer and expected output as evidence.
                </p>
                <div>
                  <Label className="text-xs">NLI Model</Label>
                  <Select value={nliModelName} onValueChange={setNliModelName}>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select NLI model" />
                    </SelectTrigger>
                    <SelectContent>
                      {NLI_MODEL_OPTIONS.map((model) => (
                        <SelectItem key={model.value} value={model.value}>
                          {model.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">Min Entailment Score (0-1)</Label>
                  <Input
                    value={nliMinEntailScore}
                    onChange={(e) => setNliMinEntailScore(e.target.value)}
                    className="mt-1"
                    placeholder="0.5"
                  />
                </div>
                {false && (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="nli-fail-on-contradiction"
                      checked={nliFailOnContradiction}
                      onCheckedChange={(checked) => setNliFailOnContradiction(Boolean(checked))}
                    />
                    <Label htmlFor="nli-fail-on-contradiction" className="text-xs font-normal cursor-pointer">
                      Fail on contradiction
                    </Label>
                  </div>
                )}
              </div>
            )}

            {metrics.includes("provenance_eval") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500"></span>
                  Provenance Evaluation Config
                </div>
                <p className="text-xs text-gray-500">
                  Uses workflow output as answer and expected output as context.
                </p>
                <div>
                  <Label className="text-xs">Provenance Mode</Label>
                  <Select
                    value={provMode}
                    onValueChange={(value: "embeddings" | "llm") => setProvMode(value)}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select mode" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="embeddings">Embeddings</SelectItem>
                      <SelectItem value="llm">LLM Judge</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">Min Score (0-1)</Label>
                  <Input
                    value={provMinScore}
                    onChange={(e) => setProvMinScore(e.target.value)}
                    className="mt-1"
                    placeholder="0.5"
                  />
                </div>
                {false && (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="prov-fail-on-violation"
                      checked={provFailOnViolation}
                      onCheckedChange={(checked) => setProvFailOnViolation(Boolean(checked))}
                    />
                    <Label htmlFor="prov-fail-on-violation" className="text-xs font-normal cursor-pointer">
                      Fail on violation
                    </Label>
                  </div>
                )}

                {provMode === "embeddings" && (
                  <>
                    <div>
                      <Label className="text-xs">Embedding Provider</Label>
                      <Select
                        value={provEmbeddingType}
                        onValueChange={(value: "openai" | "huggingface" | "bedrock") =>
                          setProvEmbeddingType(value)
                        }
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="Select embedding provider" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="huggingface">HuggingFace</SelectItem>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">Embedding Model Name</Label>
                      <Input
                        value={provEmbeddingModelName}
                        onChange={(e) => setProvEmbeddingModelName(e.target.value)}
                        placeholder="all-MiniLM-L6-v2"
                        className="mt-1"
                      />
                    </div>
                  </>
                )}

                {provMode === "llm" && (
                  <>
                    <div>
                      <Label className="text-xs">LLM Provider</Label>
                      <Select value={provLlmProviderId} onValueChange={setProvLlmProviderId}>
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="Select provider" />
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
                    <div>
                      <Label className="text-xs">Additional Judge Instructions</Label>
                      <Textarea
                        value={provLlmJudgeSystemPromptSuffix}
                        onChange={(e) => setProvLlmJudgeSystemPromptSuffix(e.target.value)}
                        placeholder="Optional extra instructions for the judge..."
                        rows={3}
                        className="mt-1"
                      />
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[760px] p-0 overflow-hidden">
        <div className="max-h-[85vh] overflow-hidden flex flex-col">
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
                        !isActive && !isCompleted && "bg-gray-100 text-gray-500",
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
                          index < currentStepIndex ? "bg-primary" : "bg-gray-200"
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
                <Button variant="outline" onClick={handleBack}>
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Back
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
