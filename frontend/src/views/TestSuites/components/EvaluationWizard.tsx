import React, { useState } from "react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
} from "@/components/dialog";
import { ChevronLeft, ChevronRight, Check, Database, Workflow, Settings, ClipboardCheck } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";

interface MetricDef {
  value: string;
  label: string;
  description: string;
}

const METRIC_GROUPS: { label: string; metrics: MetricDef[] }[] = [
  {
    label: "Output match",
    metrics: [
      { value: "exact_match", label: "Exact Match", description: "Output exactly equals the expected value" },
      { value: "contains", label: "Contains", description: "Output contains the expected text" },
      { value: "json_match", label: "JSON Match", description: "Output matches the expected JSON structure and values" },
    ],
  },
  {
    label: "Agent process",
    metrics: [
      { value: "tool_used", label: "Tool Usage", description: "Define whether a tool should or should not be used" },
      { value: "route_taken", label: "Route Taken", description: "Select the route the workflow is expected to take" },
      { value: "action_taken", label: "Action Taken", description: "Define whether an action should or should not happen" },
      { value: "no_errors", label: "No Errors", description: "The run completed without any node failures" },
    ],
  },
  {
    label: "Grounding & LLM judge",
    metrics: [
      { value: "nli_eval", label: "NLI Evaluation", description: "Natural Language Inference entailment check" },
      { value: "provenance_eval", label: "Provenance Evaluation", description: "Verifies the answer is grounded in context" },
      { value: "llm_judge", label: "LLM Judge", description: "Grades the answer against a custom rubric" },
    ],
  },
];

const CONFIG_METRICS = [
  "nli_eval",
  "provenance_eval",
  "tool_used",
  "route_taken",
  "action_taken",
  "llm_judge",
];

const isJsonObject = (text: string): boolean => {
  try {
    const parsed = JSON.parse(text);
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed);
  } catch {
    return false;
  }
};

// A score field is valid when empty (a default applies) or a number in [0, 1].
const isValidScore = (text: string): boolean => {
  if (text.trim() === "") return true;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 && value <= 1;
};

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

const MetricOption: React.FC<{
  metric: MetricDef;
  selected: boolean;
  onToggle: (checked: boolean) => void;
}> = ({ metric, selected, onToggle }) => (
  <div
    className={cn(
      "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
      selected ? "border-primary bg-primary/5" : "hover:border-gray-300"
    )}
    onClick={() => onToggle(!selected)}
  >
    <Checkbox
      id={`metric-${metric.value}`}
      checked={selected}
      onClick={(e) => e.stopPropagation()}
      onCheckedChange={(checked) => onToggle(Boolean(checked))}
      className="mt-0.5"
    />
    <div className="flex-1">
      <Label htmlFor={`metric-${metric.value}`} className="text-sm font-medium cursor-pointer">
        {metric.label}
      </Label>
      <p className="text-xs text-gray-500 mt-0.5">{metric.description}</p>
    </div>
  </div>
);

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
  toolName: string;
  toolShouldCall: boolean;
  toolExpectedArgsText: string;
  toolNode: string;
  toolResultNotEmpty: boolean;
  toolResultContains: string;
  routeExpected: string;
  routeNode: string;
  actionNode: string;
  actionNodeType: string;
  actionShouldFire: boolean;
  judgeRubric: string;
  judgeMinScore: string;
  judgeProviderId: string;
  judgeSourceField: string;
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

  // Tool Used config
  const [toolName, setToolName] = useState(initialData?.toolName ?? "");
  const [toolShouldCall, setToolShouldCall] = useState(initialData?.toolShouldCall ?? true);
  const [toolExpectedArgsText, setToolExpectedArgsText] = useState(initialData?.toolExpectedArgsText ?? "");
  const [toolNode, setToolNode] = useState(initialData?.toolNode ?? "");
  const [toolResultNotEmpty, setToolResultNotEmpty] = useState(initialData?.toolResultNotEmpty ?? false);
  const [toolResultContains, setToolResultContains] = useState(initialData?.toolResultContains ?? "");
  const [toolAdvancedOpen, setToolAdvancedOpen] = useState(false);

  const toolRuleSummary = (): string => {
    const agentPart = toolNode.trim() ? `the "${toolNode.trim()}" agent` : "any agent";
    const toolPart = toolName.trim() ? `"${toolName.trim()}"` : "any tool";
    if (!toolShouldCall) {
      return `Passes when ${agentPart} does NOT call ${toolPart}.`;
    }
    const extraClauses: string[] = [];
    if (toolExpectedArgsText.trim()) extraClauses.push("the arguments match your JSON");
    if (toolResultNotEmpty) extraClauses.push("the result is not empty");
    if (toolResultContains.trim()) extraClauses.push(`the result contains "${toolResultContains.trim()}"`);
    const extras = extraClauses.length ? `, and ${extraClauses.join(", and ")}` : "";
    return `Passes when ${agentPart} calls ${toolPart}${extras}.`;
  };

  // Route Taken config
  const [routeExpected, setRouteExpected] = useState(initialData?.routeExpected ?? "");
  const [routeNode, setRouteNode] = useState(initialData?.routeNode ?? "");

  // Action Taken config
  const [actionNode, setActionNode] = useState(initialData?.actionNode ?? "");
  const [actionNodeType, setActionNodeType] = useState(initialData?.actionNodeType ?? "");
  const [actionShouldFire, setActionShouldFire] = useState(initialData?.actionShouldFire ?? true);

  // LLM Judge config
  const [judgeRubric, setJudgeRubric] = useState(initialData?.judgeRubric ?? "");
  const [judgeMinScore, setJudgeMinScore] = useState(initialData?.judgeMinScore ?? "0.5");
  const [judgeProviderId, setJudgeProviderId] = useState(
    initialData?.judgeProviderId ?? providers[0]?.id ?? ""
  );
  const [judgeSourceField, setJudgeSourceField] = useState(initialData?.judgeSourceField ?? "");

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  const toolArgsInvalid =
    metrics.includes("tool_used") &&
    toolShouldCall &&
    toolExpectedArgsText.trim() !== "" &&
    !isJsonObject(toolExpectedArgsText);
  const nliScoreInvalid = metrics.includes("nli_eval") && !isValidScore(nliMinEntailScore);
  const provScoreInvalid = metrics.includes("provenance_eval") && !isValidScore(provMinScore);
  const judgeScoreInvalid = metrics.includes("llm_judge") && !isValidScore(judgeMinScore);

  const isConfigureStepValid = (): boolean => {
    if (metrics.includes("llm_judge") && !judgeRubric.trim()) return false;
    if (metrics.includes("route_taken") && !routeExpected.trim()) return false;
    if (metrics.includes("action_taken") && !actionNode.trim() && !actionNodeType.trim()) return false;
    if (toolArgsInvalid || nliScoreInvalid || provScoreInvalid || judgeScoreInvalid) return false;
    return true;
  };

  const canProceed = (): boolean => {
    switch (step) {
      case "basics":
        return name.trim().length > 0;
      case "data":
        return suiteId !== "none" && isMetadataValid;
      case "validation":
        return metrics.length > 0;
      case "configure":
        return isConfigureStepValid();
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
        toolName,
        toolShouldCall,
        toolExpectedArgsText,
        toolNode,
        toolResultNotEmpty,
        toolResultContains,
        routeExpected,
        routeNode,
        actionNode,
        actionNodeType,
        actionShouldFire,
        judgeRubric,
        judgeMinScore,
        judgeProviderId,
        judgeSourceField,
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
    setToolName("");
    setToolShouldCall(true);
    setToolExpectedArgsText("");
    setToolNode("");
    setToolResultNotEmpty(false);
    setToolResultContains("");
    setToolAdvancedOpen(false);
    setRouteExpected("");
    setRouteNode("");
    setActionNode("");
    setActionNodeType("");
    setActionShouldFire(true);
    setJudgeRubric("");
    setJudgeMinScore("0.5");
    setJudgeProviderId(providers[0]?.id ?? "");
    setJudgeSourceField("");
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      resetForm();
    }
    onOpenChange(open);
  };

  const needsConfigStep = metrics.some((m) => CONFIG_METRICS.includes(m));

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
          <div className="space-y-5">
            <div>
              <Label className="text-sm font-medium">Validation Methods *</Label>
              <p className="text-xs text-gray-500">
                Select at least one method to validate your agent's outputs
              </p>
            </div>
            {METRIC_GROUPS.map((group) => (
              <div key={group.label} className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  {group.label}
                </div>
                {group.metrics.map((metric) => (
                  <MetricOption
                    key={metric.value}
                    metric={metric}
                    selected={metrics.includes(metric.value)}
                    onToggle={(checked) =>
                      setMetrics((prev) =>
                        checked
                          ? [...prev, metric.value]
                          : prev.filter((m) => m !== metric.value)
                      )
                    }
                  />
                ))}
              </div>
            ))}
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
                  {nliScoreInvalid && (
                    <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
                  )}
                </div>
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
                      <SelectItem value="llm">LLM Verification</SelectItem>
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
                  {provScoreInvalid && (
                    <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
                  )}
                </div>
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
                      <Label className="text-xs">Additional Verification Instructions</Label>
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

            {metrics.includes("tool_used") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  Tool Usage Config
                </div>
                <p className="text-xs text-gray-500">
                  Checks whether an agent called a specific tool during the run.
                </p>
                <div>
                  <Label className="text-xs">Tool Name</Label>
                  <Input
                    value={toolName}
                    onChange={(e) => setToolName(e.target.value)}
                    placeholder="e.g. search_handbook"
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Leave empty to check whether any tool was called.
                  </p>
                </div>
                <div>
                  <Label className="text-xs">Agent (optional)</Label>
                  <Input
                    value={toolNode}
                    onChange={(e) => setToolNode(e.target.value)}
                    placeholder="Any agent"
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Defaults to any agent. Name one (id or label) to only count its calls — useful
                    when several agents share tool names.
                  </p>
                </div>
                <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div>
                    <div className="text-xs font-medium">
                      {toolShouldCall ? "Must be called" : "Should not be used"}
                    </div>
                    <div className="text-xs text-gray-500">
                      Turn off to assert the tool was NOT called
                    </div>
                  </div>
                  <Switch checked={toolShouldCall} onCheckedChange={setToolShouldCall} />
                </div>

                {toolShouldCall && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setToolAdvancedOpen((open) => !open)}
                      className="text-xs font-medium text-gray-500 hover:text-gray-700"
                    >
                      {toolAdvancedOpen ? "▾" : "▸"} Advanced validation
                    </button>
                    {toolAdvancedOpen && (
                      <div className="space-y-3 mt-3">
                        <div>
                          <Label className="text-xs">Expected Arguments (JSON, optional)</Label>
                          <Textarea
                            value={toolExpectedArgsText}
                            onChange={(e) => setToolExpectedArgsText(e.target.value)}
                            placeholder='{"query": "vacation policy"}'
                            rows={2}
                            className="mt-1 font-mono text-xs"
                          />
                          {toolArgsInvalid && (
                            <p className="text-xs text-red-500 mt-1">
                              Enter a valid JSON object, e.g. {'{"query": "vacation policy"}'}.
                            </p>
                          )}
                        </div>
                        <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                          <div>
                            <div className="text-xs font-medium">Result must not be empty</div>
                            <div className="text-xs text-gray-500">
                              Fail if the call returned nothing (e.g. an empty retrieval)
                            </div>
                          </div>
                          <Switch checked={toolResultNotEmpty} onCheckedChange={setToolResultNotEmpty} />
                        </div>
                        <div>
                          <Label className="text-xs">Result must contain (optional)</Label>
                          <Input
                            value={toolResultContains}
                            onChange={(e) => setToolResultContains(e.target.value)}
                            placeholder="Text the tool's result must include"
                            className="mt-1"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="rounded-lg bg-gray-50 border border-gray-100 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold mb-0.5">
                    Rule
                  </div>
                  <p className="text-xs text-gray-600">{toolRuleSummary()}</p>
                </div>
              </div>
            )}

            {metrics.includes("route_taken") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  Route Taken Config
                </div>
                <p className="text-xs text-gray-500">
                  Checks that a router node selected the expected branch.
                </p>
                <div>
                  <Label className="text-xs">Expected Route *</Label>
                  <Input
                    value={routeExpected}
                    onChange={(e) => setRouteExpected(e.target.value)}
                    placeholder="e.g. escalate"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">Router Node (id or label, optional)</Label>
                  <Input
                    value={routeNode}
                    onChange={(e) => setRouteNode(e.target.value)}
                    placeholder="Leave empty to match any router node"
                    className="mt-1"
                  />
                </div>
              </div>
            )}

            {metrics.includes("action_taken") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-teal-500"></span>
                  Action Taken Config
                </div>
                <p className="text-xs text-gray-500">
                  Checks that a specific side-effect node ran successfully. Provide a node
                  or a node type.
                </p>
                <div>
                  <Label className="text-xs">Node (id or label)</Label>
                  <Input
                    value={actionNode}
                    onChange={(e) => setActionNode(e.target.value)}
                    placeholder="e.g. Create Zendesk Ticket"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">Node Type</Label>
                  <Input
                    value={actionNodeType}
                    onChange={(e) => setActionNodeType(e.target.value)}
                    placeholder="e.g. zendeskTicketNode"
                    className="mt-1"
                  />
                </div>
                <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div>
                    <div className="text-xs font-medium">Must fire</div>
                    <div className="text-xs text-gray-500">
                      Turn off to assert the node did NOT run
                    </div>
                  </div>
                  <Switch checked={actionShouldFire} onCheckedChange={setActionShouldFire} />
                </div>
              </div>
            )}

            {metrics.includes("llm_judge") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-pink-500"></span>
                  LLM Judge Config
                </div>
                <p className="text-xs text-gray-500">
                  Grades the answer against a rubric you write. One criterion per judge works best.
                </p>
                <div>
                  <Label className="text-xs">Rubric *</Label>
                  <Textarea
                    value={judgeRubric}
                    onChange={(e) => setJudgeRubric(e.target.value)}
                    placeholder="e.g. Score 1.0 if the answer is polite and offers a next step, 0.0 otherwise."
                    rows={4}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">LLM Provider</Label>
                  <Select value={judgeProviderId} onValueChange={setJudgeProviderId}>
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
                  <Label className="text-xs">Min Score (0-1)</Label>
                  <Input
                    value={judgeMinScore}
                    onChange={(e) => setJudgeMinScore(e.target.value)}
                    className="mt-1"
                    placeholder="0.5"
                  />
                  {judgeScoreInvalid && (
                    <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
                  )}
                </div>
                <div>
                  <Label className="text-xs">Grounding Source Field (optional)</Label>
                  <Input
                    value={judgeSourceField}
                    onChange={(e) => setJudgeSourceField(e.target.value)}
                    placeholder="e.g. trace.retrievals"
                    className="mt-1 font-mono text-xs"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    Dotted path into the run to check the answer against (e.g. knowledge-base
                    retrievals).
                  </p>
                </div>
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
