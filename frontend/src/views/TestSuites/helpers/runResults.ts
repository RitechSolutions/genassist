import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type {
  RuleTechnique,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";

// Order rule sections the way the wizard lists the techniques.
const TECHNIQUE_ORDER: RuleTechnique[] = ["tool_used", "route_taken", "action_taken"];

// Rule-based techniques count rule checks (a rule per scope unit), not test cases.
export const isRuleTechnique = (technique: string): boolean =>
  TECHNIQUE_ORDER.includes(technique as RuleTechnique);

// Rule results arrive for every technique at once; each is displayed on its own.
export const groupByTechnique = (
  results: TestToolRuleResult[],
): [RuleTechnique, TestToolRuleResult[]][] => {
  const byTechnique = new Map<RuleTechnique, TestToolRuleResult[]>();
  for (const result of results) {
    const technique = result.technique ?? "tool_used";
    byTechnique.set(technique, [...(byTechnique.get(technique) ?? []), result]);
  }
  return TECHNIQUE_ORDER.filter((technique) => byTechnique.has(technique)).map(
    (technique) => [technique, byTechnique.get(technique) as TestToolRuleResult[]],
  );
};

// A turn-scoped result belongs to one case, so it is shown with that case; a
// conversation-scoped one has no single case to sit on.
export const isTurnScope = (scope: string): boolean =>
  scope === "every_turn" || scope === "specific_turn";

// Shown wherever a method's accuracy is null: nothing could be checked.
export const NOT_EVALUATED = "Not evaluated";

const countLabel = (count: number, noun: string): string =>
  `${count} ${noun}${count === 1 ? "" : "s"}`;

// A rule is graded once per scope unit, so the check count is rules x turns (plus
// one per conversation for a conversation-scoped rule) — never the turn count. The
// subline spells that out, so a number like "24 checks" over 12 turns is traceable.
export const ruleCheckSummary = (
  results: TestToolRuleResult[],
): { headline: string; subline: string } => {
  const passed = results.filter((result) => result.status === "passed").length;
  const failed = results.filter((result) => result.status === "failed").length;
  const evaluated = passed + failed;

  const ruleCount = new Set(results.map((result) => result.rule_id)).size;
  const turnChecks = results.filter((result) => isTurnScope(result.scope)).length;
  const conversationChecks = results.filter((result) => result.scope === "conversation").length;

  const parts = [countLabel(ruleCount, "rule")];
  if (turnChecks) parts.push(countLabel(turnChecks, "turn check"));
  if (conversationChecks) parts.push(countLabel(conversationChecks, "conversation check"));

  // Nothing checked has no pass rate, so it must not read as 0%.
  if (!evaluated) return { headline: NOT_EVALUATED, subline: parts.join(" · ") };

  const rate = Math.round((passed / evaluated) * 100);
  return {
    headline: `${passed} of ${evaluated} checks passed · ${rate}% pass rate`,
    subline: parts.join(" · "),
  };
};

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

export const notScoredLabel = (result: { status?: string | null }): string => {
  if (result.status === "skipped") return "Skipped";
  if (result.status === "scoring_failed") return "Scoring failed";
  if (result.status === "execution_failed") return "Execution failed";
  return "Not scored";
};

// A case's status reflects its turn-level rule results too (tool usage, route,
// action): a failed rule fails the case, and a passed rule can score an
// otherwise-unscored case.
export const caseStatusFor = (
  result: TestResult,
  ruleResults: TestToolRuleResult[],
): CaseStatus => {
  const ruleFailed = ruleResults.some((rule) => rule.status === "failed");
  const rulePassed = ruleResults.some((rule) => rule.status === "passed");
  if (ruleFailed) return "failed";
  const passed = isResultPassed(result) || (isResultNotScored(result) && rulePassed);
  if (passed) return "passed";
  if (isResultFailed(result)) return "failed";
  return "not_scored";
};

export interface TechniqueSummary {
  accuracy?: number | null;
  avg_score?: number | null;
  cases?: number;
}

// Run-level entries stored beside the methods: "_totals", a failed run's "error".
const isTechniqueKey = (key: string): boolean => key !== "error" && !key.startsWith("_");

// A run's per-method summaries, without the run-level entries.
export const techniqueSummaries = (
  run: TestRun | null | undefined,
): [string, TechniqueSummary][] =>
  Object.entries(run?.summary_metrics ?? {}).filter(
    (entry): entry is [string, TechniqueSummary] =>
      isTechniqueKey(entry[0]) && Boolean(entry[1]) && typeof entry[1] === "object",
  );

export const techniqueAccuracy = (summary: TechniqueSummary | undefined): number | null =>
  typeof summary?.accuracy === "number" ? summary.accuracy : null;

// The mean of each method's pass rate, shown as "Avg score". Not turns passed.
export const runAvgAccuracy = (run: TestRun): number | null => {
  const accuracies = techniqueSummaries(run)
    .map(([, summary]) => techniqueAccuracy(summary))
    .filter((accuracy): accuracy is number => accuracy !== null);
  if (!accuracies.length) return null;
  return accuracies.reduce((sum, accuracy) => sum + accuracy, 0) / accuracies.length;
};

// Turn-scoped rule results keyed by the case they graded.
const turnRulesByCase = (
  ruleResults: TestToolRuleResult[],
): Map<string, TestToolRuleResult[]> => {
  const byCase = new Map<string, TestToolRuleResult[]>();
  for (const rule of ruleResults) {
    if (!isTurnScope(rule.scope) || !rule.case_id) continue;
    byCase.set(rule.case_id, [...(byCase.get(rule.case_id) ?? []), rule]);
  }
  return byCase;
};

// Turns passed in a run, by the same per-case status the run details show.
export const turnsPassed = (
  results: TestResult[],
  ruleResults: TestToolRuleResult[],
): { passed: number; total: number } => {
  const rulesByCase = turnRulesByCase(ruleResults);
  const passed = results.filter(
    (result) => caseStatusFor(result, rulesByCase.get(result.case_id) ?? []) === "passed",
  ).length;
  return { passed, total: results.length };
};

export const isRunInProgress = (run: Pick<TestRun, "status"> | null | undefined): boolean =>
  run?.status === "queued" || run?.status === "running";

const RUN_STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const runStatusLabel = (status: string): string => RUN_STATUS_LABELS[status] ?? status;

// Older runs stored the raw exception after this prefix, which can name internal systems.
const UNEXPECTED_FAILURE_PREFIX = "Run failed unexpectedly";
const UNEXPECTED_FAILURE_TEXT = "Run failed unexpectedly. Details are in the server logs.";

const FAILURE_TEXTS: Record<string, string> = {
  "No test cases in suite": "The dataset has no conversations.",
};

// Why a failed run failed, from the error the backend stores in its summary.
export const runFailureReason = (run: TestRun | null | undefined): string | null => {
  if (run?.status !== "failed") return null;
  const error = (run.summary_metrics as Record<string, unknown> | undefined)?.error;
  if (typeof error !== "string" || !error.trim()) return null;
  const text = error.trim();
  if (text.startsWith(UNEXPECTED_FAILURE_PREFIX)) return UNEXPECTED_FAILURE_TEXT;
  return FAILURE_TEXTS[text] ?? text;
};

// The failure line under a run; a reason that already opens with "Run" reads on its own.
export const runFailureText = (run: TestRun): string => {
  const reason = runFailureReason(run);
  if (!reason) return "Run failed.";
  return /^run\b/i.test(reason) ? reason : `Run failed: ${reason}`;
};
