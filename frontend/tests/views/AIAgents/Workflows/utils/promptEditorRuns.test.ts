import { describe, expect, it } from "vitest";
import type { PromptEvalCaseResult } from "@/interfaces/promptEditor.interface";
import {
  evalKeyOf,
  failedCasesOf,
  failuresKeyOf,
  isOptimizeCurrent,
  type OptimizeRequest,
} from "@/views/AIAgents/Workflows/utils/promptEditorRuns";

const result = (
  caseId: string,
  passed: boolean,
  actual = "actual",
): PromptEvalCaseResult =>
  ({
    case_id: caseId,
    input: `in-${caseId}`,
    expected: `exp-${caseId}`,
    actual,
    metrics: {},
    passed,
  }) as PromptEvalCaseResult;

describe("evalKeyOf", () => {
  it("ignores the order techniques were toggled in", () => {
    expect(evalKeyOf("p", "prov", ["contains", "exact_match"])).toBe(
      evalKeyOf("p", "prov", ["exact_match", "contains"]),
    );
  });

  it("separates runs that differ in prompt, provider or technique set", () => {
    const base = evalKeyOf("p", "prov", ["contains"]);

    expect(evalKeyOf("other", "prov", ["contains"])).not.toBe(base);
    expect(evalKeyOf("p", "other", ["contains"])).not.toBe(base);
    expect(evalKeyOf("p", "prov", ["contains", "nli_eval"])).not.toBe(base);
  });
});

describe("failuresKeyOf", () => {
  it("keeps only the failures, in the shape the optimizer is sent", () => {
    const cases = failedCasesOf([result("a", false), result("b", true)]);

    expect(cases).toEqual([
      { input: "in-a", expected: "exp-a", actual: "actual" },
    ]);
  });

  it("separates two runs of the same inputs that failed differently", () => {
    const first = failuresKeyOf(failedCasesOf([result("a", false, "X")]));
    const second = failuresKeyOf(failedCasesOf([result("a", false, "Y")]));

    expect(first).not.toBe(second);
  });

  it("is null when nothing failed", () => {
    expect(failuresKeyOf([])).toBeNull();
    expect(failuresKeyOf(failedCasesOf([result("a", true)]))).toBeNull();
  });
});

describe("isOptimizeCurrent", () => {
  const FAILURES = failuresKeyOf(failedCasesOf([result("a", false, "X")]));

  const request = (overrides: Partial<OptimizeRequest> = {}): OptimizeRequest => ({
    prompt: "prompt",
    providerId: "prov",
    instructions: "",
    sourceFailuresKey: FAILURES,
    ...overrides,
  });

  const current = (overrides: Partial<Parameters<typeof isOptimizeCurrent>[1]> = {}) => ({
    prompt: "prompt",
    providerId: "prov",
    instructions: "",
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
  ])("expires when the %s changes", (_label, change) => {
    expect(isOptimizeCurrent(request(), current(change))).toBe(false);
  });

  it("expires when the same inputs are re-evaluated into different failures", () => {
    const rerun = failuresKeyOf(failedCasesOf([result("a", false, "Y")]));

    expect(isOptimizeCurrent(request(), current({ failuresKey: rerun }))).toBe(
      false,
    );
  });

  it("expires when the evaluation supplying its failures becomes stale", () => {
    expect(isOptimizeCurrent(request(), current({ failuresKey: null }))).toBe(
      false,
    );
  });

  it("survives later failures when it was built without any", () => {
    const withoutFailures = request({ sourceFailuresKey: null });

    expect(isOptimizeCurrent(withoutFailures, current({ failuresKey: null }))).toBe(
      true,
    );
    expect(isOptimizeCurrent(withoutFailures, current())).toBe(true);
  });
});
