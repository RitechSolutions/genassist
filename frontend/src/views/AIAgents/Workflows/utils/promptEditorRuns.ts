import type {
  PromptEvalCaseResult,
  PromptTechniqueConfigs,
} from "@/interfaces/promptEditor.interface";

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

/** One failure handed to the optimizer. Input and expectation are re-read server-side */
export interface FailedCase {
  caseId: string;
  actual: string;
}

export const MAX_OPTIMIZE_FAILED = 10;

/** Only graded failures reach optimizer; errors don't measure prompt quality. Server-side order keeps the cap stable */
export const failedCasesOf = (
  results: readonly PromptEvalCaseResult[],
): FailedCase[] =>
  results
    .filter((r) => r.verdict === "failed")
    .map((r) => ({ caseId: r.case_id, actual: r.actual }))
    .slice(0, MAX_OPTIMIZE_FAILED);

/** How many failed before the cap, for the "10 of 14 failures included" line */
export const failedCaseCount = (
  results: readonly PromptEvalCaseResult[],
): number => results.filter((r) => r.verdict === "failed").length;

export interface EvalKeyInputs {
  prompt: string;
  providerId: string;
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
    techniques: [...input.techniques].sort(),
    techniqueConfigs: input.techniqueConfigs,
    caseIds: input.caseIds,
    maxCases: input.maxCases,
    caseRowsKey: input.caseRowsKey,
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
}

/** The inputs a suggestion relies on. Failures are tracked separately, so early suggestions persist despite later failures */
export const optimizeKeyOf = (input: OptimizeKeyInputs): string =>
  canonicalJson({
    prompt: input.prompt,
    providerId: input.providerId,
    instructions: input.instructions,
    caseSplit: input.caseSplit,
    caseRowsKey: input.caseRowsKey,
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
}

/**
 * Identifies failures, not runs (same prompt/provider can fail differently).
 * Null = no failures, so optimizations without failures never expire.
 */
export const failuresKeyOf = (cases: readonly FailedCase[]): string | null =>
  cases.length === 0 ? null : canonicalJson(cases);

/** Suggestion is valid while inputs match and failures are current */
export const isOptimizeCurrent = (
  request: OptimizeRequest,
  current: { key: string; failuresKey: string | null },
): boolean =>
  !staleOf(request.key, current.key) &&
  (request.sourceFailuresKey === null ||
    request.sourceFailuresKey === current.failuresKey);
