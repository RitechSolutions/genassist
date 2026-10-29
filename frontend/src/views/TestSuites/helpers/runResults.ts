import { TestResult, TestRun } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";

// A turn-scoped result belongs to one case, so it is shown with that case; a
// conversation-scoped one has no single case to sit on.
export const isTurnScope = (scope: string): boolean =>
  scope === "every_turn" || scope === "specific_turn" || scope === "turn";

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

/** A run opens once it has ended; a failed one only when some turns finished before it stopped. */
export const runOpens = (run: Pick<TestRun, "status" | "progress">): boolean => {
  if (run.status === "queued" || run.status === "running") return false;
  return run.status !== "failed" || (run.progress?.turns_done ?? 0) > 0;
};

// "3 of 9 conversations done" while a run is in progress, counted as its results are; null before it reports any.
export const runProgressText = (run: Pick<TestRun, "progress"> | null | undefined): string | null => {
  const progress = run?.progress;
  if (!progress || !progress.conversations_total) return null;
  const total = progress.conversations_total;
  return `${progress.conversations_done} of ${total} conversation${total === 1 ? "" : "s"} done`;
};

/** A run still going, in words: "Queued", or "Running…" with how far it got. */
export const runInProgressText = (run: Pick<TestRun, "status" | "progress"> | null | undefined): string => {
  if (run?.status === "queued") return "Queued";
  // A finished run's count would read as this run's, as it does just after Run.
  const progress = run?.status === "running" ? runProgressText(run) : null;
  return progress ? `Running… ${progress}` : "Running…";
};

/** Said beside Run all: starting its runs, running them, or runs started elsewhere. */
export const runAllStatusText = (
  starting: boolean,
  progress: { done: number; total: number } | null,
  anyRunning: boolean,
): string | null => {
  if (starting && progress) return `Running… ${progress.done} of ${progress.total} done`;
  if (starting) return "Starting…";
  return anyRunning ? "Running…" : null;
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

/** Why none of a run's checks could be graded, or null. */
export const checksGradingError = (run: TestRun | null | undefined): string | null => {
  const checks = (run?.summary_metrics as Record<string, unknown> | undefined)?.checks as { error?: unknown } | undefined;
  return typeof checks?.error === "string" && checks.error
    ? "The checks could not be graded in this run, so its conversations were not evaluated. Run it again."
    : null;
};

/** True when a run also graded turns with an older method, beside its checks. */
export const runGradesTurns = (run: Pick<TestRun, "techniques"> | null | undefined): boolean =>
  (run?.techniques ?? []).some((technique) => technique !== "checks");

/** "3 of 4 conversations passed · 1 failed" for a run with checks, or null. Read where the switch is off. */
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

/** "Run 3" once numbered in its evaluation, else "Run #a1b2". */
export const runName = (run: Pick<TestRun, "id" | "number">): string =>
  run.number ? `Run ${run.number}` : `Run #${(run.id ?? "").slice(-4)}`;

/** The runs numbered in their evaluation: its run ids are kept newest first and never removed. */
export const numberRuns = (runs: TestRun[], runIds: string[]): TestRun[] => {
  const numbers = new Map(runIds.map((id, index) => [id, runIds.length - index]));
  return runs.map((run) => (run.id && numbers.has(run.id) ? { ...run, number: numbers.get(run.id) } : run));
};

export const runDate = (run: Pick<TestRun, "created_at">): string => new Date(run.created_at ?? "").toLocaleString();

/** How long a finished run took, from when it was queued to its last update. */
export const runDuration = (run: Pick<TestRun, "status" | "created_at" | "updated_at">): string | null => {
  if (isRunInProgress(run) || !run.created_at || !run.updated_at) return null;
  const seconds = Math.round((new Date(run.updated_at).getTime() - new Date(run.created_at).getTime()) / 1000);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
};

/** "Run 3 · workflow v4.1 · 9 Oct, 14:02", for choosing a run; the version is the workflow's. */
export const runOptionLabel = (run: TestRun): string =>
  [runName(run), run.workflow_version ? `workflow v${run.workflow_version}` : null, runDate(run)]
    .filter(Boolean)
    .join(" · ");
