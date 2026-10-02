import { describe, expect, it } from "vitest";
import type {
  PromptEvalCaseResult,
  PromptEvalResponse,
  PromptEvalSummary,
  PromptRunProvenance,
} from "@/interfaces/promptEditor.interface";
import {
  caseStatusLabel,
  formatAvgScore,
  joinPairedRuns,
  metricOutcomeLabel,
  snapshotHeader,
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
    ...overrides,
  }) as PromptEvalCaseResult;

const response = (results: PromptEvalCaseResult[]): PromptEvalResponse => ({
  results,
  summary: summary(),
  provenance: provenance(),
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

    expect(header).toContain("Snapshot · 10 of 42 cases");
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
    expect(header).toContain("spend hand-off failed");
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
});

describe("formatAvgScore", () => {
  it("renders a dash when nothing was scored", () => {
    expect(formatAvgScore(null)).toBe("—");
  });

  it("renders a percentage to one decimal", () => {
    expect(formatAvgScore(0.8)).toBe("80.0%");
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
