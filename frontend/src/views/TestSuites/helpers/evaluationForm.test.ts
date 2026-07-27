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
