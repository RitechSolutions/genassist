import { EvaluationWizardData } from "../components/EvaluationWizard";
import { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";
import { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";

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

  if (data.metrics.includes("nli_eval")) {
    configs.nli_eval = {
      min_entail_score: Number(data.nliMinEntailScore || "0.5"),
      fail_on_contradiction: data.nliFailOnContradiction,
      ...(data.nliModelName.trim() ? { nli_model_name: data.nliModelName.trim() } : {}),
    };
  }

  if (data.metrics.includes("provenance_eval")) {
    const isLlmMode = data.provMode === "llm";
    configs.provenance_eval = {
      min_score: Number(data.provMinScore || "0.5"),
      fail_on_violation: data.provFailOnViolation,
      use_llm_judge: isLlmMode,
      provenance_mode: data.provMode,
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
    // Advanced validation only applies when the tool must be called; drop it otherwise.
    const includeAdvanced = data.toolShouldCall;
    const expectedArgs = includeAdvanced ? parseJsonObject(data.toolExpectedArgsText) : undefined;
    configs.tool_used = {
      should_call: data.toolShouldCall,
      ...(data.toolName.trim() ? { tool: data.toolName.trim() } : {}),
      ...(data.toolNode.trim() ? { node: data.toolNode.trim() } : {}),
      ...(expectedArgs ? { expected_args: expectedArgs } : {}),
      ...(includeAdvanced && data.toolResultNotEmpty ? { result_not_empty: true } : {}),
      ...(includeAdvanced && data.toolResultContains.trim()
        ? { result_contains: data.toolResultContains.trim() }
        : {}),
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
      ...(data.judgeSourceField.trim() ? { source_field: data.judgeSourceField.trim() } : {}),
    };
  }

  return configs;
};

export const getEditInitialData = (
  evaluation: TestEvaluationConfig,
  providers: LLMProviderMinimal[],
): Partial<EvaluationWizardData> => {
  const nliCfg = evaluation.technique_configs?.["nli_eval"] as Record<string, unknown> | undefined;
  const provCfg = evaluation.technique_configs?.["provenance_eval"] as Record<string, unknown> | undefined;
  const toolCfg = evaluation.technique_configs?.["tool_used"] as Record<string, unknown> | undefined;
  const routeCfg = evaluation.technique_configs?.["route_taken"] as Record<string, unknown> | undefined;
  const actionCfg = evaluation.technique_configs?.["action_taken"] as Record<string, unknown> | undefined;
  const judgeCfg = evaluation.technique_configs?.["llm_judge"] as Record<string, unknown> | undefined;
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
    provMode: (provCfg?.provenance_mode as "embeddings" | "llm") ?? "embeddings",
    provEmbeddingType: (provCfg?.embedding_type as "openai" | "huggingface" | "bedrock") ?? "huggingface",
    provEmbeddingModelName: (provCfg?.embedding_model_name as string) ?? "all-MiniLM-L6-v2",
    provMinScore: String(provCfg?.min_score ?? "0.5"),
    provFailOnViolation: Boolean(provCfg?.fail_on_violation),
    provLlmProviderId: (provCfg?.llm_provider_id as string) ?? providers[0]?.id ?? "",
    provLlmJudgeSystemPromptSuffix: (provCfg?.llm_judge_system_prompt_suffix as string) ?? "",
    toolName: (toolCfg?.tool as string) ?? "",
    toolShouldCall: toolCfg?.should_call === undefined ? true : Boolean(toolCfg.should_call),
    toolExpectedArgsText: toolCfg?.expected_args
      ? JSON.stringify(toolCfg.expected_args, null, 2)
      : "",
    toolNode: (toolCfg?.node as string) ?? "",
    toolResultNotEmpty: Boolean(toolCfg?.result_not_empty),
    toolResultContains: (toolCfg?.result_contains as string) ?? "",
    routeExpected: (routeCfg?.expected as string) ?? "",
    routeNode: (routeCfg?.node as string) ?? "",
    actionNode: (actionCfg?.node as string) ?? "",
    actionNodeType: (actionCfg?.node_type as string) ?? "",
    actionShouldFire: actionCfg?.should_fire === undefined ? true : Boolean(actionCfg.should_fire),
    judgeRubric: (judgeCfg?.rubric as string) ?? "",
    judgeMinScore: String(judgeCfg?.min_score ?? "0.5"),
    judgeProviderId: (judgeCfg?.llm_provider_id as string) ?? providers[0]?.id ?? "",
    judgeSourceField: (judgeCfg?.source_field as string) ?? "",
  };
};
