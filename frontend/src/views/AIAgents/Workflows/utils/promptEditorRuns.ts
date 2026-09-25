import type { PromptEvalCaseResult } from "@/interfaces/promptEditor.interface";

/** One failure handed to the optimizer */
export interface FailedCase {
  input: string;
  expected: string;
  actual: string;
}

export interface EvalRequest {
  prompt: string;
  providerId: string;
  techniques: string[];
}

export interface OptimizeRequest {
  prompt: string;
  providerId: string;
  instructions: string;
  failedCases?: FailedCase[];
  /** Identity of the failures that were sent; null when none were */
  sourceFailuresKey: string | null;
}

/** Inputs an evaluation depends on. Order-independent, so a reordered set still matches */
export const evalKeyOf = (
  prompt: string,
  providerId: string,
  techniques: readonly string[],
): string =>
  JSON.stringify({ prompt, providerId, techniques: [...techniques].sort() });

export const failedCasesOf = (
  results: readonly PromptEvalCaseResult[],
): FailedCase[] =>
  results
    .filter((r) => !r.passed)
    .map((r) => ({ input: r.input, expected: r.expected, actual: r.actual }));

/**
 * Identifies failures, not runs (same prompt/provider can fail differently).
 * Null = no failures, so optimizations without failures never expire.
 */
export const failuresKeyOf = (cases: readonly FailedCase[]): string | null =>
  cases.length === 0 ? null : JSON.stringify(cases);

/** Suggestion is valid while inputs match and failures are current */
export const isOptimizeCurrent = (
  request: OptimizeRequest,
  current: {
    prompt: string;
    providerId: string;
    instructions: string;
    failuresKey: string | null;
  },
): boolean =>
  request.prompt === current.prompt &&
  request.providerId === current.providerId &&
  request.instructions === current.instructions &&
  (request.sourceFailuresKey === null ||
    request.sourceFailuresKey === current.failuresKey);
