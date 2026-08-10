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

  it("skips non-object rule entries instead of crashing the edit wizard", () => {
    const rules = parseRules({
      rules: [null, { id: "r1", tool_ids: ["t1"], operator: "all", scope: "every_turn" }],
    });
    expect(rules).toHaveLength(1);
    expect(rules[0].id).toBe("r1");
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
      judgeRules: [
        {
          label: "",
          rubric: "The answer should be helpful.",
          minScore: "0.5",
          sourceType: "none",
          sourceField: "",
        },
      ],
      judgeProviderId: "",
    } as unknown as EvaluationWizardData;

    const configs = buildTechniqueConfigs(data);
    expect(configs.nli_eval.evidence_source).toBe("expected_output");
    expect(configs.provenance_eval.context_source).toBe("kb_retrievals");
    const judgeRules = configs.llm_judge.rules as Record<string, unknown>[];
    expect(judgeRules[0].source_type).toBe("none");
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
    const judgeRules = configs.llm_judge.rules as Record<string, unknown>[];
    expect(judgeRules[0].source_field).toBe("trace.session.custom");
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
    expect(initial.judgeRules?.[0]?.sourceType).toBe("none");
  });

  it("round-trips a multi-rule judge config through the wizard", () => {
    const evaluation = {
      id: "e4",
      name: "multi judge",
      suite_id: "s1",
      techniques: ["llm_judge"],
      technique_configs: {
        llm_judge: {
          llm_provider_id: "p1",
          rules: [
            { label: "Tone", rubric: "Polite?", min_score: 0.5, source_type: "none" },
            {
              label: "Relevance",
              rubric: "Sources relevant?",
              min_score: 0.7,
              source_type: "kb_retrievals",
            },
          ],
        },
      },
      run_ids: [],
      created_at: "",
      updated_at: "",
    } as TestEvaluationConfig;

    const initial = getEditInitialData(evaluation, []);
    expect(initial.judgeRules).toHaveLength(2);
    expect(initial.judgeRules?.[1]?.sourceType).toBe("kb_retrievals");

    const data = {
      metrics: ["llm_judge"],
      judgeRules: initial.judgeRules,
      judgeProviderId: initial.judgeProviderId,
    } as unknown as EvaluationWizardData;
    const configs = buildTechniqueConfigs(data);
    expect(configs.llm_judge).toEqual({
      llm_provider_id: "p1",
      rules: [
        { label: "Tone", rubric: "Polite?", min_score: 0.5, source_type: "none" },
        {
          label: "Relevance",
          rubric: "Sources relevant?",
          min_score: 0.7,
          source_type: "kb_retrievals",
        },
      ],
    });
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

describe("route_taken and action_taken multi-rule configs", () => {
  const evalWithConfigs = (
    configs: Record<string, Record<string, unknown>>,
  ): TestEvaluationConfig =>
    ({
      id: "ra1",
      name: "route/action",
      suite_id: "s1",
      techniques: Object.keys(configs),
      technique_configs: configs,
      run_ids: [],
      created_at: "",
      updated_at: "",
    }) as TestEvaluationConfig;

  it("parses a legacy single-rule route config into one draft rule", () => {
    const initial = getEditInitialData(
      evalWithConfigs({ route_taken: { expected: "true", node: "router1" } }),
      [],
    );
    expect(initial.routeRules).toEqual([{ router: "router1", expected: "true" }]);
  });

  it("parses a legacy single-rule action config into one draft rule", () => {
    const initial = getEditInitialData(
      evalWithConfigs({ action_taken: { node: "action1", should_fire: false } }),
      [],
    );
    expect(initial.actionRules).toEqual([
      { node: "action1", nodeType: "", shouldFire: false },
    ]);
  });

  it("serializes route rules as a rules list", () => {
    const data = {
      metrics: ["route_taken"],
      routeRules: [
        { router: "r1", expected: "true" },
        { router: "", expected: "support" },
      ],
    } as unknown as EvaluationWizardData;

    expect(buildTechniqueConfigs(data).route_taken).toEqual({
      rules: [{ router: "r1", expected: "true" }, { expected: "support" }],
    });
  });

  it("skips non-object rule entries the backend tolerates instead of crashing", () => {
    const initial = getEditInitialData(
      evalWithConfigs({
        route_taken: { rules: [null, { router: "r1", expected: "true" }, "junk"] },
        action_taken: { rules: [42, { node: "a1" }] },
      }),
      [],
    );
    expect(initial.routeRules).toEqual([{ router: "r1", expected: "true" }]);
    expect(initial.actionRules).toEqual([{ node: "a1", nodeType: "", shouldFire: true }]);
  });

  it("round-trips a stored multi-rule action config through the wizard", () => {
    const stored = {
      action_taken: {
        rules: [
          { node: "a1", should_fire: true },
          { node_type: "zendeskTicketNode", should_fire: false },
        ],
      },
    };
    const initial = getEditInitialData(evalWithConfigs(stored), []);
    const data = {
      metrics: ["action_taken"],
      actionRules: initial.actionRules,
    } as unknown as EvaluationWizardData;

    expect(buildTechniqueConfigs(data).action_taken).toEqual({
      rules: [
        { node: "a1", should_fire: true },
        { node_type: "zendeskTicketNode", should_fire: false },
      ],
    });
  });
});
