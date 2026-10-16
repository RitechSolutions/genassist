import { describe, expect, it } from "vitest";
import type {
  PromptEvalCaseResult,
  PromptEvalResponse,
} from "@/interfaces/promptEditor.interface";
import { joinPairedRuns } from "@/views/AIAgents/Workflows/utils/promptEditorResults";
import type {
  EvalRunState,
  SuggestedRunState,
} from "@/views/AIAgents/Workflows/utils/promptEditorRuns";
import {
  MAX_ROUND_DIFF_CHARS,
  MAX_ROUND_REGRESSION_FEEDBACK_CHARS,
  attachKeptRun,
  baselineOf,
  optimizerHistoryOf,
  promptDiffSummary,
  regressionsOf,
  roundRunOf,
  type Round,
  type RoundCounts,
} from "@/views/AIAgents/Workflows/utils/promptEditorRounds";

const caseResult = (
  caseId: string,
  verdict: PromptEvalCaseResult["verdict"],
  comment?: string,
): PromptEvalCaseResult =>
  ({
    case_id: caseId,
    input: "in",
    expected: "exp",
    actual: "act",
    actual_truncated: false,
    status: "scored",
    error: null,
    metrics: comment
      ? { contains: { passed: false, comment } as never }
      : {},
    verdict,
    passed: verdict === "passed",
    case_score: 1,
    scored_metrics: 1,
    failed_metrics: verdict === "failed" ? 1 : 0,
    errored_metrics: 0,
    not_evaluated_metrics: 0,
    not_applicable_metrics: 0,
  }) as PromptEvalCaseResult;

const response = (results: PromptEvalCaseResult[]): PromptEvalResponse =>
  ({
    results,
    summary: {},
    provenance: { evaluated_case_ids: results.map((r) => r.case_id) },
  }) as unknown as PromptEvalResponse;

const run = (key: string): SuggestedRunState =>
  ({
    key,
    caseIds: null,
    results: response([]),
    providerFallback: undefined,
  }) as SuggestedRunState;

const counts = (overrides: Partial<RoundCounts> = {}): RoundCounts => ({
  improved: 0,
  regressed: 0,
  unchanged: 0,
  compared: 0,
  ...overrides,
});

const round = (overrides: Partial<Round> = {}): Round => ({
  id: 1,
  source: {
    request: { prompt: "before" },
    result: { suggested_prompt: "after", explanation: "why", outcome: "changed" },
  } as Round["source"],
  suggestion: "after",
  run: run("r"),
  incomplete: null,
  counts: counts({ improved: 2, compared: 2 }),
  regressions: [],
  contextKey: "ctx",
  ...overrides,
});

describe("promptDiffSummary", () => {
  it("keeps only changed lines, prefixed and in document order", () => {
    expect(promptDiffSummary("a\nb\nc\n", "a\nB\nc\n")).toBe("- b\n+ B");
  });

  it("is empty when nothing changed", () => {
    expect(promptDiffSummary("same\n", "same\n")).toBe("");
  });

  it("never exceeds the bound, marker included", () => {
    const summary = promptDiffSummary("", "x\n".repeat(2_000));

    expect(Array.from(summary).length).toBeLessThanOrEqual(MAX_ROUND_DIFF_CHARS);
    expect(summary.endsWith(" […]")).toBe(true);
  });

  it("clips by code point, so an astral character is never split", () => {
    const summary = promptDiffSummary("", "𝔘".repeat(50), 10);

    expect(Array.from(summary).length).toBeLessThanOrEqual(10);
    expect(summary).not.toContain("�");
  });
});

describe("regressionsOf", () => {
  it("selects only the cases that ranked lower, with their grader feedback", () => {
    const comparison = joinPairedRuns(
      response([
        caseResult("up", "failed"),
        caseResult("down", "passed"),
        caseResult("flat", "passed"),
      ]),
      response([
        caseResult("up", "passed"),
        caseResult("down", "failed", "missing the phrase"),
        caseResult("flat", "passed"),
      ]),
    );

    expect(regressionsOf(comparison)).toEqual([
      { caseId: "down", feedback: "contains: missing the phrase" },
    ]);
  });

  it("ignores a case that only one side scored", () => {
    const comparison = joinPairedRuns(
      response([caseResult("only", "passed")]),
      response([]),
    );

    expect(regressionsOf(comparison)).toEqual([]);
  });

  it("clips feedback to the bound a round's payload allows", () => {
    const comparison = joinPairedRuns(
      response([caseResult("down", "passed")]),
      response([caseResult("down", "failed", "f".repeat(400))]),
    );

    const [regression] = regressionsOf(comparison);

    expect(Array.from(regression.feedback ?? "")).toHaveLength(
      MAX_ROUND_REGRESSION_FEEDBACK_CHARS,
    );
  });

  it("caps the list at five", () => {
    const ids = Array.from({ length: 8 }, (_, i) => `c${i}`);
    const comparison = joinPairedRuns(
      response(ids.map((id) => caseResult(id, "passed"))),
      response(ids.map((id) => caseResult(id, "failed"))),
    );

    expect(regressionsOf(comparison)).toHaveLength(5);
  });
});

describe("optimizerHistoryOf", () => {
  it("excludes rounds that were never scored, were incomplete, or ran elsewhere", () => {
    const rounds = [
      round({ id: 1, run: null }),
      round({ id: 2, incomplete: "The two runs evaluated different cases." }),
      round({ id: 3, contextKey: "other" }),
    ];

    expect(optimizerHistoryOf(rounds, "ctx")).toEqual([]);
  });

  it("takes the three most recent and orders them by net change, worst first", () => {
    const rounds = [
      round({ id: 1, counts: counts({ improved: 5 }) }),
      round({ id: 2, counts: counts({ improved: 1 }) }),
      round({ id: 3, counts: counts({ improved: 4, regressed: 1 }) }),
      round({ id: 4, counts: counts({ regressed: 5 }) }),
    ];

    expect(optimizerHistoryOf(rounds, "ctx").map((a) => a.improved)).toEqual([
      1, 4, 5,
    ]);
  });

  it("carries the counts, a diff of what the round changed, and the feedback", () => {
    const rounds = [
      round({
        regressions: [{ caseId: "c1", feedback: "contains: missing the link" }],
        counts: counts({ improved: 2, regressed: 1, unchanged: 3 }),
      }),
    ];

    const [attempt] = optimizerHistoryOf(rounds, "ctx");

    expect(attempt.improved).toBe(2);
    expect(attempt.regressed).toBe(1);
    expect(attempt.unchanged).toBe(3);
    expect(attempt.explanation).toBe("why");
    expect(attempt.diff_summary).toBe("- before\n+ after");
    expect(attempt.regressions).toEqual([
      { case_id: "c1", feedback: "contains: missing the link" },
    ]);
  });

  it("sends no explanation for a round whose suggestion the user edited, since the diff describes the user's text", () => {
    const [attempt] = optimizerHistoryOf(
      [round({ suggestion: "after, edited" })],
      "ctx",
    );

    expect(attempt.explanation).toBe("");
    expect(attempt.diff_summary).toContain("+ after, edited");
  });
});

describe("roundRunOf", () => {
  it("finds the scored run of a text at any position in the chain", () => {
    const older = run("older");
    const rounds = [
      round({ id: 2, suggestion: "second" }),
      round({ id: 1, suggestion: "first", run: older }),
    ];

    expect(roundRunOf(rounds, "ctx", "first")).toBe(older);
  });

  it("ignores a round scored under other settings or never scored", () => {
    const rounds = [
      round({ id: 2, suggestion: "text", contextKey: "other" }),
      round({ id: 1, suggestion: "text", run: null }),
    ];

    expect(roundRunOf(rounds, "ctx", "text")).toBeNull();
    expect(roundRunOf([round()], "ctx", "missing")).toBeNull();
  });
});

describe("baselineOf", () => {
  const evalRun = { key: "draft" } as EvalRunState;

  it("prefers the newest scored round and names it by position", () => {
    expect(baselineOf([round({ id: 2 })], "ctx", evalRun, false)).toEqual({
      run: round().run,
      label: "the previous round",
    });
  });

  it("skips an unscored newest round rather than falling through to the draft", () => {
    const rounds = [round({ id: 2, run: null }), round({ id: 1 })];

    expect(baselineOf(rounds, "ctx", evalRun, false)?.label).toBe(
      "an earlier round",
    );
  });

  it("skips a round scored under other settings", () => {
    const rounds = [round({ contextKey: "other" })];

    expect(baselineOf(rounds, "ctx", evalRun, false)).toEqual({
      run: evalRun,
      label: "the draft",
    });
  });

  it("uses the draft's run only while it is current", () => {
    expect(baselineOf([], "ctx", evalRun, true)).toBeNull();
    expect(baselineOf([], "ctx", null, false)).toBeNull();
  });
});

describe("attachKeptRun", () => {
  const keptRun = run("kept");
  const kept = (overrides: Partial<Round> = {}): Round =>
    round({
      id: 9,
      source: {
        request: { prompt: "s1" },
        result: { suggested_prompt: "s1", explanation: "", outcome: "unchanged" },
      } as Round["source"],
      suggestion: "s1",
      run: keptRun,
      counts: counts({ improved: 1, regressed: 1, compared: 3 }),
      regressions: [{ caseId: "c2", feedback: null }],
      contextKey: "now",
      ...overrides,
    });

  it("hands a scored keep to the unscored round that suggested it, without taking a slot", () => {
    const other = round({ id: 1, suggestion: "other" });
    const rounds = [
      round({ id: 2, suggestion: "s1", run: null, counts: null, contextKey: "old" }),
      other,
    ];

    const result = attachKeptRun(rounds, kept());

    expect(result).toEqual([
      {
        ...rounds[0],
        run: keptRun,
        counts: { improved: 1, regressed: 1, unchanged: 0, compared: 3 },
        regressions: [{ caseId: "c2", feedback: null }],
        contextKey: "now",
      },
      other,
    ]);
  });

  it("never overwrites a scored round, even when an older copy of the text is unscored", () => {
    const rounds = [
      round({ id: 3, suggestion: "s1" }),
      round({ id: 1, suggestion: "s1", run: null }),
    ];

    expect(attachKeptRun(rounds, kept())).toBe(rounds);
  });

  it("leaves the rounds alone for a changed, unscored or missing suggestion", () => {
    const rounds = [round({ id: 2, suggestion: "s1", run: null })];

    expect(attachKeptRun(rounds, kept({ suggestion: "s2" }))).toBe(rounds);
    expect(attachKeptRun(rounds, kept({ run: null }))).toBe(rounds);
    expect(attachKeptRun(rounds, null)).toBe(rounds);
  });
});
