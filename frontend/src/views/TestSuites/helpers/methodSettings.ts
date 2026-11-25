import type { EvaluationFormData } from "./evaluationForm";
import type { EvaluationAgentInfo, ToolUsagePerToolCheck, ToolUsageRule } from "@/interfaces/testEvaluation.interface";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";

// The older methods' settings, which the evaluation editor keeps as they are.
export type MethodSettingsValue = Omit<
  EvaluationFormData,
  | "name"
  | "description"
  | "category"
  | "suiteId"
  | "workflowId"
  | "metrics"
  | "inputMetadataText"
  | "useMemory"
  | "checks"
  | "checksProviderId"
>;

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

export type GradingSourceSelection =
  | "expected_output"
  | "kb_retrievals"
  | "conversation_context"
  | "tool_events"
  | "none"
  | "legacy";

// Starting settings: what an evaluation was saved with, or each method's defaults.
export const methodDefaults = (
  initial: Partial<EvaluationFormData> | undefined,
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
  toolRules: initial?.toolRules ?? [],
  notContainsText: initial?.notContainsText ?? "",
  fieldEqualsField: initial?.fieldEqualsField ?? "",
  fieldEqualsExpected: initial?.fieldEqualsExpected ?? "",
  routeRules: initial?.routeRules ?? [],
  actionRules: initial?.actionRules ?? [],
  judgeRules: initial?.judgeRules ?? [],
  judgeProviderId: initial?.judgeProviderId ?? providers[0]?.id ?? "",
});
