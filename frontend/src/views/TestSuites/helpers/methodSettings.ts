import type { EvaluationWizardData } from "../components/EvaluationWizard";
import type {
  ActionRuleDraft,
  EvaluationAgentInfo,
  EvaluationRouterInfo,
  RouteRuleDraft,
  ToolUsagePerToolCheck,
  ToolUsageRule,
} from "@/interfaces/testEvaluation.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import { scopeTargetIncomplete } from "./ruleScope";
import { newToolRule } from "../components/ToolUsageRuleBuilder";
import { newRouteRule } from "../components/RouteRulesBuilder";
import { newActionRule } from "../components/ActionRulesBuilder";
import { newJudgeRule } from "../components/JudgeRulesBuilder";

// The settings of the 12 methods, shared by the wizard and the evaluation editor.
export type MethodSettingsValue = Omit<
  EvaluationWizardData,
  | "name"
  | "description"
  | "suiteId"
  | "workflowId"
  | "metrics"
  | "inputMetadataText"
  | "useMemory"
  | "checks"
  | "checksProviderId"
>;

// Methods with settings to fill in after they are picked.
export const CONFIG_METRICS = [
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
export const isValidScore = (text: string): boolean => {
  if (text.trim() === "") return true;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 && value <= 1;
};

export interface MethodCatalog {
  agents: EvaluationAgentInfo[];
  routers: EvaluationRouterInfo[];
}

// A legacy name that never resolved to a catalogue id blocks saving.
const toolRuleInvalid = (rule: ToolUsageRule, agents: EvaluationAgentInfo[]): boolean => {
  const catalogLoaded = agents.length > 0;
  const toolIds = new Set(agents.flatMap((agent) => agent.tools.map((tool) => tool.id)));
  const agentIds = new Set(agents.map((agent) => agent.id));
  const unresolved =
    catalogLoaded &&
    (rule.tool_ids.some((id) => !toolIds.has(id)) ||
      (Boolean(rule.agent_id) && !agentIds.has(rule.agent_id as string)));
  return (rule.operator !== "only" && rule.tool_ids.length === 0) || unresolved || scopeTargetIncomplete(rule);
};

// With a catalogue a fresh rule must pick a router; legacy free-text rules only need the route.
export const routeRuleInvalid = (rule: RouteRuleDraft, routers: EvaluationRouterInfo[]): boolean => {
  const inCatalog = routers.some((router) => router.id === rule.router);
  const isLegacyValue =
    routers.length > 0 &&
    ((Boolean(rule.router) && !inCatalog) || (!rule.router && Boolean(rule.expected)));
  const usesDropdowns = routers.length > 0 && !isLegacyValue;
  if (usesDropdowns && !rule.router.trim()) return true;
  if (scopeTargetIncomplete(rule)) return true;
  return !rule.expected.trim();
};

export const actionRuleInvalid = (rule: ActionRuleDraft): boolean =>
  (!rule.node.trim() && !rule.nodeType.trim()) || scopeTargetIncomplete(rule);

/** Whether the picked methods' settings can be saved. */
export const methodSettingsComplete = (
  metrics: string[],
  value: MethodSettingsValue,
  catalog: MethodCatalog,
): boolean => {
  if (metrics.includes("not_contains") && !value.notContainsText.trim()) return false;
  if (metrics.includes("route_taken")) {
    if (value.routeRules.length === 0 || value.routeRules.some((rule) => routeRuleInvalid(rule, catalog.routers))) {
      return false;
    }
  }
  if (metrics.includes("action_taken")) {
    if (value.actionRules.length === 0 || value.actionRules.some(actionRuleInvalid)) return false;
  }
  if (
    metrics.includes("tool_used") &&
    (value.toolRules.length === 0 || value.toolRules.some((rule) => toolRuleInvalid(rule, catalog.agents)))
  ) {
    return false;
  }
  if (metrics.includes("nli_eval") && !isValidScore(value.nliMinEntailScore)) return false;
  if (metrics.includes("provenance_eval") && !isValidScore(value.provMinScore)) return false;
  if (
    metrics.includes("llm_judge") &&
    (value.judgeRules.length === 0 ||
      value.judgeRules.some((rule) => !rule.rubric.trim() || !isValidScore(rule.minScore)))
  ) {
    return false;
  }
  return true;
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

/** Legacy tool and agent names rewritten to catalogue ids; the same array when nothing changed. */
export const remapToolRuleNames = (rules: ToolUsageRule[], catalog: EvaluationAgentInfo[]): ToolUsageRule[] => {
  if (catalog.length === 0 || rules.length === 0) return rules;
  const toolMap = buildToolNameToId(catalog);
  const agentMap = buildAgentNameToId(catalog);
  const allToolIds = [...new Set(catalog.flatMap((a) => a.tools.map((t) => t.id)))];
  let changed = false;
  const remapped = rules.map((rule) => {
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
      tool_ids.length !== rule.tool_ids.length ||
      tool_ids.some((id, i) => id !== rule.tool_ids[i]) ||
      agent_id !== rule.agent_id ||
      per_tool !== rule.per_tool
    ) {
      changed = true;
      return { ...rule, tool_ids, agent_id, per_tool };
    }
    return rule;
  });
  return changed ? remapped : rules;
};

export interface MethodDef {
  value: string;
  label: string;
  description: string;
}

export const METRIC_GROUPS: { label: string; metrics: MethodDef[] }[] = [
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

export const NLI_MODEL_OPTIONS = [
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

export const GRADING_SOURCE_OPTIONS: {
  value: Exclude<GradingSourceSelection, "none" | "legacy">;
  label: string;
}[] = [
  { value: "kb_retrievals", label: "Retrieved context" },
  { value: "expected_output", label: "Expected answer" },
];

// Ready-made rubrics: one click fills the rubric text and picks the matching
// grading source. The user can still edit the text afterwards.
// Anchors put "partial" at 0.4 so it lands under the default 0.5 threshold — a
// partially satisfied criterion should not pass unless the user lowers the bar.
export const RUBRIC_PRESETS: {
  key: string;
  label: string;
  rubric: string;
  sourceType: GradingSourceSelection;
}[] = [
  {
    key: "retrieval_relevance",
    label: "Retrieval relevance",
    rubric:
      "Judge whether the SOURCE passages are relevant to answering the QUESTION. " +
      "Ignore the answer itself. Score 1.0 when the passages contain the " +
      "information needed to answer the question, 0.4 when they are only " +
      "partially relevant, and 0.0 when they are unrelated to the question. " +
      "Intermediate scores are allowed.",
    sourceType: "kb_retrievals",
  },
  {
    key: "completeness",
    label: "Completeness",
    rubric:
      "Judge whether the ANSWER fully addresses every part of the QUESTION. " +
      "Ignore style and tone. Score 1.0 when every part is answered, 0.4 when " +
      "only some parts are answered, and 0.0 when the answer misses the point " +
      "of the question. Intermediate scores are allowed.",
    sourceType: "none",
  },
  {
    key: "helpfulness",
    label: "Helpfulness",
    rubric:
      "Judge whether the ANSWER moves the user toward resolving their request. " +
      "Ignore length and formatting. Score 1.0 when it resolves the request or " +
      "gives a clear, correct next step, 0.4 when it is on topic but leaves the " +
      "user without a usable way forward, and 0.0 when it is unhelpful or " +
      "off-topic. Intermediate scores are allowed.",
    sourceType: "none",
  },
  {
    key: "politeness",
    label: "Politeness & tone",
    rubric:
      "Judge whether the ANSWER is polite, professional and helpful in tone. " +
      "Ignore factual correctness. Score 1.0 when it is courteous and " +
      "constructive, 0.4 when it is neutral or curt, and 0.0 when it is rude, " +
      "dismissive or inappropriate. Intermediate scores are allowed.",
    sourceType: "none",
  },
];

// Starting settings: what an evaluation was saved with, or each method's defaults.
export const methodDefaults = (
  initial: Partial<EvaluationWizardData> | undefined,
  providers: LLMProviderMinimal[],
): MethodSettingsValue => ({
  nliModelName: initial?.nliModelName ?? "cross-encoder/nli-deberta-v3-base",
  nliMinEntailScore: initial?.nliMinEntailScore ?? "0.5",
  nliFailOnContradiction: initial?.nliFailOnContradiction ?? false,
  nliEvidenceSource: initial?.nliEvidenceSource ?? "expected_output",
  nliEvidenceField: initial?.nliEvidenceField ?? "",
  provMode: initial?.provMode ?? "embeddings",
  provContextSource: initial?.provContextSource ?? "kb_retrievals",
  provContextField: initial?.provContextField ?? "",
  provEmbeddingType: initial?.provEmbeddingType ?? "huggingface",
  provEmbeddingModelName: initial?.provEmbeddingModelName ?? "all-MiniLM-L6-v2",
  provMinScore: initial?.provMinScore ?? "0.5",
  provFailOnViolation: initial?.provFailOnViolation ?? false,
  provLlmProviderId: initial?.provLlmProviderId ?? providers[0]?.id ?? "",
  provLlmJudgeSystemPromptSuffix: initial?.provLlmJudgeSystemPromptSuffix ?? "",
  // Every rule builder opens on one blank rule, so picking a technique always
  // shows what there is to fill in rather than an empty panel.
  toolRules: initial?.toolRules?.length ? initial.toolRules : [newToolRule()],
  notContainsText: initial?.notContainsText ?? "",
  fieldEqualsField: initial?.fieldEqualsField ?? "",
  fieldEqualsExpected: initial?.fieldEqualsExpected ?? "",
  routeRules: initial?.routeRules?.length ? initial.routeRules : [newRouteRule()],
  actionRules: initial?.actionRules?.length ? initial.actionRules : [newActionRule()],
  judgeRules: initial?.judgeRules?.length ? initial.judgeRules : [newJudgeRule()],
  judgeProviderId: initial?.judgeProviderId ?? providers[0]?.id ?? "",
});
