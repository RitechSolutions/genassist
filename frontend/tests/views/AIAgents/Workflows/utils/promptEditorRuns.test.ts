import { describe, expect, it } from "vitest";
import type { PromptEvalCaseResult } from "@/interfaces/promptEditor.interface";
import {
  canonicalJson,
  evalKeyOf,
  failedCaseCount,
  failedCasesOf,
  failuresKeyOf,
  isOptimizeCurrent,
  optimizeKeyOf,
  staleOf,
  type EvalKeyInputs,
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

    expect(cases).toEqual([{ caseId: "a", actual: "actual" }]);
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
    instructions: "",
    caseSplit: null,
    caseRowsKey: "rows",
    ...overrides,
  });

  const request = (overrides: Partial<OptimizeRequest> = {}): OptimizeRequest => ({
    key: optimizeKeyOf(optimizeInputs()),
    prompt: "prompt",
    providerId: "prov",
    instructions: "",
    sourceFailuresKey: FAILURES,
    caseSplit: null,
    ...overrides,
  });

  const current = (overrides = {}) => ({
    key: optimizeKeyOf(optimizeInputs()),
    failuresKey: FAILURES,
    ...overrides,
  });

  it("holds while every input and the failures behind it are unchanged", () => {
    expect(isOptimizeCurrent(request(), current())).toBe(true);
  });

  it.each([
    ["prompt", { prompt: "edited" }],
    ["provider", { providerId: "other" }],
    ["instructions", { instructions: "Be terse." }],
    ["gold dataset", { caseRowsKey: "edited" }],
    ["split", { caseSplit: { holdoutShare: 0.5, holdoutIds: ["c1"] } }],
  ])("expires when the %s changes", (_label, change) => {
    expect(
      isOptimizeCurrent(request(), current({ key: optimizeKeyOf(optimizeInputs(change)) })),
    ).toBe(false);
  });

  it("expires when the same inputs are re-evaluated into different failures", () => {
    const rerun = failuresKeyOf(failedCasesOf([result("a", { actual: "Y" })]));

    expect(isOptimizeCurrent(request(), current({ failuresKey: rerun }))).toBe(false);
  });

  it("expires when the evaluation supplying its failures becomes stale", () => {
    expect(isOptimizeCurrent(request(), current({ failuresKey: null }))).toBe(false);
  });

  it("survives later failures when it was built without any", () => {
    const withoutFailures = request({ sourceFailuresKey: null });

    expect(isOptimizeCurrent(withoutFailures, current({ failuresKey: null }))).toBe(true);
    expect(isOptimizeCurrent(withoutFailures, current())).toBe(true);
  });
});
