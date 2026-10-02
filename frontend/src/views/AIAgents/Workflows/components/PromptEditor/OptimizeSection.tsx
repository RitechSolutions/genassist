import React from "react";
import { Loader2, Play, Sparkles } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import type { PromptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import { SUGGESTION_STALE_REASON } from "../../utils/promptEditorGates";
import { GateTooltip } from "./GateTooltip";
import { PromptEvalResults } from "./PromptEvalResults";
import { ProviderSelect } from "./ProviderSelect";
import { SuggestionDiffEditor } from "./SuggestionDiffEditor";
import type { PromptMeasurementState } from "./usePromptMeasurement";

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
    holdoutError,
    optimize,
    evaluateSuggested,
    accept,
    retryHoldout,
    dismiss,
  } = measurement;

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
          {failedTotal > failedIncluded && (
            <p className="text-xs text-muted-foreground">
              {failedIncluded} of {failedTotal} failures included.
            </p>
          )}
          {evalStale && (
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
            {caps.canEditPrompt && (
              <GateTooltip reason={accept.reason}>
                <Button size="sm" onClick={accept.run} disabled={!accept.enabled}>
                  {accept.pending ? "Accepting..." : "Accept & Save as Version"}
                </Button>
              </GateTooltip>
            )}
            <Button size="sm" variant="ghost" onClick={dismiss}>
              Dismiss
            </Button>
          </div>

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
            <div className="border-t pt-3">
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
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
