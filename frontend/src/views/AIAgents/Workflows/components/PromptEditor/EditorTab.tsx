import React, { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2, Play, Sparkles, XCircle } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/accordion';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { RichTextarea } from '@/components/richTextarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Badge } from '@/components/badge';
import { Switch } from '@/components/switch';
import { getAllLLMProviders } from '@/services/llmProviders';
import { createPromptVersion, evaluatePrompt, optimizePrompt } from '@/services/promptEditor';
import { listTestCases } from '@/services/testSuites';
import { extractErrorMessage } from '@/helpers/apiError';
import type { LLMProvider } from '@/interfaces/llmProvider.interface';
import type { PromptEvalResponse, PromptOptimizeResponse } from '@/interfaces/promptEditor.interface';
import type { PromptEditorCapabilities } from '../../utils/promptEditorCapabilities';
import { acceptGate, evaluateGate, optimizeGate } from '../../utils/promptEditorGates';
import type { CasesState, HistoryState } from '../../utils/promptEditorGates';
import { draftUnchangedSince } from '../../utils/promptEditorHistory';
import { GateTooltip } from './GateTooltip';
import { promptHistoryKey } from './usePromptHistory';

interface EditorTabProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  value: string;
  /** Clear preview undo snapshot on typing */
  onDraftEdit: (newValue: string) => void;
  /** Accepted optimization that was saved as a version */
  onAccepted: (newValue: string) => void;
  latestDraftRef: React.MutableRefObject<string>;
  fieldLabel: string;
  historyState: HistoryState;
  caps: PromptEditorCapabilities;
  defaultProviderId?: string;
}

export const EditorTab: React.FC<EditorTabProps> = ({
  workflowId,
  nodeId,
  promptField,
  value,
  onDraftEdit,
  onAccepted,
  latestDraftRef,
  fieldLabel,
  historyState,
  caps,
  defaultProviderId,
}) => {
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState(defaultProviderId || '');
  const [selectedTechniques, setSelectedTechniques] = useState<string[]>(['contains']);
  const [evalResults, setEvalResults] = useState<PromptEvalResponse | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<PromptOptimizeResponse | null>(null);
  const [optimizedEvalResults, setOptimizedEvalResults] = useState<PromptEvalResponse | null>(null);
  const [optimizeInstructions, setOptimizeInstructions] = useState('');
  // Bumped on Accept/Dismiss/new suggestions to prevent stale applies
  const acceptTokenRef = useRef(0);

  const TECHNIQUES = [
    { key: 'exact_match', label: 'Exact Match' },
    { key: 'contains', label: 'Contains' },
    { key: 'nli_eval', label: 'NLI Semantic Match' },
  ];

  const { data: providers = [] } = useQuery({
    queryKey: ['llmProviders'],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });

  const goldSuiteId = historyState.goldSuiteId;

  const goldCasesQuery = useQuery({
    queryKey: ['goldCases', goldSuiteId],
    queryFn: () => listTestCases(goldSuiteId!),
    enabled: !!goldSuiteId && caps.canReadCases,
  });

  // Gate distinguishes forbidden/failed reads from empty datasets
  const casesState: CasesState = {
    status:
      !goldSuiteId || !caps.canReadCases
        ? 'idle'
        : goldCasesQuery.isPending
          ? 'pending'
          : goldCasesQuery.isError
            ? 'error'
            : goldCasesQuery.data === null
              ? 'forbidden'
              : 'success',
    count: goldCasesQuery.data?.length ?? 0,
  };

  const toggleTechnique = (key: string) => {
    setSelectedTechniques((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const showError = (action: string, err: unknown) => {
    setError(`Failed to ${action}: ${extractErrorMessage(err, 'Request failed')}`);
    setWarningMessage(null);
    setSuccessMessage(null);
  };

  const evalMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await evaluatePrompt(workflowId, nodeId, promptField, {
        prompt_content: value,
        techniques: selectedTechniques,
        provider_id: selectedProviderId,
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      setEvalResults(data);
    },
    onError: (err) => showError('evaluate prompt', err),
  });

  const optimizeMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const result = await optimizePrompt(workflowId, nodeId, promptField, {
        provider_id: selectedProviderId,
        current_prompt: value,
        instructions: optimizeInstructions || undefined,
        failed_cases: evalResults?.results
          .filter((r) => !r.passed)
          .map((r) => ({
            input: r.input,
            expected: r.expected,
            actual: r.actual,
          })),
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      acceptTokenRef.current += 1;
      setOptimizeResult(data);
      setOptimizedEvalResults(null);
    },
    onError: (err) => showError('optimize prompt', err),
  });

  const evalOptimizedMutation = useMutation({
    mutationFn: async () => {
      if (!optimizeResult) return;
      setError(null);
      const result = await evaluatePrompt(workflowId, nodeId, promptField, {
        prompt_content: optimizeResult.suggested_prompt,
        techniques: selectedTechniques,
        provider_id: selectedProviderId,
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data) => {
      if (data) setOptimizedEvalResults(data);
    },
    onError: (err) => showError('evaluate suggested prompt', err),
  });

  const acceptOptimizedMutation = useMutation({
    mutationFn: async (vars: { content: string; draftAtSubmit: string; token: number }) => {
      setError(null);
      const created = await createPromptVersion(workflowId, nodeId, promptField, {
        content: vars.content,
        label: 'Optimized prompt',
      });
      if (!created) throw new Error('Not allowed to save a version');
      return created;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptHistoryKey(workflowId, nodeId, promptField) });
    },
    onError: (err) => showError('accept optimized prompt', err),
  });

  const evaluate = evaluateGate(historyState, casesState, caps);
  const optimize = optimizeGate(historyState, caps);
  const suggestion = optimizeResult?.suggested_prompt ?? '';
  const accept = acceptGate(historyState, caps, acceptOptimizedMutation.isPending, suggestion);
  const canRunSuggested = evaluate.enabled && !!suggestion.trim();

  // Save, then apply (only if draft/suggestion haven't changed)
  // Callbacks drop on unmount, so closing mid-save is safe
  const handleAcceptOptimized = () => {
    if (!optimizeResult || !accept.enabled) return;
    const token = ++acceptTokenRef.current;
    acceptOptimizedMutation.mutate(
      { content: optimizeResult.suggested_prompt, draftAtSubmit: value, token },
      {
        onSuccess: (created, vars) => {
          const stillCurrent = vars.token === acceptTokenRef.current;
          if (stillCurrent && draftUnchangedSince(vars.draftAtSubmit, latestDraftRef.current)) {
            onAccepted(created.content);
            setSuccessMessage(`Saved as v${created.version_number} and applied to the draft`);
          } else {
            setSuccessMessage(`Saved as v${created.version_number}; the draft was left as it is`);
          }
          if (stillCurrent) {
            setOptimizeResult(null);
            setOptimizedEvalResults(null);
          }
        },
      },
    );
  };

  return (
    <div className="space-y-4 pt-4 px-2">
      {(error || warningMessage || successMessage) && (
        <div className="space-y-2">
          {error && (
            <div className="flex items-center gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {warningMessage && (
            <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{warningMessage}</span>
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
        <Label>LLM Provider</Label>
        <Select value={selectedProviderId} onValueChange={setSelectedProviderId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select provider for evaluation/optimization" />
          </SelectTrigger>
          <SelectContent>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>{fieldLabel}</Label>
        <RichTextarea
          value={value}
          onChange={(e) => onDraftEdit(e.target.value)}
          placeholder="Enter your prompt..."
          rows={10}
          className="w-full font-mono text-sm"
        />
        <div className="text-xs text-muted-foreground text-right">{value.length} characters</div>
      </div>

      <Accordion type="multiple" className="border rounded-lg px-4">
        {caps.canOptimize && (
          <AccordionItem value="optimize">
            <AccordionTrigger className="hover:no-underline">
              <div className="flex items-center justify-between w-full pr-2">
                <span>Optimize Prompt</span>
                {optimizeResult && <span className="text-xs text-muted-foreground">Suggestion ready</span>}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 flex flex-col gap-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      Add optional guidance, then generate an improved prompt suggestion.
                    </p>
                  </div>
                </div>

                <div className="space-y-2 px-2">
                  <Label className="text-sm">Additional Instructions (optional)</Label>
                  <RichTextarea
                    value={optimizeInstructions}
                    onChange={(e) => setOptimizeInstructions(e.target.value)}
                    placeholder="e.g., Make it more concise, add examples, enforce JSON output..."
                    rows={2}
                    className="text-sm"
                  />
                </div>

                {optimizeResult && (
                  <div className="space-y-3 border-t pt-4">
                    <div className="space-y-2">
                      <Label className="text-sm font-medium">Suggested Prompt</Label>
                      <div className="border rounded p-3 bg-muted text-sm font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                        {optimizeResult.suggested_prompt}
                      </div>
                    </div>
                    {optimizeResult.explanation && (
                      <div className="space-y-1">
                        <Label className="text-sm font-medium">Explanation</Label>
                        <p className="text-sm text-muted-foreground">{optimizeResult.explanation}</p>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {caps.canEvaluate && (
                        <GateTooltip
                          reason={
                            evaluate.reason ??
                            (suggestion.trim() ? null : 'The suggested prompt is empty.')
                          }
                        >
                        <Button
                          size="sm"
                          onClick={() => {
                            if (!canRunSuggested) return;
                            evalOptimizedMutation.mutate();
                          }}
                          disabled={
                            !canRunSuggested ||
                            !selectedProviderId ||
                            selectedTechniques.length === 0 ||
                            evalOptimizedMutation.isPending
                          }
                          variant="outline"
                        >
                          {evalOptimizedMutation.isPending ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4 mr-2" />
                          )}
                          {evalOptimizedMutation.isPending ? 'Evaluating...' : 'Evaluate Suggested'}
                        </Button>
                        </GateTooltip>
                      )}
                      {caps.canEditPrompt && (
                        <GateTooltip reason={accept.reason}>
                        <Button
                          size="sm"
                          onClick={handleAcceptOptimized}
                          disabled={!accept.enabled}
                        >
                          {acceptOptimizedMutation.isPending ? 'Accepting...' : 'Accept & Save as Version'}
                        </Button>
                        </GateTooltip>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          acceptTokenRef.current += 1;
                          setOptimizeResult(null);
                          setOptimizedEvalResults(null);
                        }}
                      >
                        Dismiss
                      </Button>
                    </div>

                    {optimizedEvalResults && (
                      <div className="space-y-3 border-t pt-3">
                        <div className="flex flex-wrap items-center gap-3">
                          <p className="text-sm font-medium">Suggested Prompt Evaluation</p>
                          <Badge variant="secondary">
                            {optimizedEvalResults.summary.passed}/{optimizedEvalResults.summary.total} passed
                          </Badge>
                          <Badge variant="secondary">
                            Avg Score: {(optimizedEvalResults.summary.avg_score * 100).toFixed(1)}%
                          </Badge>
                        </div>
                        <div className="space-y-2 max-h-60 overflow-y-auto">
                          {optimizedEvalResults.results.map((r, i) => (
                            <div
                              key={r.case_id || i}
                              className={`border rounded p-3 text-sm ${
                                r.passed ? 'border-green-200 bg-green-50 dark:border-green-500/30 dark:bg-green-500/15' : 'border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/15'
                              }`}
                            >
                              <div className="flex items-center gap-2 mb-2">
                                {r.passed ? (
                                  <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                                ) : (
                                  <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                                )}
                                <span className="font-medium">{r.passed ? 'Passed' : 'Failed'}</span>
                              </div>
                              <div className="grid grid-cols-3 gap-2 text-xs">
                                <div>
                                  <p className="font-medium text-muted-foreground">Input</p>
                                  <p className="line-clamp-3">{r.input}</p>
                                </div>
                                <div>
                                  <p className="font-medium text-muted-foreground">Expected</p>
                                  <p className="line-clamp-3">{r.expected}</p>
                                </div>
                                <div>
                                  <p className="font-medium text-muted-foreground">Actual</p>
                                  <p className="line-clamp-3">{r.actual}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end">
                  <GateTooltip reason={optimize.reason}>
                    <Button
                      size="sm"
                      onClick={() => {
                        if (!optimize.enabled) return;
                        optimizeMutation.mutate();
                      }}
                      disabled={!optimize.enabled || !selectedProviderId || !value.trim() || optimizeMutation.isPending}
                    >
                      {optimizeMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4 mr-2" />
                      )}
                      {optimizeMutation.isPending ? 'Optimizing...' : 'Optimize'}
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
                {evalResults && (
                  <span className="text-xs text-muted-foreground">
                    {evalResults.summary.passed}/{evalResults.summary.total} passed
                  </span>
                )}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-wrap gap-2">
                    {TECHNIQUES.map((t) => (
                      <div key={t.key} className="flex items-center gap-2">
                        <Switch
                          checked={selectedTechniques.includes(t.key)}
                          onCheckedChange={() => toggleTechnique(t.key)}
                        />
                        <Label className="text-sm cursor-pointer">{t.label}</Label>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-end">
                    <GateTooltip reason={evaluate.reason}>
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => {
                        setWarningMessage(null);
                        if (!evaluate.enabled) {
                          if (evaluate.reason) setWarningMessage(evaluate.reason);
                          return;
                        }
                        evalMutation.mutate();
                      }}
                      disabled={
                        !evaluate.enabled ||
                        !selectedProviderId ||
                        selectedTechniques.length === 0 ||
                        !value.trim() ||
                        evalMutation.isPending
                      }
                    >
                      {evalMutation.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4 mr-2" />
                      )}
                      {evalMutation.isPending ? 'Evaluating...' : 'Run Evaluation'}
                    </Button>
                    </GateTooltip>
                  </div>
                </div>

                {evalResults && (
                  <div className="space-y-3">
                    <div className="flex gap-3">
                      <Badge variant="secondary">
                        {evalResults.summary.passed}/{evalResults.summary.total} passed
                      </Badge>
                      <Badge variant="secondary">Avg Score: {(evalResults.summary.avg_score * 100).toFixed(1)}%</Badge>
                    </div>

                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {evalResults.results.map((r, i) => (
                        <div
                          key={r.case_id || i}
                          className={`border rounded p-3 text-sm ${
                            r.passed ? 'border-green-200 bg-green-50 dark:border-green-500/30 dark:bg-green-500/15' : 'border-red-200 bg-red-50 dark:border-red-500/30 dark:bg-red-500/15'
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            {r.passed ? (
                              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                            )}
                            <span className="font-medium">{r.passed ? 'Passed' : 'Failed'}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div>
                              <p className="font-medium text-muted-foreground">Input</p>
                              <p className="line-clamp-3">{r.input}</p>
                            </div>
                            <div>
                              <p className="font-medium text-muted-foreground">Expected</p>
                              <p className="line-clamp-3">{r.expected}</p>
                            </div>
                            <div>
                              <p className="font-medium text-muted-foreground">Actual</p>
                              <p className="line-clamp-3">{r.actual}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>
    </div>
  );
};
