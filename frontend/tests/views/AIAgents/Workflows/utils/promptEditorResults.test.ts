import { describe, expect, it } from "vitest";
import type {
  PromptCaseVerdict,
  PromptEvalCaseResult,
  PromptEvalMetric,
  PromptEvalResponse,
  PromptEvalSummary,
  PromptRunProvenance,
} from "@/interfaces/promptEditor.interface";
import {
  caseSpendLine,
  caseStatusLabel,
  compareRuns,
  formatAvgScore,
  formatSpend,
  joinPairedRuns,
  metricOutcomeLabel,
  metricScoreLabel,
  rewriteHeader,
  soleMetricEchoesVerdict,
  snapshotHeader,
  spendComparisonLine,
  summaryLine,
} from "@/views/AIAgents/Workflows/utils/promptEditorResults";

const summary = (overrides: Partial<PromptEvalSummary> = {}): PromptEvalSummary => ({
  total: 10,
  passed: 7,
  failed: 2,
  inconclusive: 1,
  execution_failed: 0,
  scoring_failed: 0,
  skipped: 0,
  scored: 10,
  avg_score: 0.8,
  ...overrides,
});

const provenance = (
  overrides: Partial<PromptRunProvenance> = {},
): PromptRunProvenance => ({
  mode: "isolated_prompt",
  provider_id: "p1",
  provider_key: "azure_openai",
  model: "gpt-4o",
  techniques: ["contains"],
  evaluated_case_ids: Array.from({ length: 10 }, (_, i) => `c${i}`),
  total_cases: 42,
  trials: 1,
  ran_at: "2026-09-14T14:32:00Z",
  latency_ms_total: 1200,
  usage_total: {},
  cost_usd: null,
  unpriced_calls: 0,
  grader_calls: 0,
  grader_tokens: 0,
  grader_cost_usd: null,
  budget_seconds: 70,
  deadline_hit: false,
  metering_handoff_failed: false,
  ...overrides,
});

const caseResult = (
  caseId: string,
  overrides: Partial<PromptEvalCaseResult> = {},
): PromptEvalCaseResult =>
  ({
    case_id: caseId,
    input: "in",
    expected: "exp",
    actual: "act",
    actual_truncated: false,
    status: "scored",
    error: null,
    metrics: {},
    verdict: "passed",
    passed: true,
    case_score: 1,
    scored_metrics: 1,
    failed_metrics: 0,
    errored_metrics: 0,
    not_evaluated_metrics: 0,
    not_applicable_metrics: 0,
    latency_ms: null,
    usage: null,
    cost_usd: null,
    ...overrides,
  }) as PromptEvalCaseResult;

const response = (
  results: PromptEvalCaseResult[],
  provenanceOverrides: Partial<PromptRunProvenance> = {},
): PromptEvalResponse => ({
  results,
  summary: summary(),
  provenance: provenance(provenanceOverrides),
});

describe("summaryLine", () => {
  it("lists every outcome that occurred", () => {
    expect(summaryLine(summary({ execution_failed: 3 }))).toBe(
      "7 passed · 2 failed · 1 inconclusive · 3 execution errors",
    );
  });

  it("drops the outcomes that did not occur but always states the passes", () => {
    expect(
      summaryLine(summary({ passed: 0, failed: 0, inconclusive: 0, skipped: 4 })),
    ).toBe("0 passed · 4 skipped");
  });

  it("does not report an infrastructure error as a failure", () => {
    expect(summaryLine(summary({ failed: 0, scoring_failed: 1 }))).toBe(
      "7 passed · 1 inconclusive · 1 scoring error",
    );
  });
});

describe("snapshotHeader", () => {
  it("states the cases run, the model the server used and the sampling", () => {
    const header = snapshotHeader(provenance());

    expect(header).toMatch(/^10 of 42 cases · /);
    expect(header).toMatch(/ran \d{1,2}:\d{2}/);
    expect(header).toContain("azure_openai (gpt-4o)");
    expect(header).toContain("single sample");
    expect(header).not.toContain("cut by the time budget");
  });

  it("says a fresh run was cut short, and whether its spend was handed over", () => {
    const header = snapshotHeader(
      provenance({ deadline_hit: true, metering_handoff_failed: true }),
    );

    expect(header).toContain("cut by the time budget");
    expect(header).toContain("spend not recorded");
  });

  it("falls back to the local provider row when the run named no model", () => {
    expect(
      snapshotHeader(provenance({ provider_key: "", model: "" }), {
        name: "House OpenAI",
        llm_model_provider: "",
        llm_model: "",
      }),
    ).toContain("House OpenAI");
  });

  it("states what the run took, used and cost", () => {
    const header = snapshotHeader(
      provenance({
        usage_total: { total_tokens: 1500, responses_without_usage: 0 },
        cost_usd: 0.0412,
      }),
    );

    expect(header).toContain("took 1.20 s");
    expect(header).toMatch(/1[,.\s ]?500 tokens/);
    expect(header).toContain("$0.0412");
  });

  it("names the calls the provider reported no tokens for", () => {
    expect(
      snapshotHeader(
        provenance({
          usage_total: { total_tokens: 1500, responses_without_usage: 2 },
        }),
      ),
    ).toContain("2 calls unreported");
  });

  it("never prints zero tokens for a run that reported none", () => {
    const header = snapshotHeader(
      provenance({ usage_total: { total_tokens: 0, responses_without_usage: 3 } }),
    );

    expect(header).toContain("tokens unreported");
    expect(header).not.toContain("0 tokens");
  });

  it("says nothing about tokens when the run has no usage at all", () => {
    expect(snapshotHeader(provenance())).not.toContain("tokens");
  });

  it("says unpriced rather than $0 when nothing could be priced", () => {
    const header = snapshotHeader(provenance({ cost_usd: null, unpriced_calls: 3 }));

    expect(header).toContain("unpriced");
    expect(header).not.toContain("$");
  });

  it("discloses the calls a priced subtotal leaves out", () => {
    expect(
      snapshotHeader(provenance({ cost_usd: 0.02, unpriced_calls: 1 })),
    ).toContain("$0.0200 (1 call unpriced)");
  });

  it("names the judge's own share only when a judge call was recorded", () => {
    expect(
      snapshotHeader(
        provenance({
          cost_usd: 0.0021,
          grader_calls: 2,
          grader_tokens: 2051,
          grader_cost_usd: 0.0009,
        }),
      ),
    ).toMatch(/\$0\.0021 · LLM Judge 2[,.\s ]?051 tokens · \$0\.0009/);
    expect(
      snapshotHeader(provenance({ techniques: ["llm_judge"], grader_calls: 0 })),
    ).not.toContain("LLM Judge");
  });

  it("stays silent about a judge share the run never priced", () => {
    const header = snapshotHeader(
      provenance({
        usage_total: { total_tokens: 6415, responses_without_usage: 0 },
        cost_usd: 0.0007,
        unpriced_calls: 5,
        grader_calls: 5,
        grader_tokens: 0,
        grader_cost_usd: null,
      }),
    );

    expect(header).not.toContain("LLM Judge");
    expect(header).toContain("6,415 tokens");
    expect(header).toContain("(5 calls unpriced)");
  });
});

describe("rewriteHeader", () => {
  it("states the rewrite's own spend and never claims a sample or a grader", () => {
    const header = rewriteHeader(
      provenance({
        usage_total: { total_tokens: 900, responses_without_usage: 0 },
        cost_usd: 0.0031,
        techniques: ["llm_judge"],
      }),
    );

    expect(header).toContain("Rewrite");
    expect(header).toContain("10 of 42 cases shown");
    expect(header).toContain("$0.0031");
    expect(header).not.toContain("single sample");
    expect(header).not.toContain("LLM Judge");
  });

  it("carries the hand-off flag", () => {
    expect(
      rewriteHeader(provenance({ metering_handoff_failed: true })),
    ).toContain("spend not recorded");
  });
});

describe("formatSpend", () => {
  it("never renders a real cost as zero", () => {
    expect(formatSpend(0.00005)).toBe("<$0.0001");
    expect(formatSpend(0)).toBe("$0.0000");
    expect(formatSpend(0.0412)).toBe("$0.0412");
  });
});

describe("caseSpendLine", () => {
  it("reports nothing when the case measured nothing", () => {
    expect(caseSpendLine(caseResult("a"))).toBeNull();
  });

  it("reports only the parts the case carries", () => {
    const line = caseSpendLine(
      caseResult("a", {
        latency_ms: 840,
        usage: { input_tokens: 100, output_tokens: 50, total_tokens: 150 },
      }),
    );

    expect(line).toContain("840 ms");
    expect(line).toContain("150 tokens");
    expect(line).not.toContain("$");
  });
});

describe("formatAvgScore", () => {
  it("renders a dash when nothing was scored", () => {
    expect(formatAvgScore(null)).toBe("—");
  });

  it("keeps a decimal only when it carries a digit", () => {
    expect(formatAvgScore(0.8)).toBe("80%");
    expect(formatAvgScore(0.875)).toBe("87.5%");
    expect(formatAvgScore(0.07)).toBe("7%");
  });
});

describe("caseStatusLabel", () => {
  it("names the verdict of a scored case", () => {
    expect(caseStatusLabel(caseResult("a"))).toBe("Passed");
    expect(caseStatusLabel(caseResult("a", { verdict: "inconclusive" }))).toBe(
      "Inconclusive",
    );
  });

  it("reuses the app's wording for a case that never got a verdict", () => {
    expect(
      caseStatusLabel(caseResult("a", { status: "execution_failed", verdict: null })),
    ).toBe("Execution failed");
    expect(caseStatusLabel(caseResult("a", { status: "skipped", verdict: null }))).toBe(
      "Skipped",
    );
  });
});

describe("metricOutcomeLabel", () => {
  it("separates a dataset gap from a check that could not run", () => {
    expect(metricOutcomeLabel({ score: null, passed: false, not_applicable: true })).toBe(
      "N/A — no expected output",
    );
    expect(metricOutcomeLabel({ score: null, passed: false, not_evaluated: true })).toBe(
      "Not evaluated",
    );
    expect(metricOutcomeLabel({ score: null, passed: false, error: true })).toBe(
      "Could not run",
    );
    expect(metricOutcomeLabel({ score: 0, passed: false })).toBe("Failed");
  });
});

describe("metricScoreLabel", () => {
  it("shows a number only for a check that produced one", () => {
    expect(metricScoreLabel({ score: 0.6, passed: true })).toBe("60%");
    expect(metricScoreLabel({ score: true, passed: true })).toBeNull();
    expect(metricScoreLabel({ score: false, passed: false })).toBeNull();
    expect(metricScoreLabel({ score: null, passed: false })).toBeNull();
  });
});

describe("soleMetricEchoesVerdict", () => {
  const withMetrics = (
    metrics: Record<string, PromptEvalMetric>,
    overrides: Partial<PromptEvalCaseResult> = {},
  ) => caseResult("a", { metrics, ...overrides });

  it("reports a lone check that only restated the verdict", () => {
    expect(
      soleMetricEchoesVerdict(withMetrics({ llm_judge: { score: 1, passed: true } })),
    ).toBe(true);
  });

  it("keeps a lone check that says why the case is inconclusive", () => {
    const inconclusive = { verdict: "inconclusive" as const, passed: false };

    expect(
      soleMetricEchoesVerdict(
        withMetrics({ nli_eval: { score: null, passed: false, error: true } }, inconclusive),
      ),
    ).toBe(false);
    expect(
      soleMetricEchoesVerdict(
        withMetrics(
          { nli_eval: { score: null, passed: false, not_applicable: true } },
          inconclusive,
        ),
      ),
    ).toBe(false);
  });

  it("keeps every check once more than one ran", () => {
    expect(
      soleMetricEchoesVerdict(
        withMetrics({
          contains: { score: true, passed: true },
          llm_judge: { score: 1, passed: true },
        }),
      ),
    ).toBe(false);
  });
});

describe("joinPairedRuns", () => {
  it("counts each case's move and states how many were compared", () => {
    const before = response([
      caseResult("a", { verdict: "failed", passed: false }),
      caseResult("b"),
      caseResult("c", { verdict: "passed" }),
    ]);
    const after = response([
      caseResult("a", { verdict: "passed" }),
      caseResult("b"),
      caseResult("c", { verdict: "failed", passed: false }),
    ]);

    expect(joinPairedRuns(before, after)).toMatchObject({
      compared: 3,
      improved: 1,
      regressed: 1,
      unchanged: 1,
    });
  });

  it("shows a case missing from one side but leaves it out of the counts", () => {
    const before = response([caseResult("a"), caseResult("b")]);
    const after = response([caseResult("a")]);
    const joined = joinPairedRuns(before, after);

    expect(joined.rows).toHaveLength(2);
    expect(joined.rows[1]).toEqual({
      caseId: "b",
      baseline: before.results[1],
      suggestion: null,
    });
    expect(joined.compared).toBe(1);
  });

  it("leaves a case that never got a verdict out of the counts", () => {
    const before = response([
      caseResult("a", { status: "execution_failed", verdict: null }),
    ]);
    const after = response([caseResult("a")]);

    expect(joinPairedRuns(before, after).compared).toBe(0);
  });
});

describe("spendComparisonLine", () => {
  const measured = (
    caseId: string,
    latency: number,
    tokens: number,
    cost: number,
  ) =>
    caseResult(caseId, {
      latency_ms: latency,
      usage: { input_tokens: tokens, output_tokens: 0, total_tokens: tokens },
      cost_usd: cost,
    });

  it("reports each metric plainly when every compared pair carries it", () => {
    const before = response([
      measured("a", 1600, 8000, 0.03),
      measured("b", 1200, 4345, 0.0112),
    ]);
    const after = response([
      measured("a", 1200, 6000, 0.02),
      measured("b", 1000, 3870, 0.012),
    ]);

    const line = spendComparisonLine(joinPairedRuns(before, after));

    expect(line).toContain("Model calls over 2 compared cases:");
    expect(line).toContain("avg 1.40 s → 1.10 s");
    expect(line).toMatch(/12[,.\s ]?345 → 9[,.\s ]?870 tokens/);
    expect(line).toContain("$0.0412 → $0.0320");
    expect(line).not.toContain("of 2 cases");
  });

  it("names its own coverage when only some pairs carry a metric", () => {
    const before = response([
      measured("a", 1000, 100, 0.01),
      caseResult("b", { latency_ms: 1000, usage: null, cost_usd: null }),
    ]);
    const after = response([
      measured("a", 1000, 200, 0.02),
      caseResult("b", { latency_ms: 1000, usage: null, cost_usd: null }),
    ]);

    const line = spendComparisonLine(joinPairedRuns(before, after));

    expect(line).toContain("100 → 200 tokens (1 of 2 cases)");
    expect(line).toContain("$0.0100 → $0.0200 (1 of 2 cases)");
    expect(line).toContain("avg 1.00 s → 1.00 s");
    expect(line).not.toContain("avg 1.00 s → 1.00 s (1 of 2 cases)");
  });

  it("leaves a case that never ran on one side out of the comparison", () => {
    const before = response([
      measured("a", 1000, 100, 0.01),
      caseResult("b", { status: "execution_failed", verdict: null }),
    ]);
    const after = response([
      measured("a", 1000, 200, 0.02),
      measured("b", 1000, 999, 0.99),
    ]);

    expect(spendComparisonLine(joinPairedRuns(before, after))).toContain(
      "Model calls over 1 compared case:",
    );
  });

  it("says nothing when no compared pair measured anything", () => {
    const before = response([caseResult("a")]);
    const after = response([caseResult("a")]);

    expect(spendComparisonLine(joinPairedRuns(before, after))).toBeNull();
  });
});

describe("compareRuns", () => {
  const scored = (caseId: string, verdict: PromptCaseVerdict) =>
    caseResult(caseId, { verdict, passed: verdict === "passed" });

  const run = (results: PromptEvalCaseResult[], ids?: string[]) =>
    response(results, { evaluated_case_ids: ids ?? results.map((r) => r.case_id) });

  it("reports the counts with no reason when the same cases finished on both sides", () => {
    const before = run([
      scored("a", "failed"),
      scored("b", "failed"),
      scored("c", "passed"),
    ]);
    const after = run([
      scored("a", "passed"),
      scored("b", "passed"),
      scored("c", "passed"),
    ]);

    expect(compareRuns(before, after)).toMatchObject({
      incomplete: null,
      comparison: { improved: 2, regressed: 0, unchanged: 1 },
    });
  });

  it("refuses to compare two runs of different cases", () => {
    const before = run([scored("a", "failed"), scored("b", "failed")]);
    const after = run([scored("a", "passed"), scored("c", "passed")]);

    expect(compareRuns(before, after).incomplete).toBe(
      "The two runs evaluated different cases.",
    );
  });

  it("refuses a run whose case list repeats an id", () => {
    const before = run([scored("a", "failed"), scored("a", "failed")], ["a", "a"]);
    const after = run([scored("a", "passed")], ["a"]);

    expect(compareRuns(before, after).incomplete).toBe(
      "The two runs evaluated different cases.",
    );
  });

  it("refuses a pair where a case never ran on one side", () => {
    const before = run([
      scored("a", "passed"),
      caseResult("b", { status: "execution_failed", verdict: null }),
    ]);
    const after = run([scored("a", "passed"), scored("b", "passed")]);

    expect(compareRuns(before, after).incomplete).toBe(
      "1 case did not finish on one side.",
    );
  });

  it("refuses a pair where a scored case came back without a verdict", () => {
    const before = run([scored("a", "passed"), scored("b", "failed")]);
    const after = run([scored("a", "passed"), caseResult("b", { verdict: null })]);

    expect(compareRuns(before, after).incomplete).toBe(
      "1 case did not finish on one side.",
    );
  });

  it("counts every unfinished case in the reason it gives", () => {
    const before = run([
      caseResult("a", { status: "scoring_failed", verdict: null }),
      caseResult("b", { status: "skipped", verdict: null }),
    ]);
    const after = run([scored("a", "passed"), scored("b", "passed")]);

    expect(compareRuns(before, after).incomplete).toBe(
      "2 cases did not finish on one side.",
    );
  });
});
