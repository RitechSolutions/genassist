import { describe, it, expect } from "vitest";
import { buildTechniqueConfigs, getEditInitialData } from "./evaluationForm";
import type { EvaluationWizardData } from "../components/EvaluationWizard";
import type { TestEvaluationConfig } from "@/interfaces/testEvaluation.interface";

const evalWith = (toolUsed: Record<string, unknown>): TestEvaluationConfig =>
  ({
    id: "e1",
    name: "eval",
    suite_id: "s1",
    techniques: ["tool_used"],
    technique_configs: { tool_used: toolUsed },
    run_ids: [],
    created_at: "",
    updated_at: "",
  }) as TestEvaluationConfig;

const parseRules = (toolUsed: Record<string, unknown>) =>
  getEditInitialData(evalWith(toolUsed), []).toolRules ?? [];

describe("parseToolRules legacy shapes", () => {
  it("keeps a bare should_call:false as a 'no tools' rule instead of dropping it", () => {
    const rules = parseRules({ should_call: false });
    expect(rules).toHaveLength(1);
    expect(rules[0].operator).toBe("only");
    expect(rules[0].tool_ids).toEqual([]);
  });

  it("turns a bare should_call:true into an any-tool marker instead of dropping it", () => {
    const rules = parseRules({ should_call: true });
    expect(rules).toHaveLength(1);
    expect(rules[0].operator).toBe("any");
    expect(rules[0].tool_ids).toEqual([]);
  });

  it("maps a named tool with should_call:false to 'none'", () => {
    const rules = parseRules({ tool: "search", should_call: false });
    expect(rules[0].operator).toBe("none");
    expect(rules[0].tool_ids).toEqual(["search"]);
  });

  it("folds legacy top-level result checks into the tool's per_tool entry", () => {
    const rules = parseRules({ tool: "search", result_contains: "ok" });
    expect(rules[0].per_tool?.search?.result_contains).toBe("ok");
  });
});

describe("serializeToolRule round-trips per_tool", () => {
  it("preserves per_tool through parse -> serialize (edit without loss)", () => {
    const stored = {
      rules: [
        {
          id: "r1",
          tool_ids: ["t1"],
          operator: "all",
          scope: "every_turn",
          per_tool: { t1: { result_not_empty: true, result_contains: "x", expected_args: { q: "1" } } },
        },
      ],
    };
    const rules = parseRules(stored);
    const data = { metrics: ["tool_used"], toolRules: rules } as unknown as EvaluationWizardData;
    const out = buildTechniqueConfigs(data).tool_used as {
      rules: { per_tool?: Record<string, unknown> }[];
    };
    expect(out.rules[0].per_tool).toEqual({
      t1: { result_not_empty: true, result_contains: "x", expected_args: { q: "1" } },
    });
  });
});

describe("grading source configs", () => {
  it("writes explicit sources for new NLI, Provenance, and LLM Judge configs", () => {
    const data = {
      metrics: ["nli_eval", "provenance_eval", "llm_judge"],
      nliMinEntailScore: "0.6",
      nliFailOnContradiction: false,
      nliModelName: "cross-encoder/nli-deberta-v3-base",
      nliEvidenceSource: "expected_output",
      nliEvidenceField: "",
      provMode: "embeddings",
      provContextSource: "kb_retrievals",
      provContextField: "",
      provMinScore: "0.7",
      provEmbeddingType: "huggingface",
      provEmbeddingModelName: "all-MiniLM-L6-v2",
      provLlmProviderId: "",
      provLlmJudgeSystemPromptSuffix: "",
      judgeRubric: "The answer should be helpful.",
      judgeMinScore: "0.5",
      judgeProviderId: "",
      judgeSourceType: "none",
      judgeSourceField: "",
    } as unknown as EvaluationWizardData;

    const configs = buildTechniqueConfigs(data);
    expect(configs.nli_eval.evidence_source).toBe("expected_output");
    expect(configs.provenance_eval.context_source).toBe("kb_retrievals");
    expect(configs.llm_judge.source_type).toBe("none");
  });

  it("keeps unknown legacy source fields when an evaluation is edited", () => {
    const evaluation = {
      id: "e2",
      name: "legacy",
      suite_id: "s1",
      techniques: ["nli_eval", "provenance_eval", "llm_judge"],
      technique_configs: {
        nli_eval: { evidence_field: "trace.nodes.custom.output" },
        provenance_eval: { context_field: "trace.nodes.legacy.output" },
        llm_judge: { rubric: "Grounded?", source_field: "trace.session.custom" },
      },
      run_ids: [],
      created_at: "",
      updated_at: "",
    } as TestEvaluationConfig;

    const initial = getEditInitialData(evaluation, []);
    const data = {
      ...initial,
      metrics: evaluation.techniques,
    } as EvaluationWizardData;
    const configs = buildTechniqueConfigs(data);

    expect(configs.nli_eval.evidence_field).toBe("trace.nodes.custom.output");
    expect(configs.provenance_eval.context_field).toBe("trace.nodes.legacy.output");
    expect(configs.llm_judge.source_field).toBe("trace.session.custom");
  });

  it("preserves the old expected-output default for saved semantic evaluations", () => {
    const evaluation = {
      id: "e3",
      name: "old defaults",
      suite_id: "s1",
      techniques: ["nli_eval", "provenance_eval", "llm_judge"],
      technique_configs: {
        nli_eval: {},
        provenance_eval: {},
        llm_judge: { rubric: "Helpful?" },
      },
      run_ids: [],
      created_at: "",
      updated_at: "",
    } as TestEvaluationConfig;

    const initial = getEditInitialData(evaluation, []);
    expect(initial.nliEvidenceSource).toBe("expected_output");
    expect(initial.provContextSource).toBe("expected_output");
    expect(initial.judgeSourceType).toBe("none");
  });
});

describe("field_equals config", () => {
  it("serializes field and expected value when both are set", () => {
    const data = {
      metrics: ["field_equals"],
      fieldEqualsField: "outputs.status",
      fieldEqualsExpected: "resolved",
    } as unknown as EvaluationWizardData;

    expect(buildTechniqueConfigs(data).field_equals).toEqual({
      field: "outputs.status",
      expected: "resolved",
    });
  });

  it("omits empty field and expected so backend defaults apply", () => {
    const data = {
      metrics: ["field_equals"],
      fieldEqualsField: "",
      fieldEqualsExpected: "",
    } as unknown as EvaluationWizardData;

    expect(buildTechniqueConfigs(data).field_equals).toEqual({});
  });

  it("round-trips a saved field_equals config back into the wizard", () => {
    const evaluation = {
      id: "fe1",
      name: "field equals",
      suite_id: "s1",
      techniques: ["field_equals"],
      technique_configs: { field_equals: { field: "outputs.status", expected: "resolved" } },
      run_ids: [],
      created_at: "",
      updated_at: "",
    } as TestEvaluationConfig;

    const initial = getEditInitialData(evaluation, []);
    expect(initial.fieldEqualsField).toBe("outputs.status");
    expect(initial.fieldEqualsExpected).toBe("resolved");
  });
});
