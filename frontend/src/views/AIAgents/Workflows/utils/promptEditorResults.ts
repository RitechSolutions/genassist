import { formatUsd } from "@/helpers/formatCurrency";
import type {
  PromptEvalCaseResult,
  PromptEvalMetric,
  PromptEvalResponse,
  PromptEvalSummary,
  PromptRunProvenance,
} from "@/interfaces/promptEditor.interface";
import { methodLabel } from "@/views/TestSuites/helpers/methodLabels";
import { notScoredLabel } from "@/views/TestSuites/helpers/runResults";
import { formatDuration } from "./executionView";

/** Shown under every run: the check is not what the node runs */
export const ISOLATION_NOTE =
  "Isolated check: the prompt was sent unrendered ({{variables}} not substituted), " +
  "without this node's memory, tools, user prompt or fallback chain. " +
  "It does not reproduce what the node runs.";

/** Shown under a run scored on the cases the optimizer was given */
export const LEAKAGE_NOTE =
  "Development cases are sent to the optimizer word for word, so their scores do not " +
  "show whether the suggestion generalises. The hold-out comparison is the one to read.";

export const STALE_NOTE = "Inputs changed since this run. Re-run to compare.";
export const METERING_NOTE = "spend not recorded";

/** Counts that are zero are dropped; "passed" always renders so a run always has a
 *  headline. An execution or scoring error is never reported as a failure */
export const summaryLine = (summary: PromptEvalSummary): string => {
  const segments = [`${summary.passed} passed`];
  const add = (count: number, singular: string, plural = `${singular}s`) => {
    if (count > 0) segments.push(`${count} ${count === 1 ? singular : plural}`);
  };
  add(summary.failed, "failed", "failed");
  add(summary.inconclusive, "inconclusive", "inconclusive");
  add(summary.execution_failed, "execution error");
  add(summary.scoring_failed, "scoring error");
  add(summary.skipped, "skipped", "skipped");
  return segments.join(" · ");
};

export interface ProviderFallback {
  name: string;
  llm_model_provider: string;
  llm_model: string;
}

const modelLabel = (
  provenance: PromptRunProvenance,
  fallback?: ProviderFallback,
): string => {
  const key = provenance.provider_key || fallback?.llm_model_provider || "";
  const model = provenance.model || fallback?.llm_model || "";
  if (key && model) return `${key} (${model})`;
  return key || model || fallback?.name || "Unknown provider";
};

const ranAt = (isoTimestamp: string): string => {
  const at = new Date(isoTimestamp);
  return Number.isNaN(at.getTime())
    ? "unknown time"
    : at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export const formatTokens = (count: number): string => count.toLocaleString();

export const formatSpend = (cost: number): string =>
  cost > 0 && cost < 0.0001 ? "<$0.0001" : formatUsd(cost);

const numberOrNull = (value: number | null | undefined): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const calls = (count: number): string =>
  `${count} call${count === 1 ? "" : "s"}`;

const JUDGE_LABEL = methodLabel("llm_judge");

const spendSegments = (provenance: PromptRunProvenance): string[] => {
  const usage = provenance.usage_total ?? {};
  const tokens = usage.total_tokens ?? 0;
  const unreported = usage.responses_without_usage ?? 0;
  const unpriced = provenance.unpriced_calls ?? 0;
  const cost = numberOrNull(provenance.cost_usd);
  const segments = [`took ${formatDuration(provenance.latency_ms_total)}`];

  if (tokens > 0) {
    const gap = unreported > 0 ? `, ${calls(unreported)} unreported` : "";
    segments.push(`${formatTokens(tokens)} tokens${gap}`);
  } else if (unreported > 0) {
    segments.push("tokens unreported");
  }

  if (cost !== null) {
    const gap = unpriced > 0 ? ` (${calls(unpriced)} unpriced)` : "";
    segments.push(`${formatSpend(cost)}${gap}`);
  } else if (unpriced > 0) {
    segments.push("unpriced");
  }

  const graderTokens = provenance.grader_tokens ?? 0;
  const graderCost = numberOrNull(provenance.grader_cost_usd);
  const grader = [
    ...(graderTokens > 0 ? [`${formatTokens(graderTokens)} tokens`] : []),
    ...(graderCost !== null ? [formatSpend(graderCost)] : []),
  ];
  if ((provenance.grader_calls ?? 0) > 0 && grader.length > 0) {
    segments.push(`${JUDGE_LABEL} ${grader.join(" · ")}`);
  }
  return segments;
};

/**
 * One line stating what the run did. Names the provider and model used
 * rather than the locally selected row: another user's edit to the provider
 * is undetectable here
 */
export const snapshotHeader = (
  provenance: PromptRunProvenance,
  providerFallback?: ProviderFallback,
): string => {
  const parts = [
    `${provenance.evaluated_case_ids.length} of ${provenance.total_cases} cases`,
    `ran ${ranAt(provenance.ran_at)}`,
    modelLabel(provenance, providerFallback),
    provenance.trials === 1 ? "single sample" : `${provenance.trials} samples`,
    ...spendSegments(provenance),
  ];
  if (provenance.deadline_hit) parts.push("cut by the time budget");
  if (provenance.metering_handoff_failed) parts.push(METERING_NOTE);
  return parts.join(" · ");
};

export const rewriteHeader = (
  provenance: PromptRunProvenance,
  providerFallback?: ProviderFallback,
): string => {
  const parts = [
    "Rewrite",
    `${provenance.evaluated_case_ids.length} of ${provenance.total_cases} cases shown`,
    `ran ${ranAt(provenance.ran_at)}`,
    modelLabel(provenance, providerFallback),
    ...spendSegments(provenance),
  ];
  if (provenance.metering_handoff_failed) parts.push(METERING_NOTE);
  return parts.join(" · ");
};

/** What the case's own model call took, used and cost */
export const caseSpendLine = (result: PromptEvalCaseResult): string | null => {
  const latency = numberOrNull(result.latency_ms);
  const cost = numberOrNull(result.cost_usd);
  const parts: string[] = [];
  if (latency !== null) parts.push(formatDuration(latency));
  if (result.usage) parts.push(`${formatTokens(result.usage.total_tokens)} tokens`);
  if (cost !== null) parts.push(formatSpend(cost));
  return parts.length > 0 ? parts.join(" · ") : null;
};

export const formatAvgScore = (avg: number | null): string => {
  if (avg === null) return "—";
  const percent = (avg * 100).toFixed(1);
  return `${percent.endsWith(".0") ? percent.slice(0, -2) : percent}%`;
};

/** A case that never ran has no verdict, so it never shows as a failure */
export const caseStatusLabel = (result: PromptEvalCaseResult): string => {
  if (result.status !== "scored") return notScoredLabel(result);
  if (result.verdict === "passed") return "Passed";
  if (result.verdict === "failed") return "Failed";
  return "Inconclusive";
};

export type MetricOutcome =
  | "passed"
  | "failed"
  | "error"
  | "not_evaluated"
  | "not_applicable";

/** `not_applicable` = data gap (checked first). `not_evaluated` = check ran but didn't finish */
export const metricOutcomeOf = (metric: PromptEvalMetric): MetricOutcome => {
  if (metric.not_applicable) return "not_applicable";
  if (metric.error) return "error";
  if (metric.not_evaluated) return "not_evaluated";
  return metric.passed ? "passed" : "failed";
};

const METRIC_OUTCOME_LABELS: Record<MetricOutcome, string> = {
  passed: "Passed",
  failed: "Failed",
  error: "Could not run",
  not_evaluated: "Not evaluated",
  not_applicable: "N/A — no expected output",
};

export const metricOutcomeLabel = (metric: PromptEvalMetric): string =>
  METRIC_OUTCOME_LABELS[metricOutcomeOf(metric)];

export const metricScoreLabel = (metric: PromptEvalMetric): string | null =>
  typeof metric.score === "number" ? formatAvgScore(metric.score) : null;

export const soleMetricEchoesVerdict = (
  result: PromptEvalCaseResult,
): boolean => {
  const metrics = Object.values(result.metrics ?? {});
  return metrics.length === 1 && metricOutcomeOf(metrics[0]) === result.verdict;
};

export interface PairedCaseRow {
  caseId: string;
  baseline: PromptEvalCaseResult | null;
  suggestion: PromptEvalCaseResult | null;
}

export interface PairedComparison {
  rows: PairedCaseRow[];
  compared: number;
  improved: number;
  regressed: number;
  unchanged: number;
}

export const VERDICT_RANK: Record<string, number> = {
  failed: 0,
  inconclusive: 1,
  passed: 2,
};

/** Joins two runs of the same cases. A case missing from either side is shown but
 *  never counted: there is nothing to compare it against */
export const joinPairedRuns = (
  baseline: PromptEvalResponse,
  suggestion: PromptEvalResponse,
): PairedComparison => {
  const byId = (response: PromptEvalResponse) =>
    new Map(response.results.map((result) => [result.case_id, result]));
  const baselineById = byId(baseline);
  const suggestionById = byId(suggestion);

  const caseIds = [
    ...baseline.results.map((result) => result.case_id),
    ...suggestion.results
      .map((result) => result.case_id)
      .filter((id) => !baselineById.has(id)),
  ];

  const comparison: PairedComparison = {
    rows: [],
    compared: 0,
    improved: 0,
    regressed: 0,
    unchanged: 0,
  };

  for (const caseId of caseIds) {
    const before = baselineById.get(caseId) ?? null;
    const after = suggestionById.get(caseId) ?? null;
    comparison.rows.push({ caseId, baseline: before, suggestion: after });

    const beforeRank = VERDICT_RANK[before?.verdict ?? ""];
    const afterRank = VERDICT_RANK[after?.verdict ?? ""];
    if (beforeRank === undefined || afterRank === undefined) continue;

    comparison.compared += 1;
    if (afterRank > beforeRank) comparison.improved += 1;
    else if (afterRank < beforeRank) comparison.regressed += 1;
    else comparison.unchanged += 1;
  }

  return comparison;
};

interface SpendPair {
  before: PromptEvalCaseResult;
  after: PromptEvalCaseResult;
}

/** One before/after figure over the pairs that carry it, disclosing its own coverage
 *  when some pair does not. Null when no pair carries the metric at all */
const pairedFigure = (
  pairs: readonly SpendPair[],
  read: (result: PromptEvalCaseResult) => number | null,
  render: (before: number, after: number, covered: number) => string,
): string | null => {
  const covered = pairs
    .map((pair) => ({ before: read(pair.before), after: read(pair.after) }))
    .filter(
      (pair): pair is { before: number; after: number } =>
        pair.before !== null && pair.after !== null,
    );
  if (covered.length === 0) return null;

  const total = (side: "before" | "after") =>
    covered.reduce((running, pair) => running + pair[side], 0);
  const figure = render(total("before"), total("after"), covered.length);
  return covered.length === pairs.length
    ? figure
    : `${figure} (${covered.length} of ${pairs.length} cases)`;
};

/** Model-call spend across a paired hold-out run */
export const spendComparisonLine = (joined: PairedComparison): string | null => {
  const pairs: SpendPair[] = [];
  for (const row of joined.rows) {
    if (row.baseline?.status === "scored" && row.suggestion?.status === "scored") {
      pairs.push({ before: row.baseline, after: row.suggestion });
    }
  }
  if (pairs.length === 0) return null;

  const figures = [
    pairedFigure(
      pairs,
      (result) => numberOrNull(result.latency_ms),
      (before, after, covered) =>
        `avg ${formatDuration(before / covered)} → ${formatDuration(after / covered)}`,
    ),
    pairedFigure(
      pairs,
      (result) => result.usage?.total_tokens ?? null,
      (before, after) => `${formatTokens(before)} → ${formatTokens(after)} tokens`,
    ),
    pairedFigure(
      pairs,
      (result) => numberOrNull(result.cost_usd),
      (before, after) => `${formatSpend(before)} → ${formatSpend(after)}`,
    ),
  ].filter((figure): figure is string => figure !== null);

  if (figures.length === 0) return null;
  const scope = `${pairs.length} compared case${pairs.length === 1 ? "" : "s"}`;
  return `Model calls over ${scope}: ${figures.join(" · ")}`;
};

export interface ChallengerComparison {
  comparison: PairedComparison;
  /** Why the runs cannot be compared; null when the comparison is complete */
  incomplete: string | null;
}

const sameIdSet = (a: readonly string[], b: readonly string[]): boolean => {
  const setA = new Set(a);
  const setB = new Set(b);
  return (
    setA.size === a.length &&
    setB.size === b.length &&
    setA.size === setB.size &&
    b.every((id) => setA.has(id))
  );
};

const incompleteReason = (
  baseline: PromptEvalResponse,
  challenger: PromptEvalResponse,
  comparison: PairedComparison,
): string | null => {
  if (
    !sameIdSet(
      baseline.provenance.evaluated_case_ids,
      challenger.provenance.evaluated_case_ids,
    )
  )
    return "The two runs evaluated different cases.";
  const unfinished = comparison.rows.filter(
    (row) =>
      !row.baseline ||
      !row.suggestion ||
      row.baseline.status !== "scored" ||
      row.suggestion.status !== "scored" ||
      row.baseline.verdict === null ||
      row.suggestion.verdict === null,
  ).length;
  if (unfinished > 0)
    return `${unfinished} case${unfinished === 1 ? "" : "s"} did not finish on one side.`;
  if (comparison.compared !== baseline.provenance.evaluated_case_ids.length)
    return "Not every case could be compared.";
  return null;
};

/** Counts the moves between two runs and states whether the pair is comparable at all */
export const compareRuns = (
  baseline: PromptEvalResponse,
  challenger: PromptEvalResponse,
): ChallengerComparison => {
  const comparison = joinPairedRuns(baseline, challenger);
  return {
    comparison,
    incomplete: incompleteReason(baseline, challenger, comparison),
  };
};
