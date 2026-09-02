import { describe, expect, it } from "vitest";
import {
  groupByTechnique,
  hasMetrics,
  ruleCheckSummary,
  isResultNotScored,
  isResultPassed,
  isResultFailed,
  notScoredLabel,
  caseStatusFor,
  runAvgAccuracy,
} from "@/views/TestSuites/helpers/runResults";
import type { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";

const result = (overrides: Partial<TestResult>): TestResult => ({
  run_id: "run",
  case_id: "case",
  ...overrides,
});

const metric = (passed: boolean) => ({ score: passed ? 1 : 0, passed });

const toolResult = (
  status: TestToolRuleResult["status"],
  technique: TestToolRuleResult["technique"] = "tool_used",
): TestToolRuleResult => ({
  id: `${technique}-${status}`,
  run_id: "run",
  technique,
  rule_id: "rule",
  scope: "conversation",
  status,
  created_at: "2024-01-01",
});

describe("hasMetrics", () => {
  it("is true only when the metrics object exists and is non-empty", () => {
    expect(hasMetrics(result({ metrics: { m: metric(true) } }))).toBe(true);
  });

  it("is false for an empty or missing metrics object", () => {
    expect(hasMetrics(result({ metrics: {} }))).toBe(false);
    expect(hasMetrics(result({}))).toBe(false);
  });
});

describe("isResultNotScored", () => {
  it("is not scored when there are no metrics", () => {
    expect(isResultNotScored(result({}))).toBe(true);
    expect(isResultNotScored(result({ metrics: {} }))).toBe(true);
  });

  it("is scored when metrics exist and status is absent or 'scored'", () => {
    expect(isResultNotScored(result({ metrics: { m: metric(true) } }))).toBe(
      false,
    );
    expect(
      isResultNotScored(
        result({ metrics: { m: metric(true) }, status: "scored" }),
      ),
    ).toBe(false);
  });

  it("is not scored when a non-'scored' status is present, even with metrics", () => {
    expect(
      isResultNotScored(
        result({ metrics: { m: metric(true) }, status: "skipped" }),
      ),
    ).toBe(true);
  });

  it("treats an empty-string status as scored (falsy status is ignored)", () => {
    expect(
      isResultNotScored(result({ metrics: { m: metric(true) }, status: "" })),
    ).toBe(false);
  });
});

describe("isResultPassed", () => {
  it("passes when scored and every metric passed", () => {
    expect(
      isResultPassed(
        result({ metrics: { a: metric(true), b: metric(true) } }),
      ),
    ).toBe(true);
  });

  it("fails when any metric did not pass", () => {
    expect(
      isResultPassed(
        result({ metrics: { a: metric(true), b: metric(false) } }),
      ),
    ).toBe(false);
  });

  it("does not pass when not scored", () => {
    expect(isResultPassed(result({}))).toBe(false);
    expect(
      isResultPassed(
        result({ metrics: { a: metric(true) }, status: "skipped" }),
      ),
    ).toBe(false);
  });
});

describe("isResultFailed", () => {
  it("is failed when scored but not passed", () => {
    expect(isResultFailed(result({ metrics: { a: metric(false) } }))).toBe(
      true,
    );
  });

  it("is not failed when passed", () => {
    expect(isResultFailed(result({ metrics: { a: metric(true) } }))).toBe(
      false,
    );
  });

  it("is not failed when not scored", () => {
    expect(isResultFailed(result({}))).toBe(false);
    expect(
      isResultFailed(
        result({ metrics: { a: metric(false) }, status: "skipped" }),
      ),
    ).toBe(false);
  });
});

describe("notScoredLabel", () => {
  it("maps known statuses to friendly labels", () => {
    expect(notScoredLabel(result({ status: "skipped" }))).toBe("Skipped");
    expect(notScoredLabel(result({ status: "scoring_failed" }))).toBe(
      "Scoring failed",
    );
    expect(notScoredLabel(result({ status: "execution_failed" }))).toBe(
      "Execution failed",
    );
  });

  it("falls back to 'Not scored' for other or missing statuses", () => {
    expect(notScoredLabel(result({}))).toBe("Not scored");
    expect(notScoredLabel(result({ status: "scored" }))).toBe("Not scored");
  });
});

describe("caseStatusFor", () => {
  it("fails the case when any tool result failed, overriding a passing result", () => {
    expect(
      caseStatusFor(result({ metrics: { a: metric(true) } }), [
        toolResult("passed"),
        toolResult("failed"),
      ]),
    ).toBe("failed");
  });

  it("passes when the result passed and no tool failed", () => {
    expect(
      caseStatusFor(result({ metrics: { a: metric(true) } }), []),
    ).toBe("passed");
  });

  it("passes an unscored case when a tool result passed", () => {
    expect(caseStatusFor(result({}), [toolResult("passed")])).toBe("passed");
  });

  it("stays not_scored when unscored and no tool passed or failed", () => {
    expect(caseStatusFor(result({}), [])).toBe("not_scored");
    expect(caseStatusFor(result({}), [toolResult("not_evaluated")])).toBe(
      "not_scored",
    );
  });

  it("fails when the result itself failed", () => {
    expect(
      caseStatusFor(result({ metrics: { a: metric(false) } }), []),
    ).toBe("failed");
  });
});

describe("runAvgAccuracy", () => {
  const run = (summary_metrics?: Record<string, unknown>): TestRun => ({
    suite_id: "suite",
    workflow_id: "wf",
    status: "completed",
    techniques: [],
    summary_metrics,
  });

  it("returns null when summary_metrics is missing or empty", () => {
    expect(runAvgAccuracy(run(undefined))).toBeNull();
    expect(runAvgAccuracy(run({}))).toBeNull();
  });

  it("returns the single accuracy value", () => {
    expect(runAvgAccuracy(run({ exact: { accuracy: 0.8 } }))).toBeCloseTo(0.8);
  });

  it("averages accuracies across scored metrics", () => {
    expect(
      runAvgAccuracy(run({ a: { accuracy: 1 }, b: { accuracy: 0 } })),
    ).toBeCloseTo(0.5);
    expect(
      runAvgAccuracy(run({ a: { accuracy: 0.9 }, b: { accuracy: 0.7 } })),
    ).toBeCloseTo(0.8);
  });

  it("ignores metrics whose accuracy is not a number", () => {
    expect(
      runAvgAccuracy(run({ a: { accuracy: 0.8 }, b: { accuracy: "x" }, c: {} })),
    ).toBeCloseTo(0.8);
  });

  it("returns null when no metric has a numeric accuracy", () => {
    expect(runAvgAccuracy(run({ a: {}, b: { accuracy: "n/a" } }))).toBeNull();
  });

  it("counts a zero accuracy as scored (returns 0, not null)", () => {
    expect(runAvgAccuracy(run({ a: { accuracy: 0 } }))).toBe(0);
  });
});

describe("groupByTechnique", () => {
  it("groups rule results per technique, in wizard order", () => {
    const grouped = groupByTechnique([
      toolResult("passed", "action_taken"),
      toolResult("failed", "tool_used"),
      toolResult("passed", "route_taken"),
    ]);

    expect(grouped.map(([technique]) => technique)).toEqual([
      "tool_used",
      "route_taken",
      "action_taken",
    ]);
    expect(grouped[0][1]).toHaveLength(1);
  });

  it("treats a row without a technique as tool usage", () => {
    const legacy = { ...toolResult("passed"), technique: undefined } as unknown as TestToolRuleResult;
    expect(groupByTechnique([legacy]).map(([technique]) => technique)).toEqual(["tool_used"]);
  });

  it("returns nothing for an empty run", () => {
    expect(groupByTechnique([])).toEqual([]);
  });
});

describe("ruleCheckSummary", () => {
  const check = (
    status: TestToolRuleResult["status"],
    ruleId: string,
    scope: string,
  ): TestToolRuleResult => ({
    ...toolResult(status),
    id: `${ruleId}-${scope}-${Math.random()}`,
    rule_id: ruleId,
    scope,
  });

  it("counts rule checks, not turns, and says how the count is made up", () => {
    // Two every-turn rules over 12 turns: 24 checks, 15 of them passing.
    const results = Array.from({ length: 12 }, (_, index) => [
      check(index < 9 ? "passed" : "failed", "action-1", "every_turn"),
      check(index < 6 ? "passed" : "failed", "action-2", "every_turn"),
    ]).flat();

    const { headline, subline } = ruleCheckSummary(results);

    expect(headline).toBe("15 of 24 checks passed · 63% pass rate");
    expect(subline).toBe("2 rules · 24 turn checks");
  });

  it("counts a specific-turn rule once per turn it targets", () => {
    const results = [
      ...Array.from({ length: 12 }, () => check("passed", "route-2", "every_turn")),
      check("passed", "route-1", "specific_turn"),
      check("failed", "route-1", "specific_turn"),
    ];

    expect(ruleCheckSummary(results).subline).toBe("2 rules · 14 turn checks");
  });

  it("separates conversation checks from turn checks", () => {
    const results = [
      check("passed", "r1", "conversation"),
      check("failed", "r1", "conversation"),
      check("passed", "r2", "every_turn"),
    ];

    const { headline, subline } = ruleCheckSummary(results);

    expect(headline).toBe("2 of 3 checks passed · 67% pass rate");
    expect(subline).toBe("2 rules · 1 turn check · 2 conversation checks");
  });
});
