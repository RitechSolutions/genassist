import React, { useEffect, useMemo, useState } from "react";
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
import { ChevronLeft, ChevronRight, Check, Database, Workflow, Settings, SlidersHorizontal, ClipboardCheck } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { TestSuite } from "@/interfaces/testSuite.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type {
  EvaluationActionNodeInfo,
  EvaluationAgentInfo,
  EvaluationRouterInfo,
  ToolUsagePerToolCheck,
  ToolUsageRule,
} from "@/interfaces/testEvaluation.interface";
import { getEvaluationToolCatalog } from "@/services/testEvaluations";
import { listTestCases } from "@/services/testSuites";
import type { TestCase } from "@/interfaces/testSuite.interface";
import { ToolUsageRuleBuilder, type RuleConversation } from "./ToolUsageRuleBuilder";

// Group imported multi-turn cases into conversations for specific-turn targeting.
const deriveConversations = (cases: TestCase[]): RuleConversation[] => {
  const groups = new Map<string, TestCase[]>();
  for (const testCase of cases) {
    if (!testCase.source_conversation_id) continue;
    const group = groups.get(testCase.source_conversation_id) ?? [];
    group.push(testCase);
    groups.set(testCase.source_conversation_id, group);
  }
  return Array.from(groups.entries()).map(([id, turns]) => {
    const sorted = [...turns].sort((a, b) => (a.turn_index ?? 0) - (b.turn_index ?? 0));
    return {
      id,
      label: `Conversation ${id.slice(0, 8)} (${sorted.length} turns)`,
      turns: sorted.map((turn) => ({
        caseId: turn.id,
        turnIndex: turn.turn_index ?? 0,
        label: `Turn ${(turn.turn_index ?? 0) + 1}`,
      })),
    };
  });
};

// Case-insensitive name/label/id -> id map, keeping only unambiguous keys (a name
// shared by two tools is left unmapped, mirroring the backend, so it can't silently
// resolve to the wrong tool).
const uniqueNameToId = (entries: { id: string; keys: (string | undefined)[] }[]): Map<string, string> => {
  const idsByKey = new Map<string, Set<string>>();
  for (const entry of entries) {
    for (const key of entry.keys) {
      if (!key) continue;
      const normalized = key.toLowerCase();
      const ids = idsByKey.get(normalized) ?? new Set<string>();
      ids.add(entry.id);
      idsByKey.set(normalized, ids);
    }
  }
  const map = new Map<string, string>();
  for (const [key, ids] of idsByKey) {
    if (ids.size === 1) map.set(key, [...ids][0]);
  }
  return map;
};

const buildToolNameToId = (catalog: EvaluationAgentInfo[]): Map<string, string> =>
  uniqueNameToId(
    catalog.flatMap((agent) =>
      agent.tools.map((tool) => ({ id: tool.id, keys: [tool.id, tool.name, tool.label] })),
    ),
  );

const buildAgentNameToId = (catalog: EvaluationAgentInfo[]): Map<string, string> =>
  uniqueNameToId(catalog.map((agent) => ({ id: agent.id, keys: [agent.id, agent.label] })));

// Rewrite per_tool keys (legacy tool names) to canonical ids, matching tool_ids.
const remapPerToolKeys = (
  perTool: Record<string, ToolUsagePerToolCheck> | undefined,
  toolMap: Map<string, string>,
): Record<string, ToolUsagePerToolCheck> | undefined => {
  if (!perTool || Object.keys(perTool).length === 0) return perTool;
  let changed = false;
  const remapped: Record<string, ToolUsagePerToolCheck> = {};
  for (const [key, value] of Object.entries(perTool)) {
    const mapped = toolMap.get(key.toLowerCase()) ?? key;
    if (mapped !== key) changed = true;
    remapped[mapped] = value;
  }
  return changed ? remapped : perTool;
};

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
      { value: "not_contains", label: "Does Not Contain", description: "Output must not contain the specified text" },
      { value: "json_match", label: "JSON Match", description: "Output matches the expected JSON structure and values" },
      { value: "field_equals", label: "Field Equals", description: "A specific field in the output equals an expected value" },
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
  "not_contains",
  "field_equals",
  "nli_eval",
  "provenance_eval",
  "tool_used",
  "route_taken",
  "action_taken",
  "llm_judge",
];

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

export type GradingSourceSelection =
  | "expected_output"
  | "kb_retrievals"
  | "conversation_context"
  | "tool_events"
  | "none"
  | "legacy";

const GRADING_SOURCE_OPTIONS: {
  value: Exclude<GradingSourceSelection, "none" | "legacy">;
  label: string;
}[] = [
  { value: "kb_retrievals", label: "Retrieved context" },
  { value: "expected_output", label: "Expected answer" },
];

const GradingSourceSelect: React.FC<{
  value: GradingSourceSelection;
  onChange: (value: GradingSourceSelection) => void;
  allowRubricOnly?: boolean;
  legacyField?: string;
}> = ({ value, onChange, allowRubricOnly = false, legacyField }) => (
  <Select value={value} onValueChange={(next) => onChange(next as GradingSourceSelection)}>
    <SelectTrigger className="mt-1">
      <SelectValue placeholder="Select source" />
    </SelectTrigger>
    <SelectContent>
      {allowRubricOnly && <SelectItem value="none">No source — rubric only</SelectItem>}
      {GRADING_SOURCE_OPTIONS.map((source) => (
        <SelectItem key={source.value} value={source.value}>
          {source.label}
        </SelectItem>
      ))}
      {legacyField && (
        <SelectItem value="legacy">Legacy configured source ({legacyField})</SelectItem>
      )}
    </SelectContent>
  </Select>
);

type WizardStep = "workflow" | "basics" | "data" | "validation" | "configure";

const STEPS: { key: WizardStep; label: string; icon: React.ElementType }[] = [
  { key: "workflow", label: "Workflow", icon: Workflow },
  { key: "basics", label: "Basics", icon: ClipboardCheck },
  { key: "data", label: "Data Source", icon: Database },
  { key: "validation", label: "Validation", icon: Settings },
  { key: "configure", label: "Configure", icon: SlidersHorizontal },
];

// Compare two workflow version strings numerically (e.g. "10" > "9", "1.2" > "1.1").
// Returns a - b, so the highest version sorts last with a plain ascending sort.
const compareVersions = (a: string, b: string): number => {
  const parse = (v: string) => v.split(".").map((part) => parseInt(part.replace(/\D/g, ""), 10) || 0);
  const pa = parse(a);
  const pb = parse(b);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i++) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
};

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
      <p className="text-xs text-muted-foreground mt-0.5">{metric.description}</p>
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
  routeExpected: string;
  routeNode: string;
  actionNode: string;
  actionNodeType: string;
  actionShouldFire: boolean;
  judgeRubric: string;
  judgeMinScore: string;
  judgeProviderId: string;
  judgeSourceType: GradingSourceSelection;
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
  const [expandedWorkflowName, setExpandedWorkflowName] = useState<string | null>(null);

  // Group workflows by name, newest version first, so each name shows its current
  // version with older versions nested beneath it.
  const workflowGroups = useMemo(() => {
    const byName = new Map<string, WorkflowMinimal[]>();
    for (const wf of workflows) {
      if (!wf.id) continue;
      const existing = byName.get(wf.name) ?? [];
      existing.push(wf);
      byName.set(wf.name, existing);
    }
    return Array.from(byName.entries())
      .map(([wfName, versions]) => ({
        name: wfName,
        versions: [...versions].sort((a, b) => compareVersions(b.version, a.version)),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [workflows]);

  // Form state
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [suiteId, setSuiteId] = useState(initialData?.suiteId ?? "none");
  const [workflowId, setWorkflowId] = useState(
    lockedWorkflowId ?? initialData?.workflowId ?? "none",
  );
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
  const [nliEvidenceSource, setNliEvidenceSource] = useState<GradingSourceSelection>(
    initialData?.nliEvidenceSource ?? "expected_output"
  );
  const [nliEvidenceField] = useState(initialData?.nliEvidenceField ?? "");

  // Provenance config
  const [provMode, setProvMode] = useState<"embeddings" | "llm">(initialData?.provMode ?? "embeddings");
  const [provContextSource, setProvContextSource] = useState<GradingSourceSelection>(
    initialData?.provContextSource ?? "kb_retrievals"
  );
  const [provContextField] = useState(initialData?.provContextField ?? "");
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

  // Tool Usage rules + workflow tool catalogue
  const [toolRules, setToolRules] = useState<ToolUsageRule[]>(initialData?.toolRules ?? []);
  const [toolCatalog, setToolCatalog] = useState<EvaluationAgentInfo[]>([]);
  const [catalogRouters, setCatalogRouters] = useState<EvaluationRouterInfo[]>([]);
  const [catalogActionNodes, setCatalogActionNodes] = useState<EvaluationActionNodeInfo[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const toolUsageSelected = metrics.includes("tool_used");
  // Route and Action dropdowns are populated from the same catalogue.
  const needsCatalog =
    toolUsageSelected ||
    metrics.includes("route_taken") ||
    metrics.includes("action_taken");

  // Fall back to the dataset's default workflow when none is explicitly chosen,
  // so the tool catalogue still loads.
  const selectedSuite = suites.find((s) => s.id === suiteId);
  const effectiveWorkflowId =
    workflowId && workflowId !== "none" ? workflowId : selectedSuite?.workflow_id;

  useEffect(() => {
    if (!needsCatalog || !effectiveWorkflowId) {
      setToolCatalog([]);
      setCatalogRouters([]);
      setCatalogActionNodes([]);
      return;
    }
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError(null);
    getEvaluationToolCatalog(effectiveWorkflowId)
      .then((catalog) => {
        if (cancelled) return;
        setToolCatalog(catalog.agents ?? []);
        setCatalogRouters(catalog.routers ?? []);
        setCatalogActionNodes(catalog.action_nodes ?? []);
      })
      .catch(() => {
        if (!cancelled) setCatalogError("Failed to load workflow nodes");
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [needsCatalog, effectiveWorkflowId]);

  // Imported conversations for specific-turn targeting, derived from the suite's cases.
  const [conversations, setConversations] = useState<RuleConversation[]>([]);
  useEffect(() => {
    if (!toolUsageSelected || !suiteId) {
      setConversations([]);
      return;
    }
    let cancelled = false;
    listTestCases(suiteId)
      .then((cases) => {
        if (!cancelled) setConversations(deriveConversations(cases));
      })
      .catch(() => {
        if (!cancelled) setConversations([]);
      });
    return () => {
      cancelled = true;
    };
  }, [toolUsageSelected, suiteId]);

  // When the catalogue loads, rewrite any legacy tool/agent NAMES (from an old
  // evaluation) to canonical ids so they aren't later saved as if they were ids.
  useEffect(() => {
    if (toolCatalog.length === 0 || toolRules.length === 0) return;
    const toolMap = buildToolNameToId(toolCatalog);
    const agentMap = buildAgentNameToId(toolCatalog);
    const allToolIds = [...new Set(toolCatalog.flatMap((a) => a.tools.map((t) => t.id)))];
    let changed = false;
    const remapped = toolRules.map((rule) => {
      // A legacy "any tool" rule (any + no tools) expands to every workflow tool.
      const isAnyToolMarker = rule.operator === "any" && rule.tool_ids.length === 0;
      const tool_ids = isAnyToolMarker
        ? allToolIds
        : rule.tool_ids.map((id) => toolMap.get(id.toLowerCase()) ?? id);
      const agent_id = rule.agent_id
        ? agentMap.get(rule.agent_id.toLowerCase()) ?? rule.agent_id
        : rule.agent_id;
      const per_tool = remapPerToolKeys(rule.per_tool, toolMap);
      if (
        tool_ids.some((id, i) => id !== rule.tool_ids[i]) ||
        agent_id !== rule.agent_id ||
        per_tool !== rule.per_tool
      ) {
        changed = true;
        return { ...rule, tool_ids, agent_id, per_tool };
      }
      return rule;
    });
    if (changed) setToolRules(remapped);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolCatalog]);

  // Does Not Contain config
  const [notContainsText, setNotContainsText] = useState(initialData?.notContainsText ?? "");

  // Field Equals config
  const [fieldEqualsField, setFieldEqualsField] = useState(initialData?.fieldEqualsField ?? "");
  const [fieldEqualsExpected, setFieldEqualsExpected] = useState(
    initialData?.fieldEqualsExpected ?? ""
  );

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
  const [judgeSourceType, setJudgeSourceType] = useState<GradingSourceSelection>(
    initialData?.judgeSourceType ?? "none"
  );
  const [judgeSourceField] = useState(initialData?.judgeSourceField ?? "");

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  // Canonical id sets to catch legacy names that never resolved (block save on them).
  const catalogLoaded = toolCatalog.length > 0;
  const catalogToolIds = new Set(toolCatalog.flatMap((a) => a.tools.map((t) => t.id)));
  const catalogAgentIds = new Set(toolCatalog.map((a) => a.id));

  const ruleHasUnresolvedRef = (rule: ToolUsageRule): boolean => {
    if (!catalogLoaded) return false;
    const toolUnresolved = rule.tool_ids.some((id) => !catalogToolIds.has(id));
    const agentUnresolved = Boolean(rule.agent_id) && !catalogAgentIds.has(rule.agent_id as string);
    return toolUnresolved || agentUnresolved;
  };

  const ruleSpecificTurnIncomplete = (rule: ToolUsageRule): boolean =>
    rule.scope === "specific_turn" &&
    (!rule.target_source_conversation_id || rule.target_turn_index == null);

  const toolRulesInvalid =
    toolUsageSelected &&
    (toolRules.length === 0 ||
      toolRules.some(
        (rule) =>
          (rule.operator !== "only" && rule.tool_ids.length === 0) ||
          ruleHasUnresolvedRef(rule) ||
          ruleSpecificTurnIncomplete(rule),
      ));
  const nliScoreInvalid = metrics.includes("nli_eval") && !isValidScore(nliMinEntailScore);
  const provScoreInvalid = metrics.includes("provenance_eval") && !isValidScore(provMinScore);
  const judgeScoreInvalid = metrics.includes("llm_judge") && !isValidScore(judgeMinScore);

  // Route/Action dropdowns use the catalogue; fall back to free text only when the
  // catalogue is unavailable or a saved value predates it (an unmatched legacy id).
  const selectedRouter = catalogRouters.find((r) => r.id === routeNode);
  // Free text is only for a config the catalogue can't match: a saved router id that
  // is gone, or an old "any router" config (expected set with no router chosen).
  const routeLegacyValue =
    catalogRouters.length > 0 &&
    ((Boolean(routeNode) && !selectedRouter) || (!routeNode && Boolean(routeExpected)));
  const useRouteDropdowns = catalogRouters.length > 0 && !routeLegacyValue;
  const actionNodeInCatalog = catalogActionNodes.some((n) => n.id === actionNode);
  const actionLegacyValue =
    (Boolean(actionNode) && catalogActionNodes.length > 0 && !actionNodeInCatalog) ||
    Boolean(actionNodeType);
  const useActionDropdown = catalogActionNodes.length > 0 && !actionLegacyValue;

  const isConfigureStepValid = (): boolean => {
    if (metrics.includes("llm_judge") && !judgeRubric.trim()) return false;
    if (metrics.includes("not_contains") && !notContainsText.trim()) return false;
    if (metrics.includes("route_taken")) {
      if (useRouteDropdowns && !routeNode.trim()) return false;
      if (!routeExpected.trim()) return false;
    }
    if (metrics.includes("action_taken") && !actionNode.trim() && !actionNodeType.trim()) return false;
    if (toolRulesInvalid || nliScoreInvalid || provScoreInvalid || judgeScoreInvalid) return false;
    return true;
  };

  const canProceed = (): boolean => {
    switch (step) {
      case "workflow":
        return workflowId.length > 0;
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
        nliEvidenceSource,
        nliEvidenceField,
        provMode,
        provContextSource,
        provContextField,
        provEmbeddingType,
        provEmbeddingModelName,
        provMinScore,
        provFailOnViolation,
        provLlmProviderId,
        provLlmJudgeSystemPromptSuffix,
        toolRules,
        notContainsText,
        fieldEqualsField,
        fieldEqualsExpected,
        routeExpected,
        routeNode,
        actionNode,
        actionNodeType,
        actionShouldFire,
        judgeRubric,
        judgeMinScore,
        judgeProviderId,
        judgeSourceType,
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
    setStep("workflow");
    setName("");
    setDescription("");
    setSuiteId("none");
    setWorkflowId(lockedWorkflowId ?? "none");
    setExpandedWorkflowName(null);
    setMetrics(["exact_match"]);
    setInputMetadataText("{}");
    setIsMetadataValid(true);
    setUseMemory(false);
    setNliModelName("cross-encoder/nli-deberta-v3-base");
    setNliMinEntailScore("0.5");
    setNliFailOnContradiction(false);
    setNliEvidenceSource("expected_output");
    setProvMode("embeddings");
    setProvContextSource("kb_retrievals");
    setProvEmbeddingType("huggingface");
    setProvEmbeddingModelName("all-MiniLM-L6-v2");
    setProvMinScore("0.5");
    setProvFailOnViolation(false);
    setProvLlmProviderId(providers[0]?.id ?? "");
    setProvLlmJudgeSystemPromptSuffix("");
    setToolRules([]);
    setNotContainsText("");
    setFieldEqualsField("");
    setFieldEqualsExpected("");
    setRouteExpected("");
    setRouteNode("");
    setActionNode("");
    setActionNodeType("");
    setActionShouldFire(true);
    setJudgeRubric("");
    setJudgeMinScore("0.5");
    setJudgeProviderId(providers[0]?.id ?? "");
    setJudgeSourceType("none");
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
      case "workflow":
        return (
          <div className="space-y-4">
            <div>
              <Label className="text-sm font-medium">Select Workflow *</Label>
              <p className="text-xs text-muted-foreground">
                Pick the workflow this evaluation runs against. The current version is shown
                first, with older versions nested below it.
              </p>
            </div>

            {lockedWorkflowId ? (
              <div className="rounded-lg border bg-muted px-4 py-3 text-sm">
                {workflows.find((wf) => wf.id === lockedWorkflowId)?.name ?? "This workflow"}
              </div>
            ) : (
              <div className="rounded-lg border p-2 space-y-0.5">
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

                {workflowGroups.map((group) => {
                  const isExpanded = expandedWorkflowName === group.name;
                  const selectedInGroup = group.versions.find((wf) => wf.id === workflowId);
                  return (
                    <div key={group.name}>
                      {/* Workflow name = collapsible header; opening it selects the current
                          version (collapsed by default to keep the list short). */}
                      <button
                        type="button"
                        onClick={() => {
                          if (isExpanded) {
                            setExpandedWorkflowName(null);
                          } else {
                            setExpandedWorkflowName(group.name);
                            setWorkflowId(group.versions[0].id);
                          }
                        }}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors",
                          selectedInGroup ? "bg-primary/10" : "hover:bg-muted",
                        )}
                      >
                        <ChevronRight
                          className={cn(
                            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                            isExpanded && "rotate-90",
                          )}
                        />
                        <span
                          className={cn(
                            "truncate text-sm font-semibold",
                            selectedInGroup ? "text-primary" : "text-foreground",
                          )}
                        >
                          {group.name}
                        </span>
                        {!isExpanded && selectedInGroup && (
                          <span className="ml-auto shrink-0 text-xs font-medium text-primary">
                            v{selectedInGroup.version}
                          </span>
                        )}
                      </button>
                      {isExpanded && (
                        <div className="relative py-0.5 pl-[30px]">
                          <div className="absolute bottom-0 left-[18px] top-0 w-px bg-border" />
                          {group.versions.map((wf, idx) => {
                            const selected = workflowId === wf.id;
                            return (
                              <button
                                key={wf.id}
                                type="button"
                                onClick={() => setWorkflowId(wf.id)}
                                className={cn(
                                  "flex w-full items-center gap-2 rounded-md px-2.5 py-[6px] text-sm transition-colors",
                                  selected
                                    ? "bg-primary/10 font-semibold text-primary"
                                    : "font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                                )}
                              >
                                <span className="truncate">v{wf.version}</span>
                                {idx === 0 && (
                                  <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                                    Current
                                  </span>
                                )}
                                {selected && <Check className="ml-auto h-4 w-4 shrink-0" />}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
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
              <p className="text-xs text-muted-foreground mt-1">
                Choose the dataset containing your test cases
              </p>
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
                <div className="text-xs text-muted-foreground">
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
              <p className="text-xs text-muted-foreground">
                Select at least one method to validate your agent's outputs
              </p>
            </div>
            {METRIC_GROUPS.map((group) => (
              <div key={group.label} className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
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
              <div className="text-center py-8 text-muted-foreground">
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
                <p className="text-xs text-muted-foreground">
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
                  <Label className="text-xs">Compare answer with</Label>
                  <GradingSourceSelect
                    value={nliEvidenceSource}
                    onChange={setNliEvidenceSource}
                    legacyField={nliEvidenceField}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Expected answer checks consistency with the reference answer; Retrieved
                    context checks support from what the agent retrieved this run.
                  </p>
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
                <p className="text-xs text-muted-foreground">
                  Uses workflow output as answer and expected output as context.
                </p>
                <div>
                  <Label className="text-xs">Grounding source</Label>
                  <GradingSourceSelect
                    value={provContextSource}
                    onChange={setProvContextSource}
                    legacyField={provContextField}
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Retrieved context means only what the agent actually retrieved this run
                    (KB passages and retrieval-tool results), not the whole knowledge base.
                  </p>
                </div>
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
                  Tool Usage
                </div>
                <p className="text-xs text-muted-foreground">
                  Add rules about which tools an agent should or should not use. Agents and
                  tools come from the selected workflow.
                </p>
                {!effectiveWorkflowId ? (
                  <p className="text-sm text-muted-foreground">
                    Select a workflow in the Data Source step to load its agents and tools.
                  </p>
                ) : (
                  <ToolUsageRuleBuilder
                    rules={toolRules}
                    onChange={setToolRules}
                    catalog={toolCatalog}
                    conversations={conversations}
                    loading={catalogLoading}
                    error={catalogError}
                  />
                )}
              </div>
            )}

            {metrics.includes("not_contains") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                  Does Not Contain Config
                </div>
                <p className="text-xs text-muted-foreground">
                  Fails the run if any of these phrases appears in the output. One phrase
                  per line. Matching is case-insensitive.
                </p>
                <div>
                  <Label className="text-xs">Forbidden Phrases *</Label>
                  <Textarea
                    value={notContainsText}
                    onChange={(e) => setNotContainsText(e.target.value)}
                    placeholder={"e.g.\ncompetitor name\nsocial security number"}
                    rows={3}
                    className="mt-1"
                  />
                </div>
              </div>
            )}

            {metrics.includes("field_equals") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                  Field Equals Config
                </div>
                <p className="text-xs text-muted-foreground">
                  Checks that a value from the run equals an expected value. Values are
                  compared as text.
                </p>
                <div>
                  <Label className="text-xs">Field</Label>
                  <Input
                    value={fieldEqualsField}
                    onChange={(e) => setFieldEqualsField(e.target.value)}
                    placeholder="Leave empty for the final output, or e.g. outputs.status"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">Expected Value</Label>
                  <Input
                    value={fieldEqualsExpected}
                    onChange={(e) => setFieldEqualsExpected(e.target.value)}
                    placeholder="Leave empty to use the test case's expected output"
                    className="mt-1"
                  />
                </div>
              </div>
            )}

            {metrics.includes("route_taken") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  Route Taken Config
                </div>
                <p className="text-xs text-muted-foreground">
                  Checks that a router node selected the expected branch.
                </p>
                {useRouteDropdowns ? (
                  <>
                    <div>
                      <Label className="text-xs">Router *</Label>
                      <Select
                        value={routeNode}
                        onValueChange={(next) => {
                          setRouteNode(next);
                          setRouteExpected("");
                        }}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="Select a router" />
                        </SelectTrigger>
                        <SelectContent>
                          {catalogRouters.map((router) => (
                            <SelectItem key={router.id} value={router.id}>
                              {router.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {selectedRouter && selectedRouter.branches.length > 0 && (
                      <div>
                        <Label className="text-xs">Expected Branch *</Label>
                        <Select value={routeExpected} onValueChange={setRouteExpected}>
                          <SelectTrigger className="mt-1">
                            <SelectValue placeholder="Select a branch" />
                          </SelectTrigger>
                          <SelectContent>
                            {selectedRouter.branches.map((branch) => (
                              <SelectItem key={branch.value} value={branch.value}>
                                {branch.destination
                                  ? `${branch.value} → ${branch.destination}`
                                  : branch.value}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    {selectedRouter && selectedRouter.branches.length === 0 && (
                      <div>
                        <Label className="text-xs">Expected Route *</Label>
                        <Input
                          value={routeExpected}
                          onChange={(e) => setRouteExpected(e.target.value)}
                          placeholder="e.g. escalate"
                          className="mt-1"
                        />
                      </div>
                    )}
                  </>
                ) : (
                  <>
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
                  </>
                )}
              </div>
            )}

            {metrics.includes("action_taken") && (
              <div className="border rounded-lg p-4 space-y-3">
                <div className="text-sm font-semibold flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-teal-500"></span>
                  Action Taken Config
                </div>
                <p className="text-xs text-muted-foreground">
                  Checks whether a specific workflow node ran successfully.
                </p>
                {useActionDropdown ? (
                  <div>
                    <Label className="text-xs">Node *</Label>
                    <Select
                      value={actionNode}
                      onValueChange={(next) => {
                        setActionNode(next);
                        setActionNodeType("");
                      }}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select a node" />
                      </SelectTrigger>
                      <SelectContent>
                        {catalogActionNodes.map((node) => (
                          <SelectItem key={node.id} value={node.id}>
                            {node.label} ({node.type})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <>
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
                  </>
                )}
                <div className="flex items-center justify-between rounded-lg border px-3 py-2">
                  <div>
                    <div className="text-xs font-medium">Must complete</div>
                    <div className="text-xs text-muted-foreground">
                      Turn off to require that the node does not complete successfully
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
                <p className="text-xs text-muted-foreground">
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
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div>
                    <Label className="text-xs">Give the judge the retrieved context</Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Off = rubric only (style or behavior checks). On = the judge also
                      sees the KB passages the agent retrieved during the run.
                    </p>
                  </div>
                  <Switch
                    checked={judgeSourceType === "kb_retrievals"}
                    onCheckedChange={(checked) =>
                      setJudgeSourceType(checked ? "kb_retrievals" : "none")
                    }
                  />
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
