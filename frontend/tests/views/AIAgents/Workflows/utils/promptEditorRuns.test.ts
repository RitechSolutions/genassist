import { describe, expect, it } from "vitest";
import type {
  PromptEvalCaseResult,
  PromptEvalMetric,
} from "@/interfaces/promptEditor.interface";
import {
  acceptPayloadOf,
  canonicalJson,
  clipCodePoints,
  evalKeyOf,
  failedCaseCount,
  failedCasesOf,
  failuresDrifted,
  failuresKeyOf,
  feedbackOf,
  isOptimizeCurrent,
  measurementContextKeyOf,
  optimizeKeyOf,
  staleOf,
  MAX_FAILURE_FEEDBACK_CHARS,
  type EvalKeyInputs,
  type MeasurementContextInputs,
  type OptimizeRequest,
} from "@/views/AIAgents/Workflows/utils/promptEditorRuns";

const result = (
  caseId: string,
  overrides: Partial<PromptEvalCaseResult> = {},
): PromptEvalCaseResult =>
  ({
    case_id: caseId,
    input: `in-${caseId}`,
    expected: `exp-${caseId}`,
    actual: "actual",
    actual_truncated: false,
    status: "scored",
    error: null,
    metrics: {},
    verdict: "failed",
    passed: false,
    case_score: 0,
    scored_metrics: 1,
    failed_metrics: 1,
    errored_metrics: 0,
    not_evaluated_metrics: 0,
    not_applicable_metrics: 0,
    ...overrides,
  }) as PromptEvalCaseResult;

const evalInputs = (overrides: Partial<EvalKeyInputs> = {}): EvalKeyInputs => ({
  prompt: "p",
  providerId: "prov",
  providerRevision: "",
  techniques: ["contains"],
  techniqueConfigs: {},
  caseIds: null,
  maxCases: 10,
  caseRowsKey: "rows",
  ...overrides,
});

describe("canonicalJson", () => {
  it("keys the same object identically however its keys were inserted", () => {
    expect(canonicalJson({ b: 1, a: { d: 2, c: 3 } })).toBe(
      canonicalJson({ a: { c: 3, d: 2 }, b: 1 }),
    );
  });

  it("keeps array order, which carries meaning for case ids", () => {
    expect(canonicalJson(["b", "a"])).not.toBe(canonicalJson(["a", "b"]));
  });

  it("distinguishes null from an empty object", () => {
    expect(canonicalJson(null)).not.toBe(canonicalJson({}));
  });
});

describe("evalKeyOf", () => {
  it("ignores the order techniques were toggled in", () => {
    expect(evalKeyOf(evalInputs({ techniques: ["contains", "exact_match"] }))).toBe(
      evalKeyOf(evalInputs({ techniques: ["exact_match", "contains"] })),
    );
  });

  it("ignores the order a technique config was built in", () => {
    expect(
      evalKeyOf(
        evalInputs({
          techniqueConfigs: {
            not_contains: { phrases: ["a"] },
            field_equals: { field: "outputs" },
          },
        }),
      ),
    ).toBe(
      evalKeyOf(
        evalInputs({
          techniqueConfigs: {
            field_equals: { field: "outputs" },
            not_contains: { phrases: ["a"] },
          },
        }),
      ),
    );
  });

  it.each([
    ["prompt", { prompt: "other" }],
    ["provider", { providerId: "other" }],
    ["provider revision", { providerRevision: "2026-09-17T10:00:00Z" }],
    ["technique set", { techniques: ["contains", "nli_eval"] }],
    ["technique config", { techniqueConfigs: { not_contains: { phrases: ["x"] } } }],
    ["case selection", { caseIds: ["c1"] }],
    ["case count", { maxCases: 25 }],
    ["gold dataset", { caseRowsKey: "edited" }],
  ])("separates runs that differ in %s", (_label, change) => {
    expect(evalKeyOf(evalInputs(change))).not.toBe(evalKeyOf(evalInputs()));
  });

  it("separates cases the server picked from the same list sent explicitly", () => {
    expect(evalKeyOf(evalInputs({ caseIds: null }))).not.toBe(
      evalKeyOf(evalInputs({ caseIds: ["c1"] })),
    );
  });

  it("separates unloaded cases from a loaded but empty dataset", () => {
    expect(evalKeyOf(evalInputs({ caseRowsKey: null }))).not.toBe(
      evalKeyOf(evalInputs({ caseRowsKey: canonicalJson([]) })),
    );
  });
});

describe("staleOf", () => {
  it("is true exactly when the run no longer describes the current inputs", () => {
    const current = evalKeyOf(evalInputs());

    expect(staleOf(current, current)).toBe(false);
    expect(staleOf(evalKeyOf(evalInputs({ prompt: "edited" })), current)).toBe(true);
  });
});

describe("failedCasesOf", () => {
  it("sends only graded failures, in the shape the optimizer takes", () => {
    const cases = failedCasesOf([
      result("a"),
      result("b", { verdict: "passed", passed: true }),
      result("c", { verdict: "inconclusive" }),
      result("d", { status: "execution_failed", verdict: null }),
    ]);

    expect(cases).toEqual([
      { caseId: "a", actual: "actual", failedMetrics: [], feedback: null },
    ]);
  });

  it("names the techniques that rejected the reply in a fixed order, skipping the ones that had nothing to grade", () => {
    const metrics: Record<string, PromptEvalMetric> = {
      nli_eval: { score: false, passed: false },
      contains: { score: false, passed: false },
      json_match: { score: true, passed: true },
      exact_match: { score: null, passed: false, not_applicable: true },
    };

    expect(failedCasesOf([result("a", { metrics })])[0].failedMetrics).toEqual([
      "contains",
      "nli_eval",
    ]);
  });

  it("treats a server that sends no verdict as having no failures", () => {
    expect(failedCasesOf([result("a", { verdict: undefined })])).toEqual([]);
  });

  it("caps the list at the bound the optimize endpoint accepts", () => {
    const failing = Array.from({ length: 14 }, (_, i) => result(`c${i}`));

    expect(failedCasesOf(failing)).toHaveLength(10);
    expect(failedCaseCount(failing)).toBe(14);
  });

  it("passes a long actual through unshortened, as the server bounded it", () => {
    const actual = "x".repeat(16_000);

    expect(failedCasesOf([result("a", { actual })])[0].actual).toBe(actual);
  });
});

describe("clipCodePoints", () => {
  it("counts an astral character once, as the server bound does", () => {
    expect(clipCodePoints("😀😀😀", 2)).toBe("😀😀");
  });

  it("leaves a string inside the bound alone", () => {
    expect(clipCodePoints("abc", 3)).toBe("abc");
  });
});

describe("feedbackOf", () => {
  it("quotes only the graders that failed and said something, in a fixed order", () => {
    const metrics: Record<string, PromptEvalMetric> = {
      nli_eval: { score: false, passed: false, comment: "unsupported claim" },
      contains: { score: false, passed: false, comment: "missing the link" },
      json_match: { score: true, passed: true, comment: "matched" },
      exact_match: { score: false, passed: false },
    };

    expect(feedbackOf(metrics)).toBe(
      "contains: missing the link; nli_eval: unsupported claim",
    );
  });

  it("is null when no failing grader left a comment", () => {
    expect(feedbackOf({})).toBeNull();
    expect(feedbackOf({ contains: { score: false, passed: false } })).toBeNull();
  });

  it("clips to the bound the optimize endpoint accepts", () => {
    const comment = "x".repeat(600);
    const feedback = feedbackOf({
      contains: { score: false, passed: false, comment },
    });

    expect(Array.from(feedback ?? "")).toHaveLength(MAX_FAILURE_FEEDBACK_CHARS);
  });
});

describe("measurementContextKeyOf", () => {
  const contextInputs = (
    overrides: Partial<MeasurementContextInputs> = {},
  ): MeasurementContextInputs => ({
    providerId: "prov",
    providerRevision: "",
    techniques: ["contains"],
    techniqueConfigs: {},
    caseIds: null,
    maxCases: 10,
    caseRowsKey: "rows",
    holdoutIds: null,
    ...overrides,
  });

  it("ignores the order techniques were toggled in", () => {
    expect(
      measurementContextKeyOf(
        contextInputs({ techniques: ["contains", "exact_match"] }),
      ),
    ).toBe(
      measurementContextKeyOf(
        contextInputs({ techniques: ["exact_match", "contains"] }),
      ),
    );
  });

  it("separates scores taken either side of a split", () => {
    expect(measurementContextKeyOf(contextInputs({ holdoutIds: ["c1"] }))).not.toBe(
      measurementContextKeyOf(contextInputs()),
    );
  });
});

describe("failuresKeyOf", () => {
  it("separates two runs of the same inputs that failed differently", () => {
    const first = failuresKeyOf(failedCasesOf([result("a", { actual: "X" })]));
    const second = failuresKeyOf(failedCasesOf([result("a", { actual: "Y" })]));

    expect(first).not.toBe(second);
  });

  it("is null when nothing failed", () => {
    expect(failuresKeyOf([])).toBeNull();
    expect(
      failuresKeyOf(failedCasesOf([result("a", { verdict: "passed", passed: true })])),
    ).toBeNull();
  });
});

describe("isOptimizeCurrent", () => {
  const FAILURES = failuresKeyOf(failedCasesOf([result("a", { actual: "X" })]));

  const optimizeInputs = (overrides = {}) => ({
    prompt: "prompt",
    providerId: "prov",
    providerRevision: "",
    instructions: "",
    caseSplit: null,
    caseRowsKey: "rows",
    techniques: ["contains"],
    techniqueConfigs: {},
    sourceEvalKey: "e",
    ...overrides,
  });

  const request = (overrides: Partial<OptimizeRequest> = {}): OptimizeRequest => ({
    key: optimizeKeyOf(optimizeInputs()),
    prompt: "prompt",
    providerId: "prov",
    instructions: "",
    sourceFailuresKey: FAILURES,
    caseSplit: null,
    techniques: ["contains"],
    techniqueConfigs: {},
    ...overrides,
  });

  it("holds while every keyed input is unchanged", () => {
    expect(isOptimizeCurrent(request(), optimizeKeyOf(optimizeInputs()))).toBe(true);
  });

  it("ignores the order techniques were toggled in", () => {
    expect(optimizeKeyOf(optimizeInputs({ techniques: ["contains", "exact_match"] }))).toBe(
      optimizeKeyOf(optimizeInputs({ techniques: ["exact_match", "contains"] })),
    );
  });

  it.each([
    ["prompt", { prompt: "edited" }],
    ["provider", { providerId: "other" }],
    ["instructions", { instructions: "Be terse." }],
    ["gold dataset", { caseRowsKey: "edited" }],
    ["split", { caseSplit: { holdoutShare: 0.5, holdoutIds: ["c1"] } }],
    ["techniques", { techniques: ["exact_match"] }],
    ["provider revision", { providerRevision: "2026-09-17T10:00:00Z" }],
    ["technique config", { techniqueConfigs: { not_contains: { phrases: ["x"] } } }],
    ["evaluation it was built from", { sourceEvalKey: "other" }],
  ])("expires when the %s changes", (_label, change) => {
    expect(
      isOptimizeCurrent(request(), optimizeKeyOf(optimizeInputs(change))),
    ).toBe(false);
  });

  it("no longer expires on the failure set alone, which is advisory now", () => {
    expect(
      isOptimizeCurrent(
        request({ sourceFailuresKey: "re-scored" }),
        optimizeKeyOf(optimizeInputs()),
      ),
    ).toBe(true);
  });
});

describe("failuresDrifted", () => {
  const FAILURES = failuresKeyOf(failedCasesOf([result("a", { actual: "X" })]));

  const request = (sourceFailuresKey: string | null): OptimizeRequest => ({
    key: "k",
    prompt: "prompt",
    providerId: "prov",
    instructions: "",
    sourceFailuresKey,
    caseSplit: null,
    techniques: ["contains"],
    techniqueConfigs: {},
  });

  it("reports a base that was re-scored into different failures", () => {
    const rerun = failuresKeyOf(failedCasesOf([result("a", { actual: "Y" })]));

    expect(failuresDrifted(request(FAILURES), rerun)).toBe(true);
    expect(failuresDrifted(request(FAILURES), null)).toBe(true);
  });

  it("stays quiet while the failures behind it are the ones it was sent", () => {
    expect(failuresDrifted(request(FAILURES), FAILURES)).toBe(false);
    expect(failuresDrifted(request(null), null)).toBe(false);
  });
});

describe("acceptPayloadOf", () => {
  it("saves the suggestion on screen, not the text the optimizer returned", () => {
    expect(acceptPayloadOf("edited suggestion", "draft", 3)).toEqual({
      content: "edited suggestion",
      draftAtSubmit: "draft",
      token: 3,
    });
  });
});
