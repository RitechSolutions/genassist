import type {
  PromptEvalCaseResult,
  PromptEvalMetric,
  PromptEvalResponse,
  PromptTechniqueConfigs,
} from "@/interfaces/promptEditor.interface";
import {
  metricOutcomeOf,
  type ProviderFallback,
} from "@/views/AIAgents/Workflows/utils/promptEditorResults";

/** The gold-dataset fields a run depends on, so editing a case makes the run stale */
export interface CaseRow {
  id: string;
  input_data: Record<string, unknown>;
  expected_output: Record<string, unknown> | null;
  source_conversation_id: string | null;
  turn_index: number | null;
}

/** Recursively sorts keys so JSON.stringify produces consistent output regardless of build order */
export const canonicalJson = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const source = value as Record<string, unknown>;
    const entries = Object.keys(source)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(source[key])}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
};

export const clipCodePoints = (text: string, max: number): string => {
  const points = Array.from(text);
  return points.length <= max ? text : points.slice(0, max).join("");
};

/** One failure handed to the optimizer. Input and expectation are re-read server-side;
 *  the metrics that rejected it travel so the rewrite is told which rule to satisfy */
export interface FailedCase {
  caseId: string;
  actual: string;
  failedMetrics: string[];
  feedback: string | null;
}

export const MAX_OPTIMIZE_FAILED = 10;
export const MAX_FAILURE_FEEDBACK_CHARS = 500;

// Sorted: metric order follows the technique toggle order, which must not change the key
const failedMetricsOf = (metrics: Record<string, PromptEvalMetric>): string[] =>
  Object.entries(metrics ?? {})
    .filter(([, metric]) => metricOutcomeOf(metric) === "failed")
    .map(([key]) => key)
    .sort();

/** Technique-prefixed and sorted */
export const feedbackOf = (
  metrics: Record<string, PromptEvalMetric>,
): string | null => {
  const parts = Object.entries(metrics ?? {})
    .filter(([, metric]) => metricOutcomeOf(metric) === "failed" && metric.comment)
    .map(([key, metric]) => `${key}: ${metric.comment}`)
    .sort();
  return parts.length === 0
    ? null
    : clipCodePoints(parts.join("; "), MAX_FAILURE_FEEDBACK_CHARS);
};

/** Only graded failures reach optimizer; errors don't measure prompt quality. Server-side order keeps the cap stable */
export const failedCasesOf = (
  results: readonly PromptEvalCaseResult[],
): FailedCase[] =>
  results
    .filter((r) => r.verdict === "failed")
    .map((r) => ({
      caseId: r.case_id,
      actual: r.actual,
      failedMetrics: failedMetricsOf(r.metrics),
      feedback: feedbackOf(r.metrics),
    }))
    .slice(0, MAX_OPTIMIZE_FAILED);

/** How many failed before the cap, for the "10 of 14 failures included" line */
export const failedCaseCount = (
  results: readonly PromptEvalCaseResult[],
): number => results.filter((r) => r.verdict === "failed").length;

export interface EvalKeyInputs {
  prompt: string;
  providerId: string;
  providerRevision: string;
  techniques: readonly string[];
  techniqueConfigs: PromptTechniqueConfigs;
  /** The ordered list actually sent; null when the server picks the first `maxCases` */
  caseIds: readonly string[] | null;
  maxCases: number;
  /** `canonicalJson(caseRows)`, memoised by the caller. Null when the cases are
   *  not loaded or not readable, which is distinct key material from an empty set */
  caseRowsKey: string | null;
}

/** Inputs an evaluation depends on. Order-independent for techniques, so a
 *  reordered set still matches; case ids keep their order, which is the scoring order */
export const evalKeyOf = (input: EvalKeyInputs): string =>
  canonicalJson({
    prompt: input.prompt,
    providerId: input.providerId,
    providerRevision: input.providerRevision,
    techniques: [...input.techniques].sort(),
    techniqueConfigs: input.techniqueConfigs,
    caseIds: input.caseIds,
    maxCases: input.maxCases,
    caseRowsKey: input.caseRowsKey,
  });

export type MeasurementContextInputs = Omit<EvalKeyInputs, "prompt"> & {
  holdoutIds: readonly string[] | null;
};

export const measurementContextKeyOf = (
  input: MeasurementContextInputs,
): string =>
  canonicalJson({
    providerId: input.providerId,
    providerRevision: input.providerRevision,
    techniques: [...input.techniques].sort(),
    techniqueConfigs: input.techniqueConfigs,
    caseIds: input.caseIds,
    maxCases: input.maxCases,
    caseRowsKey: input.caseRowsKey,
    holdoutIds: input.holdoutIds,
  });

export const staleOf = (runKey: string, currentKey: string): boolean =>
  runKey !== currentKey;

/** Evaluate mutation variables. `key` is computed at mutate time, never recomputed
 *  in a callback, where the closure would read a stale draft */
export interface EvalRequest {
  key: string;
  prompt: string;
  providerId: string;
  techniques: string[];
  techniqueConfigs: PromptTechniqueConfigs;
  caseIds: string[] | null;
  maxCases: number;
}

/** Metadata about completed run production. Read when rendering; not in live form state */
export interface RunSnapshot {
  leaky: boolean;
  providerFallback: ProviderFallback | undefined;
}

export type EvalRunState = {
  key: string;
  results: PromptEvalResponse;
} & RunSnapshot;

/** Test cases used to score suggestion. Tracked for staleness re-keying */
export type SuggestedRunState = EvalRunState & { caseIds: string[] | null };

export interface CaseSplitRef {
  holdoutShare: number;
  holdoutIds: readonly string[];
}

export interface OptimizeKeyInputs {
  prompt: string;
  providerId: string;
  instructions: string;
  caseSplit: CaseSplitRef | null;
  caseRowsKey: string | null;
  techniques: readonly string[];
  techniqueConfigs: PromptTechniqueConfigs;
  providerRevision: string;
  sourceEvalKey: string;
}

/** The inputs a suggestion relies on. Failures are tracked separately, so early suggestions persist despite later failures */
export const optimizeKeyOf = (input: OptimizeKeyInputs): string =>
  canonicalJson({
    prompt: input.prompt,
    providerId: input.providerId,
    providerRevision: input.providerRevision,
    instructions: input.instructions,
    caseSplit: input.caseSplit,
    caseRowsKey: input.caseRowsKey,
    techniques: [...input.techniques].sort(),
    techniqueConfigs: input.techniqueConfigs,
    sourceEvalKey: input.sourceEvalKey,
  });

export interface OptimizeRequest {
  key: string;
  prompt: string;
  providerId: string;
  instructions: string;
  failedCases?: FailedCase[];
  /** Identity of the failures that were sent; null when none were */
  sourceFailuresKey: string | null;
  caseSplit: CaseSplitRef | null;
  techniques: string[];
  techniqueConfigs: PromptTechniqueConfigs;
}

/**
 * Identifies failures, not runs (same prompt/provider can fail differently).
 * Null = no failures, so optimizations without failures never expire.
 */
export const failuresKeyOf = (cases: readonly FailedCase[]): string | null =>
  cases.length === 0 ? null : canonicalJson(cases);

export const isOptimizeCurrent = (
  request: OptimizeRequest,
  currentKey: string,
): boolean => !staleOf(request.key, currentKey);

/** Identical inputs re-run produced different failures (advisory only, doesn't block) */
export const failuresDrifted = (
  request: OptimizeRequest,
  failuresKey: string | null,
): boolean => request.sourceFailuresKey !== failuresKey;

/** Version-create variables for an accepted suggestion */
export interface AcceptPayload {
  content: string;
  draftAtSubmit: string;
  token: number;
}

/** Saves the suggestion */
export const acceptPayloadOf = (
  suggestion: string,
  draft: string,
  token: number,
): AcceptPayload => ({ content: suggestion, draftAtSubmit: draft, token });
