import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type {
  RuleTechnique,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";

// Order rule sections the way the wizard lists the techniques, checks first.
const TECHNIQUE_ORDER: RuleTechnique[] = ["checks", "tool_used", "route_taken", "action_taken"];

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
  scope === "every_turn" || scope === "specific_turn" || scope === "turn";

// A check for every conversation is graded once per conversation, like a conversation rule.
export const isConversationScope = (scope: string): boolean =>
  scope === "conversation" || scope === "every_conversation";

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
  const conversationChecks = results.filter((result) => isConversationScope(result.scope)).length;

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

// Checks read by conversation; each one gives a result per conversation or turn it covers.
export const checkResultsSummary = (
  results: TestToolRuleResult[],
  verdict: string | null,
): { headline: string; subline: string } => {
  const checks = new Set(results.map((result) => result.rule_id)).size;
  const subline = `${countLabel(checks, "check")} · ${countLabel(results.length, "result")}`;
  if (verdict) return { headline: verdict, subline };
  const passed = results.filter((result) => result.status === "passed").length;
  const evaluated = passed + results.filter((result) => result.status === "failed").length;
  return { headline: evaluated ? `${passed} of ${evaluated} results passed` : NOT_EVALUATED, subline };
};

export type CaseStatus = "passed" | "failed" | "not_scored";

export const hasMetrics = (result: Pick<TestResult, "metrics">): boolean =>
  !!result.metrics && Object.keys(result.metrics).length > 0;

// Methods with nothing to compare (not evaluated) or that broke (error) neither pass nor fail.
const gradedMetrics = (result: TestResult) =>
  Object.values(result.metrics ?? {}).filter((m) => !m.not_evaluated && !m.error);

const hasErroredMetric = (result: TestResult): boolean =>
  Object.values(result.metrics ?? {}).some((m) => m.error);

// Skipped, unexecuted and unscorable turns, whatever their metrics say.
const isResultNotScoredByStatus = (result: Pick<TestResult, "status">): boolean =>
  !!result.status && result.status !== "scored";

// A scored turn every method skipped, such as one without an expected reply. Errors don't count.
const isNotEvaluatedTurn = (result: Pick<TestResult, "status" | "metrics">): boolean =>
  hasMetrics(result) &&
  !isResultNotScoredByStatus(result) &&
  Object.values(result.metrics!).every((m) => m.not_evaluated);

// No metrics means no score; a broken method leaves the turn unscored unless another failed it.
export const isResultNotScored = (result: TestResult): boolean => {
  if (!hasMetrics(result) || isResultNotScoredByStatus(result)) return true;
  const graded = gradedMetrics(result);
  const failed = graded.some((m) => !m.passed);
  return !failed && (graded.length === 0 || hasErroredMetric(result));
};

export const isResultPassed = (result: TestResult): boolean =>
  !isResultNotScored(result) && gradedMetrics(result).every((m) => m.passed);

export const isResultFailed = (result: TestResult): boolean =>
  !isResultPassed(result) && !isResultNotScored(result);

export const notScoredLabel = (result: Pick<TestResult, "status" | "metrics">): string => {
  if (result.status === "skipped") return "Skipped";
  if (result.status === "scoring_failed") return "Scoring failed";
  if (result.status === "execution_failed") return "Execution failed";
  if (isNotEvaluatedTurn(result)) return "Not evaluated";
  return "Not scored";
};

// "12 of 40 turns done" while a run is in progress; null before it reports any.
export const runProgressText = (run: Pick<TestRun, "progress"> | null | undefined): string | null => {
  const progress = run?.progress;
  if (!progress || !progress.turns_total) return null;
  const total = progress.turns_total;
  return `${progress.turns_done} of ${total} turn${total === 1 ? "" : "s"} done`;
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
  // A passed rule passes an ungraded turn, but not one that failed to run or score, or whose method broke.
  const passed =
    isResultPassed(result) ||
    (isResultNotScored(result) &&
      !isResultNotScoredByStatus(result) &&
      !hasErroredMetric(result) &&
      rulePassed);
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

export interface ChecksConversations {
  total: number;
  passed: number;
  failed: number;
  not_evaluated: number;
}

/** A run's verdict by conversation, or null without checks. */
export const checksConversations = (run: TestRun | null | undefined): ChecksConversations | null => {
  const checks = (run?.summary_metrics as Record<string, unknown> | undefined)?.checks as
    | { conversations?: ChecksConversations }
    | undefined;
  const conversations = checks?.conversations;
  return conversations && conversations.total ? conversations : null;
};

/** True when a run also graded turns with an older method, beside its checks. */
export const runGradesTurns = (run: Pick<TestRun, "techniques"> | null | undefined): boolean =>
  (run?.techniques ?? []).some((technique) => technique !== "checks");

/** "3 of 4 conversations passed · 1 failed" for a run with checks, or null. */
export const checksVerdictText = (run: TestRun | null | undefined): string | null => {
  const conversations = checksConversations(run);
  if (!conversations) return null;
  const graded = conversations.passed + conversations.failed;
  const parts = [
    graded
      ? `${conversations.passed} of ${graded} conversation${graded === 1 ? "" : "s"} passed`
      : "No conversation could be checked",
  ];
  if (conversations.failed) parts.push(`${conversations.failed} failed`);
  if (conversations.not_evaluated) parts.push(`${conversations.not_evaluated} not checked`);
  return parts.join(" · ");
};

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
// Turns nothing could grade are counted apart instead of against the pass rate.
export const turnsPassed = (
  results: TestResult[],
  ruleResults: TestToolRuleResult[],
): { passed: number; total: number; notEvaluated: number } => {
  const rulesByCase = turnRulesByCase(ruleResults);
  let passed = 0;
  let notEvaluated = 0;
  for (const result of results) {
    const status = caseStatusFor(result, rulesByCase.get(result.case_id) ?? []);
    if (status === "passed") passed += 1;
    else if (status === "not_scored" && isNotEvaluatedTurn(result)) notEvaluated += 1;
  }
  return { passed, total: results.length - notEvaluated, notEvaluated };
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
