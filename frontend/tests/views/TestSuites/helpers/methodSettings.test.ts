import { describe, it, expect } from "vitest";
import { methodDefaults, remapToolRuleNames } from "@/views/TestSuites/helpers/methodSettings";
import { buildTechniqueConfigs, getEditInitialData } from "@/views/TestSuites/helpers/evaluationForm";
import {
  checksConversations,
  checksVerdictText,
  isTurnScope,
  runGradesTurns,
} from "@/views/TestSuites/helpers/runResults";
import type { EvaluationAgentInfo, TestEvaluationConfig, ToolUsageRule } from "@/interfaces/testEvaluation.interface";
import type { TestRun } from "@/interfaces/testSuite.interface";

const AGENTS: EvaluationAgentInfo[] = [
  { id: "agent-1", label: "Refund agent", type: "agentNode", workflow_path: [], tools: [
    { id: "tool-1", name: "save_region", label: "Save region", type: "toolBuilderNode" },
  ] },
];

const RULE: ToolUsageRule = {
  id: "r",
  agent_id: null,
  tool_ids: [],
  operator: "all",
  require_success: false,
  scope: "every_turn",
};

describe("method settings", () => {
  it("start from what was saved, or each method's defaults", () => {
    const fresh = methodDefaults(undefined, [{ id: "p1" } as never]);
    expect(fresh.nliMinEntailScore).toBe("0.5");
    expect(fresh.judgeProviderId).toBe("p1");
    expect(fresh.toolRules).toEqual([]);
    expect(methodDefaults({ notContainsText: "RingGo" }, []).notContainsText).toBe("RingGo");
  });

  it("rewrite legacy tool names to ids, and keep the same rules when nothing changed", () => {
    const named = [{ ...RULE, tool_ids: ["Save region"], agent_id: "refund agent" }];
    expect(remapToolRuleNames(named, AGENTS)[0]).toMatchObject({ tool_ids: ["tool-1"], agent_id: "agent-1" });
    const canonical = [{ ...RULE, tool_ids: ["tool-1"] }];
    expect(remapToolRuleNames(canonical, AGENTS)).toBe(canonical);
    expect(remapToolRuleNames(named, [])).toBe(named);
  });
});

describe("checks in the evaluation form", () => {
  const evaluation: TestEvaluationConfig = {
    id: "e1",
    name: "Parker",
    suite_id: "s1",
    techniques: ["contains", "checks"],
    technique_configs: {
      checks: {
        checks: [{ id: "c1", kind: "reply_mentions", text: "RingGo", expect: "should_not", level: "every_conversation", when: "anywhere" }],
        llm_provider_id: "p2",
      },
    },
    run_ids: [],
    created_at: "",
    updated_at: "",
  };

  it("load with the evaluation and save back unchanged", () => {
    const initial = getEditInitialData(evaluation, []);
    expect(initial.checks).toHaveLength(1);
    expect(initial.checksProviderId).toBe("p2");
    const saved = buildTechniqueConfigs({ ...(initial as Required<typeof initial>), metrics: initial.metrics ?? [] });
    expect(saved.checks).toEqual({ checks: evaluation.technique_configs?.checks?.checks });
  });

  it("are left out when the evaluation does not use them", () => {
    const initial = getEditInitialData({ ...evaluation, techniques: ["contains"], technique_configs: {} }, []);
    expect(initial.checks).toEqual([]);
    expect(buildTechniqueConfigs({ ...(initial as Required<typeof initial>) }).checks).toBeUndefined();
  });
});

describe("check results", () => {
  it("sit with their turn", () => {
    expect(isTurnScope("turn")).toBe(true);
    expect(isTurnScope("every_conversation")).toBe(false);
  });

  it("read the run's verdict by conversation", () => {
    const run = (conversations: Record<string, number>): TestRun => ({
      suite_id: "s",
      workflow_id: "w",
      status: "completed",
      techniques: ["checks"],
      summary_metrics: { checks: { conversations } },
    });
    expect(checksVerdictText(run({ total: 4, passed: 2, failed: 1, not_evaluated: 1 }))).toBe(
      "2 of 3 conversations passed · 1 failed · 1 not checked",
    );
    expect(checksVerdictText(run({ total: 1, passed: 0, failed: 0, not_evaluated: 1 }))).toBe(
      "No conversation could be checked · 1 not checked",
    );
    expect(checksVerdictText(undefined)).toBeNull();
  });

  it("lead the run's summary when no older method graded turns", () => {
    const conversations = { total: 2, passed: 1, failed: 1, not_evaluated: 0 };
    const run = (techniques: string[]): TestRun => ({
      suite_id: "s",
      workflow_id: "w",
      status: "completed",
      techniques,
      summary_metrics: { checks: { conversations } },
    });
    expect(checksConversations(run(["checks"]))).toEqual(conversations);
    expect(runGradesTurns(run(["checks"]))).toBe(false);
    expect(runGradesTurns(run(["checks", "contains"]))).toBe(true);
    expect(checksConversations({ ...run(["contains"]), summary_metrics: {} })).toBeNull();
  });
});
