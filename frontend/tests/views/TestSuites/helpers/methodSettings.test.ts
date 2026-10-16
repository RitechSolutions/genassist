import { describe, it, expect } from "vitest";
import {
  methodDefaults,
  methodSettingsComplete,
  remapToolRuleNames,
} from "@/views/TestSuites/helpers/methodSettings";
import { buildTechniqueConfigs, getEditInitialData } from "@/views/TestSuites/helpers/evaluationForm";
import {
  checkResultsSummary,
  checksConversations,
  checksVerdictText,
  groupByTechnique,
  isConversationScope,
  isTurnScope,
  runGradesTurns,
} from "@/views/TestSuites/helpers/runResults";
import { indexConversations, ruleTargetLabel } from "@/views/TestSuites/helpers/datasetConversations";
import type { EvaluationAgentInfo, TestEvaluationConfig, TestToolRuleResult } from "@/interfaces/testEvaluation.interface";
import type { TestRun } from "@/interfaces/testSuite.interface";

const AGENTS: EvaluationAgentInfo[] = [
  { id: "agent-1", label: "Refund agent", type: "agentNode", workflow_path: [], tools: [
    { id: "tool-1", name: "save_region", label: "Save region", type: "toolBuilderNode" },
  ] },
];

describe("method settings", () => {
  it("start from what was saved, or each method's defaults", () => {
    const fresh = methodDefaults(undefined, [{ id: "p1" } as never]);
    expect(fresh.nliMinEntailScore).toBe("0.5");
    expect(fresh.judgeProviderId).toBe("p1");
    expect(fresh.toolRules).toHaveLength(1);
    expect(methodDefaults({ notContainsText: "RingGo" }, []).notContainsText).toBe("RingGo");
  });

  it("block saving until each picked method is filled in", () => {
    const settings = methodDefaults(undefined, []);
    const catalog = { agents: AGENTS, routers: [] };
    expect(methodSettingsComplete([], settings, catalog)).toBe(true);
    expect(methodSettingsComplete(["not_contains"], settings, catalog)).toBe(false);
    expect(methodSettingsComplete(["not_contains"], { ...settings, notContainsText: "RingGo" }, catalog)).toBe(true);
    expect(methodSettingsComplete(["tool_used"], settings, catalog)).toBe(false);
    expect(methodSettingsComplete(["tool_used"], {
      ...settings,
      toolRules: [{ ...settings.toolRules[0], tool_ids: ["tool-1"] }],
    }, catalog)).toBe(true);
    // A tool name that never resolved to an id blocks saving.
    expect(methodSettingsComplete(["tool_used"], {
      ...settings,
      toolRules: [{ ...settings.toolRules[0], tool_ids: ["gone"] }],
    }, catalog)).toBe(false);
    expect(methodSettingsComplete(["nli_eval"], { ...settings, nliMinEntailScore: "2" }, catalog)).toBe(false);
  });

  it("rewrite legacy tool names to ids, and keep the same rules when nothing changed", () => {
    const settings = methodDefaults(undefined, []);
    const named = [{ ...settings.toolRules[0], tool_ids: ["Save region"], agent_id: "refund agent" }];
    expect(remapToolRuleNames(named, AGENTS)[0]).toMatchObject({ tool_ids: ["tool-1"], agent_id: "agent-1" });
    const canonical = [{ ...settings.toolRules[0], tool_ids: ["tool-1"] }];
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
  const row = (scope: string, technique: TestToolRuleResult["technique"] = "checks"): TestToolRuleResult => ({
    id: `${technique}-${scope}`,
    run_id: "r",
    technique,
    rule_id: "c1",
    scope,
    status: "passed",
    created_at: "",
  });

  it("sit with their turn or their conversation, checks first", () => {
    expect(isTurnScope("turn")).toBe(true);
    expect(isConversationScope("every_conversation")).toBe(true);
    expect(isConversationScope("turn")).toBe(false);
    expect(groupByTechnique([row("every_turn", "tool_used"), row("turn")]).map(([technique]) => technique)).toEqual([
      "checks",
      "tool_used",
    ]);
  });

  it("name the conversation a check for every conversation graded", () => {
    const index = indexConversations([
      { id: "a1", suite_id: "s", input_data: { message: "Hi" }, source_conversation_id: "conv-a", turn_index: 0 },
    ]);
    expect(ruleTargetLabel({ ...row("every_conversation"), source_conversation_id: "conv-a" }, index)).toBe("Hi · 1 turn");
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

  it("count checks apart from their results, under the run's verdict", () => {
    const rows: TestToolRuleResult[] = [
      row("turn"),
      { ...row("every_conversation"), id: "b", rule_id: "c2", status: "failed" },
      { ...row("every_conversation"), id: "c", rule_id: "c2" },
    ];
    expect(checkResultsSummary(rows, "1 of 2 conversations passed · 1 failed")).toEqual({
      headline: "1 of 2 conversations passed · 1 failed",
      subline: "2 checks · 3 results",
    });
    expect(checkResultsSummary(rows, null).headline).toBe("2 of 3 results passed");
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
