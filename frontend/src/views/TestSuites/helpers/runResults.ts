import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";

export type CaseStatus = "passed" | "failed" | "not_scored";

export const hasMetrics = (result: TestResult): boolean =>
  !!result.metrics && Object.keys(result.metrics).length > 0;

// No metrics means no score, whatever the stored status claims.
export const isResultNotScored = (result: TestResult): boolean =>
  !hasMetrics(result) || (!!result.status && result.status !== "scored");

export const isResultPassed = (result: TestResult): boolean =>
  hasMetrics(result) &&
  !isResultNotScored(result) &&
  Object.values(result.metrics!).every((m) => m.passed);

export const isResultFailed = (result: TestResult): boolean =>
  !isResultPassed(result) && !isResultNotScored(result);

export const notScoredLabel = (result: TestResult): string => {
  if (result.status === "skipped") return "Skipped";
  if (result.status === "scoring_failed") return "Scoring failed";
  if (result.status === "execution_failed") return "Execution failed";
  return "Not scored";
};

// A case's status reflects its turn-level Tool Usage results too: a tool failure
// fails the case, and a tool pass can score an otherwise-unscored case.
export const caseStatusFor = (
  result: TestResult,
  toolResults: TestToolRuleResult[],
): CaseStatus => {
  const toolFailed = toolResults.some((t) => t.status === "failed");
  const toolPassed = toolResults.some((t) => t.status === "passed");
  if (toolFailed) return "failed";
  const passed = isResultPassed(result) || (isResultNotScored(result) && toolPassed);
  if (passed) return "passed";
  if (isResultFailed(result)) return "failed";
  return "not_scored";
};

export const runAvgAccuracy = (run: TestRun): number | null => {
  const summaryMetrics = run.summary_metrics as
    | Record<string, { accuracy?: number }>
    | undefined;
  const scored = Object.values(summaryMetrics ?? {}).filter(
    (m) => typeof m.accuracy === "number",
  );
  if (!scored.length) return null;
  return scored.reduce((sum, m, _, arr) => sum + (m.accuracy ?? 0) / arr.length, 0);
};
