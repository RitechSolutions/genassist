import type {
  PromptEvalCaseResult,
  PromptEvalMetric,
  PromptEvalResponse,
  PromptEvalSummary,
  PromptRunProvenance,
} from "@/interfaces/promptEditor.interface";
import { notScoredLabel } from "@/views/TestSuites/helpers/runResults";

/** Shown under every run: the check is not what the node runs */
export const ISOLATION_NOTE =
  "Isolated check: the prompt was sent unrendered ({{variables}} not substituted), " +
  "without this node's memory, tools, user prompt or fallback chain. " +
  "It does not reproduce what the node runs.";

/** Shown with the comparison panel and under a development run */
export const LEAKAGE_NOTE =
  "Development cases are sent to the optimizer word for word, so their scores do not " +
  "show whether the suggestion generalises. The hold-out comparison is the one to read.";

export const STALE_NOTE = "Inputs changed since this run. Re-run to compare.";

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
    "Snapshot",
    `${provenance.evaluated_case_ids.length} of ${provenance.total_cases} cases`,
    `ran ${ranAt(provenance.ran_at)}`,
    modelLabel(provenance, providerFallback),
    provenance.trials === 1 ? "single sample" : `${provenance.trials} samples`,
  ];
  if (provenance.deadline_hit) parts.push("cut by the time budget");
  if (provenance.metering_handoff_failed) parts.push("spend hand-off failed");
  return parts.join(" · ");
};

export const formatAvgScore = (avg: number | null): string =>
  avg === null ? "—" : `${(avg * 100).toFixed(1)}%`;

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

const VERDICT_RANK: Record<string, number> = {
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
