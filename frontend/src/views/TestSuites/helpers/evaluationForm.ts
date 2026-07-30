import {
  EvaluationWizardData,
  GradingSourceSelection,
} from "../components/EvaluationWizard";
import {
  TestEvaluationConfig,
  ToolUsageOperator,
  ToolUsagePerToolCheck,
  ToolUsageRule,
  ToolUsageScope,
} from "@/interfaces/testEvaluation.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";

const GRADING_SOURCES = new Set<GradingSourceSelection>([
  "expected_output",
  "kb_retrievals",
  "conversation_context",
  "tool_events",
  "none",
]);

const LEGACY_SOURCE_PRESETS: Record<string, GradingSourceSelection> = {
  reference_outputs: "expected_output",
  "trace.retrievals": "kb_retrievals",
  "trace.session": "conversation_context",
  "trace.tool_events": "tool_events",
};

const parseGradingSource = (
  config: Record<string, unknown> | undefined,
  sourceKey: string,
  legacyFieldKey: string,
  fallback: GradingSourceSelection,
): { selection: GradingSourceSelection; legacyField: string } => {
  const configured = config?.[sourceKey];
  if (typeof configured === "string" && GRADING_SOURCES.has(configured as GradingSourceSelection)) {
    return { selection: configured as GradingSourceSelection, legacyField: "" };
  }

  const legacyField = config?.[legacyFieldKey];
  if (typeof legacyField !== "string" || !legacyField) {
    return { selection: fallback, legacyField: "" };
  }

  return {
    selection: LEGACY_SOURCE_PRESETS[legacyField] ?? "legacy",
    legacyField,
  };
};

// Read back a stored per_tool map, keeping only the recognized check fields.
const parsePerTool = (
  raw: unknown,
): Record<string, ToolUsagePerToolCheck> => {
  if (!raw || typeof raw !== "object") return {};
  const out: Record<string, ToolUsagePerToolCheck> = {};
  for (const [toolId, value] of Object.entries(raw as Record<string, unknown>)) {
    const check = (value ?? {}) as Record<string, unknown>;
    out[toolId] = {
      result_not_empty: Boolean(check.result_not_empty),
      result_contains: (check.result_contains as string) ?? null,
      expected_args: (check.expected_args as Record<string, unknown>) ?? null,
    };
  }
  return out;
};

// Fold a legacy config's top-level result/argument checks into the tool's per_tool entry.
const legacyPerTool = (cfg: Record<string, unknown>): Record<string, ToolUsagePerToolCheck> => {
  const tool = cfg.tool as string | undefined;
  const hasChecks = cfg.result_not_empty || cfg.result_contains || cfg.expected_args;
  if (!tool || cfg.should_call === false || !hasChecks) return {};
  return {
    [tool]: {
      result_not_empty: Boolean(cfg.result_not_empty),
      result_contains: (cfg.result_contains as string) ?? null,
      expected_args: (cfg.expected_args as Record<string, unknown>) ?? null,
    },
  };
};

// Parse a stored tool_used config into builder rules, converting the legacy shape.
const parseToolRules = (
  cfg: Record<string, unknown> | undefined,
): ToolUsageRule[] => {
  if (!cfg) return [];
  if (Array.isArray(cfg.rules)) {
    return (cfg.rules as Record<string, unknown>[]).map((rule, index) => ({
      id: (rule.id as string) ?? `rule-${index}`,
      agent_id: (rule.agent_id as string) ?? null,
      tool_ids: Array.isArray(rule.tool_ids) ? (rule.tool_ids as string[]) : [],
      operator: (rule.operator as ToolUsageOperator) ?? "all",
      require_success: Boolean(rule.require_success),
      scope: (rule.scope as ToolUsageScope) ?? "every_turn",
      target_case_id: (rule.target_case_id as string) ?? null,
      target_source_conversation_id: (rule.target_source_conversation_id as string) ?? null,
      target_turn_index: (rule.target_turn_index as number) ?? null,
      min_calls: (rule.min_calls as number) ?? null,
      max_calls: (rule.max_calls as number) ?? null,
      per_tool: parsePerTool(rule.per_tool),
    }));
  }
  // Legacy shape: a named tool/agent, or a bare should_call ("any"/"no" tool). The
  // catalogue-load effect later expands an "any tool" rule to the workflow's tools.
  if (cfg.tool || cfg.node || "should_call" in cfg) {
    const shouldCall = cfg.should_call !== false;
    const operator: ToolUsageOperator = cfg.tool
      ? shouldCall
        ? "all"
        : "none"
      : shouldCall
        ? "any"
        : "only";
    return [
      {
        id: "legacy-tool-rule",
        agent_id: (cfg.node as string) ?? null,
        tool_ids: cfg.tool ? [cfg.tool as string] : [],
        operator,
        require_success: false,
        scope: "every_turn",
        per_tool: legacyPerTool(cfg),
      },
    ];
  }
  return [];
};

// Serialize a builder rule to the backend config, dropping empty optional fields.
const serializeToolRule = (rule: ToolUsageRule): Record<string, unknown> => ({
  id: rule.id,
  tool_ids: rule.tool_ids,
  operator: rule.operator,
  scope: rule.scope,
  ...(rule.agent_id ? { agent_id: rule.agent_id } : {}),
  ...(rule.require_success ? { require_success: true } : {}),
  ...(rule.target_case_id ? { target_case_id: rule.target_case_id } : {}),
  ...(rule.target_source_conversation_id
    ? { target_source_conversation_id: rule.target_source_conversation_id }
    : {}),
  ...(rule.target_turn_index != null ? { target_turn_index: rule.target_turn_index } : {}),
  ...(rule.min_calls != null ? { min_calls: rule.min_calls } : {}),
  ...(rule.max_calls != null ? { max_calls: rule.max_calls } : {}),
  ...(rule.per_tool && Object.keys(rule.per_tool).length ? { per_tool: rule.per_tool } : {}),
});

const parseJsonObject = (
  text: string,
): Record<string, unknown> | undefined => {
  if (!text.trim()) return undefined;
  try {
    const parsed = JSON.parse(text);
    const isPlainObject =
      parsed && typeof parsed === "object" && !Array.isArray(parsed);
    return isPlainObject ? (parsed as Record<string, unknown>) : undefined;
  } catch {
    return undefined;
  }
};

// One forbidden phrase per textarea line: trimmed, empties dropped, ASCII-case dedupe.
// The backend re-dedupes with Unicode casefold, which is the authoritative pass.
const splitForbiddenPhrases = (text: string): string[] => {
  const phrases: string[] = [];
  const seen = new Set<string>();
  for (const line of text.split("\n")) {
    const phrase = line.trim();
    const key = phrase.toLowerCase();
    if (!phrase || seen.has(key)) continue;
    seen.add(key);
    phrases.push(phrase);
  }
  return phrases;
};

// A stored not_contains config may hold the new phrases list or the legacy single text.
const forbiddenPhrasesToText = (config: Record<string, unknown> | undefined): string => {
  const phrases = config?.phrases;
  if (Array.isArray(phrases)) return phrases.join("\n");
  return (config?.text as string) ?? "";
};

// Parse the wizard's metadata textarea and fold in the "use memory" flag.
export const wizardMetadata = (
  data: EvaluationWizardData,
): Record<string, unknown> | undefined => {
  let metadata = parseJsonObject(data.inputMetadataText || "{}");
  if (data.useMemory) {
    metadata = { ...(metadata ?? {}), use_memory: true };
  } else if (metadata) {
    delete metadata["use_memory"];
  }
  return metadata;
};

export const buildTechniqueConfigs = (
  data: EvaluationWizardData,
): Record<string, Record<string, unknown>> => {
  const configs: Record<string, Record<string, unknown>> = {};

  if (data.metrics.includes("not_contains")) {
    configs.not_contains = {
      phrases: splitForbiddenPhrases(data.notContainsText),
    };
  }

  if (data.metrics.includes("field_equals")) {
    configs.field_equals = {
      ...(data.fieldEqualsField.trim() ? { field: data.fieldEqualsField.trim() } : {}),
      ...(data.fieldEqualsExpected.trim() ? { expected: data.fieldEqualsExpected.trim() } : {}),
    };
  }

  if (data.metrics.includes("nli_eval")) {
    configs.nli_eval = {
      min_entail_score: Number(data.nliMinEntailScore || "0.5"),
      fail_on_contradiction: data.nliFailOnContradiction,
      ...(data.nliModelName.trim() ? { nli_model_name: data.nliModelName.trim() } : {}),
      ...(data.nliEvidenceSource === "legacy" && data.nliEvidenceField
        ? { evidence_field: data.nliEvidenceField }
        : { evidence_source: data.nliEvidenceSource }),
    };
  }

  if (data.metrics.includes("provenance_eval")) {
    const isLlmMode = data.provMode === "llm";
    configs.provenance_eval = {
      min_score: Number(data.provMinScore || "0.5"),
      use_llm_judge: isLlmMode,
      provenance_mode: data.provMode,
      ...(data.provContextSource === "legacy" && data.provContextField
        ? { context_field: data.provContextField }
        : { context_source: data.provContextSource }),
      ...(isLlmMode && data.provLlmProviderId.trim()
        ? { llm_provider_id: data.provLlmProviderId.trim() }
        : {}),
      ...(isLlmMode && data.provLlmJudgeSystemPromptSuffix.trim()
        ? { llm_judge_system_prompt_suffix: data.provLlmJudgeSystemPromptSuffix.trim() }
        : {}),
      ...(!isLlmMode
        ? {
            embedding_type: data.provEmbeddingType,
            embedding_model_name: data.provEmbeddingModelName.trim() || undefined,
          }
        : {}),
    };
  }

  if (data.metrics.includes("tool_used")) {
    configs.tool_used = {
      rules: data.toolRules.map(serializeToolRule),
    };
  }

  if (data.metrics.includes("route_taken")) {
    configs.route_taken = {
      expected: data.routeExpected.trim(),
      ...(data.routeNode.trim() ? { node: data.routeNode.trim() } : {}),
    };
  }

  if (data.metrics.includes("action_taken")) {
    configs.action_taken = {
      should_fire: data.actionShouldFire,
      ...(data.actionNode.trim() ? { node: data.actionNode.trim() } : {}),
      ...(data.actionNodeType.trim() ? { node_type: data.actionNodeType.trim() } : {}),
    };
  }

  if (data.metrics.includes("llm_judge")) {
    configs.llm_judge = {
      rubric: data.judgeRubric.trim(),
      min_score: Number(data.judgeMinScore || "0.5"),
      ...(data.judgeProviderId.trim() ? { llm_provider_id: data.judgeProviderId.trim() } : {}),
      ...(data.judgeSourceType === "legacy" && data.judgeSourceField
        ? { source_field: data.judgeSourceField }
        : { source_type: data.judgeSourceType }),
    };
  }

  return configs;
};

export const getEditInitialData = (
  evaluation: TestEvaluationConfig,
  providers: LLMProviderMinimal[],
): Partial<EvaluationWizardData> => {
  const notContainsCfg = evaluation.technique_configs?.["not_contains"] as Record<string, unknown> | undefined;
  const fieldEqualsCfg = evaluation.technique_configs?.["field_equals"] as Record<string, unknown> | undefined;
  const nliCfg = evaluation.technique_configs?.["nli_eval"] as Record<string, unknown> | undefined;
  const provCfg = evaluation.technique_configs?.["provenance_eval"] as Record<string, unknown> | undefined;
  const toolCfg = evaluation.technique_configs?.["tool_used"] as Record<string, unknown> | undefined;
  const routeCfg = evaluation.technique_configs?.["route_taken"] as Record<string, unknown> | undefined;
  const actionCfg = evaluation.technique_configs?.["action_taken"] as Record<string, unknown> | undefined;
  const judgeCfg = evaluation.technique_configs?.["llm_judge"] as Record<string, unknown> | undefined;
  const nliSource = parseGradingSource(
    nliCfg,
    "evidence_source",
    "evidence_field",
    "expected_output",
  );
  const provSource = parseGradingSource(
    provCfg,
    "context_source",
    "context_field",
    "expected_output",
  );
  const judgeSource = parseGradingSource(judgeCfg, "source_type", "source_field", "none");
  const metaWithoutMemory = evaluation.input_metadata
    ? Object.fromEntries(Object.entries(evaluation.input_metadata).filter(([k]) => k !== "use_memory"))
    : {};

  return {
    name: evaluation.name,
    description: evaluation.description ?? "",
    suiteId: evaluation.suite_id,
    workflowId: evaluation.workflow_id ?? "none",
    metrics: evaluation.techniques,
    inputMetadataText: JSON.stringify(metaWithoutMemory, null, 2),
    useMemory: Boolean(evaluation.input_metadata?.use_memory),
    nliModelName: (nliCfg?.nli_model_name as string) ?? "cross-encoder/nli-deberta-v3-base",
    nliMinEntailScore: String(nliCfg?.min_entail_score ?? "0.5"),
    nliFailOnContradiction: Boolean(nliCfg?.fail_on_contradiction),
    nliEvidenceSource: nliSource.selection,
    nliEvidenceField: nliSource.legacyField,
    provMode: (provCfg?.provenance_mode as "embeddings" | "llm") ?? "embeddings",
    provContextSource: provSource.selection,
    provContextField: provSource.legacyField,
    provEmbeddingType: (provCfg?.embedding_type as "openai" | "huggingface" | "bedrock") ?? "huggingface",
    provEmbeddingModelName: (provCfg?.embedding_model_name as string) ?? "all-MiniLM-L6-v2",
    provMinScore: String(provCfg?.min_score ?? "0.5"),
    provLlmProviderId: (provCfg?.llm_provider_id as string) ?? providers[0]?.id ?? "",
    provLlmJudgeSystemPromptSuffix: (provCfg?.llm_judge_system_prompt_suffix as string) ?? "",
    toolRules: parseToolRules(toolCfg),
    notContainsText: forbiddenPhrasesToText(notContainsCfg),
    fieldEqualsField: (fieldEqualsCfg?.field as string) ?? "",
    fieldEqualsExpected:
      fieldEqualsCfg?.expected != null ? String(fieldEqualsCfg.expected) : "",
    routeExpected: (routeCfg?.expected as string) ?? "",
    routeNode: (routeCfg?.node as string) ?? "",
    actionNode: (actionCfg?.node as string) ?? "",
    actionNodeType: (actionCfg?.node_type as string) ?? "",
    actionShouldFire: actionCfg?.should_fire === undefined ? true : Boolean(actionCfg.should_fire),
    judgeRubric: (judgeCfg?.rubric as string) ?? "",
    judgeMinScore: String(judgeCfg?.min_score ?? "0.5"),
    judgeProviderId: (judgeCfg?.llm_provider_id as string) ?? providers[0]?.id ?? "",
    judgeSourceType: judgeSource.selection,
    judgeSourceField: judgeSource.legacyField,
  };
};
