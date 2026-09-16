import React from 'react';
import { AlertCircle, CheckCircle2, Loader2, Play, Sparkles } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/accordion';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { RichTextarea } from '@/components/richTextarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Switch } from '@/components/switch';
import { methodLabel } from '@/views/TestSuites/helpers/methodLabels';
import type { PromptEvalResponse } from '@/interfaces/promptEditor.interface';
import type { PromptEditorCapabilities } from '../../utils/promptEditorCapabilities';
import { promptLength, SUGGESTION_STALE_REASON } from '../../utils/promptEditorGates';
import { summaryLine } from '../../utils/promptEditorResults';
import {
  CASES_TO_CHECK_OPTIONS,
  PROMPT_CHECK_TECHNIQUES,
} from '../../utils/promptEditorTechniques';
import { GateTooltip } from './GateTooltip';
import { PromptDiagnostics } from './PromptDiagnostics';
import { ProviderSelect } from './ProviderSelect';
import { PromptEvalResults } from './PromptEvalResults';
import { SuggestionDiffEditor } from './SuggestionDiffEditor';
import type { PromptMeasurementState } from './usePromptMeasurement';

interface EditorTabProps {
  nodeId: string;
  value: string;
  /** Clear preview undo snapshot on typing */
  onDraftEdit: (newValue: string) => void;
  fieldLabel: string;
  caps: PromptEditorCapabilities;
  measurement: PromptMeasurementState;
}

const runMarkers = (results: PromptEvalResponse, stale: boolean) =>
  `${results.provenance.deadline_hit ? ' · cut by the time budget' : ''}${
    stale ? ' · inputs changed' : ''
  }`;

export const EditorTab: React.FC<EditorTabProps> = ({
  nodeId,
  value,
  onDraftEdit,
  fieldLabel,
  caps,
  measurement,
}) => {
  const {
    error,
    successMessage,
    providers,
    activeEvalProviderId,
    setEvalProviderId,
    activeOptimizeProviderId,
    setOptimizeProviderId,
    providerStatus,
    selectedTechniques,
    toggleTechnique,
    notContainsSelected,
    phrasesText,
    setPhrasesText,
    phrasesIssue,
    casesToCheck,
    setCasesToCheck,
    split,
    splitActive,
    setSplitEnabled,
    optimizeInstructions,
    setOptimizeInstructions,
    evalRun,
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
    hasRuns,
    evaluate,
    optimize,
    evaluateSuggested,
    accept,
    retryHoldout,
    dismiss,
  } = measurement;

  return (
    <div className="space-y-4 pt-4 px-2">
      {(error || successMessage) && (
        <div className="space-y-2">
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {successMessage && (
            <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm bg-green-50 dark:bg-green-500/15 border border-green-200 dark:border-green-500/30 rounded-md px-3 py-2">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <Label>{fieldLabel}</Label>
        <RichTextarea
          value={value}
          onChange={(e) => onDraftEdit(e.target.value)}
          placeholder="Enter your prompt..."
          rows={10}
          className="w-full font-mono text-sm"
        />
        <div className="text-xs text-muted-foreground text-right">{promptLength(value)} characters</div>

        <PromptDiagnostics nodeId={nodeId} value={value} />
      </div>

      <Accordion type="multiple" className="border rounded-lg px-4">
        {caps.canOptimize && (
          <AccordionItem value="optimize">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center justify-between w-full pr-2">
                <span>Optimize Prompt</span>
                {optimizeResult && (
                  <span className="text-xs text-muted-foreground">
                    Suggestion ready{optimizeStale ? ' · inputs changed' : ''}
                  </span>
                )}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 flex flex-col gap-2">
                <div className="flex items-start justify-between gap-4">
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
                </div>

                <div className="px-2">
                  <ProviderSelect
                    label="Optimization model"
                    providers={providers}
                    value={activeOptimizeProviderId}
                    onChange={setOptimizeProviderId}
                    isEmpty={providerStatus === 'empty'}
                  />
                </div>

                <div className="space-y-2 px-2">
                  <Label className="text-sm">Additional Instructions (optional)</Label>
                  <RichTextarea
                    value={optimizeInstructions}
                    onChange={(e) => setOptimizeInstructions(e.target.value)}
                    placeholder="e.g., Make it more concise, add examples, enforce JSON output..."
                    size="description"
                    className="text-sm"
                  />
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
                        <p className="text-sm text-muted-foreground">{optimizeResult.explanation}</p>
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
                        isEmpty={providerStatus === 'empty'}
                      />
                    )}

                    <div className="flex flex-wrap gap-2">
                      {caps.canEvaluate && (
                        <GateTooltip reason={evaluateSuggested.reason}>
                        <Button
                          size="sm"
                          onClick={evaluateSuggested.run}
                          disabled={!evaluateSuggested.enabled || evaluateSuggested.pending}
                          variant="outline"
                        >
                          {evaluateSuggested.pending ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4 mr-2" />
                          )}
                          {evaluateSuggested.pending ? 'Evaluating...' : 'Evaluate Suggested'}
                        </Button>
                        </GateTooltip>
                      )}
                      {caps.canEditPrompt && (
                        <GateTooltip reason={accept.reason}>
                        <Button
                          size="sm"
                          onClick={accept.run}
                          disabled={!accept.enabled}
                        >
                          {accept.pending ? 'Accepting...' : 'Accept & Save as Version'}
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
                          The {holdoutError.half === 'baseline' ? 'current' : 'suggested'} prompt
                          was not evaluated: {holdoutError.message}
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
                      {optimize.pending ? 'Optimizing...' : 'Optimize'}
                    </Button>
                  </GateTooltip>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {caps.canEvaluate && (
          <AccordionItem value="evaluate">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center justify-between w-full pr-2">
                <span>Evaluate Prompt</span>
                {evalRun && (
                  <span className="text-xs text-muted-foreground">
                    {summaryLine(evalRun.results.summary)}
                    {runMarkers(evalRun.results, evalStale)}
                  </span>
                )}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4">
                <div className="flex flex-col gap-2">
                  <ProviderSelect
                    label="Evaluation model"
                    providers={providers}
                    value={activeEvalProviderId}
                    onChange={setEvalProviderId}
                    isEmpty={providerStatus === 'empty'}
                  />

                  <div className="flex flex-wrap gap-4">
                    {PROMPT_CHECK_TECHNIQUES.map((technique) => (
                      <div key={technique} className="flex items-center gap-2">
                        <Switch
                          checked={selectedTechniques.includes(technique)}
                          onCheckedChange={() => toggleTechnique(technique)}
                        />
                        <Label className="text-sm cursor-pointer">{methodLabel(technique)}</Label>
                      </div>
                    ))}
                  </div>

                  {notContainsSelected && (
                    <div className="space-y-2 px-2">
                      <Label className="text-sm">Forbidden phrases (one per line)</Label>
                      <RichTextarea
                        value={phrasesText}
                        onChange={(e) => setPhrasesText(e.target.value)}
                        placeholder={'discount\nguarantee'}
                        size="description"
                        className="text-sm"
                      />
                      {phrasesIssue && <p className="text-xs text-destructive">{phrasesIssue}</p>}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm">Cases to check</Label>
                      <Select
                        value={String(casesToCheck)}
                        onValueChange={(v) => setCasesToCheck(Number(v))}
                        disabled={splitActive}
                      >
                        <SelectTrigger className="w-20">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CASES_TO_CHECK_OPTIONS.map((option) => (
                            <SelectItem key={option} value={String(option)}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <GateTooltip reason={split.feasible ? null : split.reason}>
                      <span className="flex items-center gap-2">
                        <Switch
                          checked={splitActive}
                          disabled={!split.feasible}
                          onCheckedChange={setSplitEnabled}
                        />
                        <Label className="text-sm cursor-pointer">
                          Hold out cases
                          {split.feasible && (
                            <span className="text-muted-foreground">
                              {' '}
                              ({split.dev.length} development · {split.holdout.length} hold-out)
                            </span>
                          )}
                        </Label>
                      </span>
                    </GateTooltip>
                  </div>

                  <div className="flex justify-end">
                    <GateTooltip reason={evaluate.reason}>
                    <Button
                      size="sm"
                      variant="default"
                      onClick={evaluate.run}
                      disabled={!evaluate.enabled || evaluate.pending}
                    >
                      {evaluate.pending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4 mr-2" />
                      )}
                      {evaluate.pending ? 'Evaluating...' : 'Run Evaluation'}
                    </Button>
                    </GateTooltip>
                  </div>
                </div>

                {evalRun && (
                  <PromptEvalResults
                    results={evalRun.results}
                    stale={evalStale}
                    providerFallback={evalRun.providerFallback}
                    leaky={evalRun.leaky}
                  />
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>

      {hasRuns && (
        <p className="text-xs text-muted-foreground">
          Results are kept while this editor is open.
        </p>
      )}
    </div>
  );
};
