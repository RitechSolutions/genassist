import { diffLines } from "diff";
import type {
  PreviousAttemptPayload,
  PromptOptimizeResponse,
} from "@/interfaces/promptEditor.interface";
import {
  clipCodePoints,
  feedbackOf,
  type EvalRunState,
  type OptimizeRequest,
  type SuggestedRunState,
} from "./promptEditorRuns";
import { VERDICT_RANK, type PairedComparison } from "./promptEditorResults";

export const MAX_ROUNDS = 5;
export const MAX_OPTIMIZER_HISTORY = 3;
export const MAX_ROUND_DIFF_CHARS = 1_500;
export const MAX_ROUND_TEXT_CHARS = 1_000;
export const MAX_ROUND_REGRESSION_FEEDBACK_CHARS = 300;
export const MAX_ROUND_REGRESSIONS = 5;

const DIFF_MARKER = " […]";

export interface RoundCounts {
  improved: number;
  regressed: number;
  unchanged: number;
  compared: number;
}

/** One superseded suggestion, kept so the chain can step back to it */
export interface Round {
  id: number;
  source: { request: OptimizeRequest; result: PromptOptimizeResponse };
  suggestion: string;
  run: SuggestedRunState | null;
  incomplete: string | null;
  counts: RoundCounts | null;
  regressions: Array<{ caseId: string; feedback: string | null }>;
  contextKey: string;
}

/** Deterministic and capped: changed lines only, +/- prefixed, in document order*/
export const promptDiffSummary = (
  before: string,
  after: string,
  max = MAX_ROUND_DIFF_CHARS,
): string => {
  const lines = diffLines(before, after)
    .filter((part) => part.added || part.removed)
    .flatMap((part) =>
      part.value
        .replace(/\n$/, "")
        .split("\n")
        .map((line) => `${part.added ? "+" : "-"} ${line}`),
    );
  const text = lines.join("\n");
  return Array.from(text).length <= max
    ? text
    : clipCodePoints(text, max - DIFF_MARKER.length) + DIFF_MARKER;
};

export const countsOf = (comparison: PairedComparison): RoundCounts => ({
  improved: comparison.improved,
  regressed: comparison.regressed,
  unchanged: comparison.unchanged,
  compared: comparison.compared,
});

/** Cases that ranked lower under this round than under the one it was compared with */
export const regressionsOf = (
  comparison: PairedComparison,
): Array<{ caseId: string; feedback: string | null }> =>
  comparison.rows
    .flatMap((row) =>
      row.baseline &&
      row.suggestion &&
      VERDICT_RANK[row.suggestion.verdict ?? ""] <
        VERDICT_RANK[row.baseline.verdict ?? ""]
        ? [
            {
              caseId: row.caseId,
              feedback: feedbackOf(
                row.suggestion.metrics,
                MAX_ROUND_REGRESSION_FEEDBACK_CHARS,
              ),
            },
          ]
        : [],
    )
    .slice(0, MAX_ROUND_REGRESSIONS);

/** A round the optimizer can be told about: scored, compared, under current settings */
type ScoredRound = Round & { counts: RoundCounts };

const describable =
  (contextKey: string) =>
  (round: Round): round is ScoredRound =>
    round.run !== null &&
    round.counts !== null &&
    round.incomplete === null &&
    round.contextKey === contextKey;

export const optimizerHistoryOf = (
  rounds: readonly Round[],
  contextKey: string,
): PreviousAttemptPayload[] =>
  rounds
    .filter(describable(contextKey))
    .slice(0, MAX_OPTIMIZER_HISTORY)
    .map((round) => ({
      improved: round.counts.improved,
      regressed: round.counts.regressed,
      unchanged: round.counts.unchanged,
      explanation: clipCodePoints(
        round.source.result.explanation,
        MAX_ROUND_TEXT_CHARS,
      ),
      diff_summary: promptDiffSummary(
        round.source.request.prompt,
        round.suggestion,
      ),
      regressions: round.regressions.map((ref) => ({
        case_id: ref.caseId,
        feedback: ref.feedback,
      })),
    }))
    .sort((x, y) => x.improved - x.regressed - (y.improved - y.regressed));

export interface Baseline {
  run: EvalRunState;
  label: string;
}

/** Baseline for new score comparison: recent round scored under current settings, or draft's run
 *  Null means nothing to compare against yet, not a different baseline */
export const baselineOf = (
  rounds: readonly Round[],
  contextKey: string,
  evalRun: EvalRunState | null,
  evalStale: boolean,
): Baseline | null => {
  const index = rounds.findIndex(
    (round) => round.run !== null && round.contextKey === contextKey,
  );
  const scored = index === -1 ? null : rounds[index];
  if (scored?.run)
    return {
      run: scored.run,
      label: index === 0 ? "the previous round" : "an earlier round",
    };
  if (evalRun && !evalStale) return { run: evalRun, label: "the draft" };
  return null;
};
