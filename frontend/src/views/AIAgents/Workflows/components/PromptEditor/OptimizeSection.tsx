import React, { useState } from "react";
import { Loader2, Play, Sparkles } from "lucide-react";
import { Button } from "@/components/button";
import { CollapsibleSection } from "@/components/CollapsibleSection";
import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import type { PromptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import { SUGGESTION_STALE_REASON } from "../../utils/promptEditorGates";
import type { Round, RoundCounts } from "../../utils/promptEditorRounds";
import { GateTooltip } from "./GateTooltip";
import { PromptEvalResults } from "./PromptEvalResults";
import { ProviderSelect } from "./ProviderSelect";
import { SuggestionDiffEditor } from "./SuggestionDiffEditor";
import type { PromptMeasurementState } from "./usePromptMeasurement";

const countsLine = (counts: RoundCounts): string =>
  `${counts.improved} improved · ${counts.regressed} regressed · ${counts.unchanged} unchanged`;

/** A round that ran but had no baseline for comparison is scored, not unevaluated
 *  Partial counts from incomplete comparison stay hidden */
const roundStatus = (round: Round): string => {
  if (round.run === null) return "Not evaluated";
  if (round.incomplete || !round.counts) return "Scored, not compared";
  return countsLine(round.counts);
};

const RESTORE_BLOCKED_REASON = "Wait for the running rewrite to finish.";

const RoundRow: React.FC<{
  round: Round;
  contextKey: string;
  blocked: boolean;
  onRestore: (id: number) => void;
}> = ({ round, contextKey, blocked, onRestore }) => (
  <div className="flex items-start justify-between gap-3 border-b last:border-b-0 pb-2 last:pb-0">
    <div className="min-w-0 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs">{roundStatus(round)}</span>
        {round.contextKey !== contextKey && (
          <span className="text-xs text-muted-foreground">
            different settings
          </span>
        )}
      </div>
      {round.source.result.explanation && (
        <p className="text-xs text-muted-foreground line-clamp-1">
          {round.source.result.explanation}
        </p>
      )}
    </div>
    <GateTooltip reason={blocked ? RESTORE_BLOCKED_REASON : null}>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onRestore(round.id)}
        disabled={blocked}
      >
        Restore
      </Button>
    </GateTooltip>
  </div>
);

interface OptimizeSectionProps {
  caps: PromptEditorCapabilities;
  measurement: PromptMeasurementState;
}

/** Rewrites the draft, then scores the rewrite. The three evaluations reachable from
 *  here run on the evaluation model, so that selector is repeated beside them */
export const OptimizeSection: React.FC<OptimizeSectionProps> = ({
  caps,
  measurement,
}) => {
  const {
    providers,
    activeEvalProviderId,
    setEvalProviderId,
    activeOptimizeProviderId,
    setOptimizeProviderId,
    providerStatus,
    optimizeInstructions,
    setOptimizeInstructions,
    evalStale,
    failedIncluded,
    failedTotal,
    baseScored,
    draftDiverged,
    comparison,
    baseline,
    rounds,
    contextKey,
    restoreRound,
    restoreBlocked,
    optimizeResult,
    optimizeStale,
    suggestion,
    optimizedFrom,
    suggestionEdited,
    editSuggestion,
    placeholderNote,
    suggestedEvalRun,
    suggestedStale,
    pairedRun,
    pairedStale,
    holdoutLook,
    holdoutError,
    optimize,
    evaluateSuggested,
    validateHoldout,
    accept,
    retryHoldout,
    dismiss,
  } = measurement;
  const [roundsOpen, setRoundsOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3">
        <ProviderSelect
          label="Optimization model"
          providers={providers}
          value={activeOptimizeProviderId}
          onChange={setOptimizeProviderId}
          isEmpty={providerStatus === "empty"}
        />

        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            Add optional guidance, then generate an improved prompt suggestion.
          </p>
          {!baseScored && (
            <p className="text-xs text-muted-foreground">
              No failures will be sent. Evaluating first produces a targeted
              rewrite.
            </p>
          )}
          {baseScored && failedTotal > failedIncluded && (
            <p className="text-xs text-muted-foreground">
              {failedIncluded} of {failedTotal} failures included.
            </p>
          )}
          {evalStale && !baseScored && suggestion === "" && (
            <p className="text-xs text-muted-foreground">
              Inputs changed since the last run, so its failures were left out.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label className="text-sm">Additional Instructions (optional)</Label>
          <RichTextarea
            value={optimizeInstructions}
            onChange={(e) => setOptimizeInstructions(e.target.value)}
            placeholder="e.g., Make it more concise, add examples, enforce JSON output..."
            size="description"
            className="text-sm"
          />
        </div>

        <div className="flex justify-end">
          <GateTooltip reason={optimize.reason}>
            <Button
              size="sm"
              onClick={optimize.run}
              disabled={!optimize.enabled || optimize.pending}
            >
              {optimize.pending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              {optimize.pending ? "Optimizing..." : "Optimize"}
            </Button>
          </GateTooltip>
        </div>
      </div>

      {optimizeResult && (
        <div className="space-y-3 border-t pt-4">
          {optimizeStale && (
            <div className="text-amber-700 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2">
              {SUGGESTION_STALE_REASON}
            </div>
          )}

          <SuggestionDiffEditor
            before={optimizedFrom}
            suggestion={suggestion}
            edited={suggestionEdited}
            onChange={editSuggestion}
          />

          {optimizeResult.explanation && (
            <div className="space-y-1">
              <Label className="text-sm font-medium">Explanation</Label>
              <p className="text-sm text-muted-foreground">
                {optimizeResult.explanation}
              </p>
            </div>
          )}

          {placeholderNote && (
            <div className="text-amber-700 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2">
              {placeholderNote} Check it before accepting.
            </div>
          )}

          {comparison && (
            <div className="border rounded-md px-3 py-2 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm">
                  {countsLine(comparison.comparison)}
                </span>
                {baseline && (
                  <span className="text-xs text-muted-foreground">
                    compared with {baseline.label}
                  </span>
                )}
              </div>
              {comparison.incomplete && (
                <p className="text-xs text-muted-foreground">
                  {comparison.incomplete}
                </p>
              )}
            </div>
          )}

          {caps.canEvaluate && (
            <ProviderSelect
              label="Evaluation model"
              providers={providers}
              value={activeEvalProviderId}
              onChange={setEvalProviderId}
              isEmpty={providerStatus === "empty"}
            />
          )}

          <div className="flex flex-wrap gap-2">
            {caps.canEvaluate && (
              <GateTooltip reason={evaluateSuggested.reason}>
                <Button
                  size="sm"
                  onClick={evaluateSuggested.run}
                  disabled={
                    !evaluateSuggested.enabled || evaluateSuggested.pending
                  }
                  variant="outline"
                >
                  {evaluateSuggested.pending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  {evaluateSuggested.pending
                    ? "Evaluating..."
                    : "Evaluate Suggested"}
                </Button>
              </GateTooltip>
            )}
            {caps.canEvaluate && (
              <GateTooltip reason={validateHoldout.reason}>
                <Button
                  size="sm"
                  onClick={validateHoldout.run}
                  disabled={!validateHoldout.enabled || validateHoldout.pending}
                  variant="outline"
                >
                  {validateHoldout.pending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  {validateHoldout.pending
                    ? "Validating..."
                    : "Validate on hold-out"}
                </Button>
              </GateTooltip>
            )}
            {caps.canEditPrompt && (
              <GateTooltip reason={accept.reason}>
                <Button size="sm" onClick={accept.run} disabled={!accept.enabled}>
                  Accept
                </Button>
              </GateTooltip>
            )}
            <Button size="sm" variant="ghost" onClick={dismiss}>
              Dismiss
            </Button>
          </div>

          {draftDiverged && (
            <p className="text-xs text-muted-foreground">
              The draft changed since this chain began. Accepting will replace
              it.
            </p>
          )}

          {holdoutError && (
            <div className="flex items-center justify-between gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
              <span>
                The {holdoutError.half === "baseline" ? "current" : "suggested"}{" "}
                prompt was not evaluated: {holdoutError.message}
              </span>
              <GateTooltip reason={holdoutError.retry.reason}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={retryHoldout}
                  disabled={!holdoutError.retry.enabled}
                >
                  Retry
                </Button>
              </GateTooltip>
            </div>
          )}

          {pairedRun && (
            <div className="border-t pt-3 space-y-3">
              {holdoutLook.continuedAfter && (
                <div className="text-amber-700 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2">
                  The search continued after this hold-out was inspected. Treat
                  it as consumed; it is no longer an untouched final check.
                </div>
              )}
              <PromptEvalResults
                results={pairedRun.suggestion.results}
                title="Hold-out comparison"
                stale={pairedStale}
                providerFallback={pairedRun.suggestion.providerFallback}
                leaky={pairedRun.suggestion.leaky}
                comparison={{ baseline: pairedRun.baseline.results }}
              />
            </div>
          )}

          {!pairedRun && suggestedEvalRun && (
            <div className="border-t pt-3">
              <PromptEvalResults
                results={suggestedEvalRun.results}
                title="Suggested Prompt Evaluation"
                stale={suggestedStale}
                providerFallback={suggestedEvalRun.providerFallback}
                leaky={suggestedEvalRun.leaky}
                comparison={
                  baseline ? { baseline: baseline.run.results } : undefined
                }
              />
            </div>
          )}

          {rounds.length > 0 && (
            <CollapsibleSection
              title={`Rounds (${rounds.length})`}
              open={roundsOpen}
              onOpenChange={() => setRoundsOpen((open) => !open)}
            >
              <div className="space-y-2">
                {rounds.map((round) => (
                  <RoundRow
                    key={round.id}
                    round={round}
                    contextKey={contextKey}
                    blocked={restoreBlocked}
                    onRestore={restoreRound}
                  />
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  );
};
