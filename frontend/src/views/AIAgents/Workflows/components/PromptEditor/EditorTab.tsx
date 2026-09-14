import React, { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2, Play, Sparkles } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/accordion';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { RichTextarea } from '@/components/richTextarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Switch } from '@/components/switch';
import { getAllLLMProviders } from '@/services/llmProviders';
import { createPromptVersion, evaluatePrompt, optimizePrompt } from '@/services/promptEditor';
import { listTestCases } from '@/services/testSuites';
import { extractErrorMessage } from '@/helpers/apiError';
import { methodLabel } from '@/views/TestSuites/helpers/methodLabels';
import type { LLMProvider } from '@/interfaces/llmProvider.interface';
import type { TestCase } from '@/interfaces/testSuite.interface';
import type {
  PromptEvalResponse,
  PromptOptimizeResponse,
  PromptTechniqueConfigs,
} from '@/interfaces/promptEditor.interface';
import type { PromptEditorCapabilities } from '../../utils/promptEditorCapabilities';
import { acceptGate, evaluateGate, optimizeGate, promptLength } from '../../utils/promptEditorGates';
import type { CasesState, EvalInputs, HistoryState, RunInputs } from '../../utils/promptEditorGates';
import { draftUnchangedSince } from '../../utils/promptEditorHistory';
import { DEFAULT_HOLDOUT_SHARE, splitCasesByConversation } from '../../utils/caseSplit';
import { summaryLine } from '../../utils/promptEditorResults';
import {
  CASES_TO_CHECK_OPTIONS,
  DEFAULT_CASES_TO_CHECK,
  MAX_CHECK_CASES,
  PROMPT_CHECK_TECHNIQUES,
  phrasesProblem,
  splitForbiddenPhrases,
} from '../../utils/promptEditorTechniques';
import {
  canonicalJson,
  evalKeyOf,
  failedCaseCount,
  failedCasesOf,
  failuresKeyOf,
  isOptimizeCurrent,
  optimizeKeyOf,
  staleOf,
  type CaseRow,
  type EvalRequest,
  type OptimizeRequest,
} from '../../utils/promptEditorRuns';
import { GateTooltip } from './GateTooltip';
import { PromptEvalResults } from './PromptEvalResults';
import { promptHistoryKey } from './usePromptHistory';

type PairedHalf = { key: string; results: PromptEvalResponse } | null;

interface HoldoutRun {
  caseIds: string[];
  baseline: PairedHalf;
  suggestion: PairedHalf;
  pending: 'baseline' | 'suggestion' | null;
  /** Keeps the variables, because TanStack clears them when the mutation resets */
  error: { half: 'baseline' | 'suggestion'; message: string; vars: EvalRequest } | null;
}

/** A 500 and the duplicate-version 400 carry no key, so a missing one is normal */
const errorKeyOf = (err: unknown): string | null => {
  const data = (err as { response?: { data?: { error_key?: unknown } } })?.response?.data;
  return typeof data?.error_key === 'string' ? data.error_key : null;
};

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
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState(defaultProviderId || '');
  const [selectedTechniques, setSelectedTechniques] = useState<string[]>(['contains']);
  const [phrasesText, setPhrasesText] = useState('');
  const [casesToCheck, setCasesToCheck] = useState<number>(DEFAULT_CASES_TO_CHECK);
  const [splitEnabled, setSplitEnabled] = useState(false);
  // Each run keeps the inputs it was produced from, so changing any of them makes it stale
  const [evalRun, setEvalRun] = useState<{ key: string; results: PromptEvalResponse } | null>(null);
  const [optimizeRun, setOptimizeRun] = useState<{
    request: OptimizeRequest;
    result: PromptOptimizeResponse;
  } | null>(null);
  const [suggestedEvalRun, setSuggestedEvalRun] = useState<{
    key: string;
    results: PromptEvalResponse;
  } | null>(null);
  const [holdoutRun, setHoldoutRun] = useState<HoldoutRun | null>(null);
  const [optimizeInstructions, setOptimizeInstructions] = useState('');
  // Bumped on Accept/Dismiss/new suggestions to prevent stale applies
  const acceptTokenRef = useRef(0);

  const providersQuery = useQuery({
    queryKey: ['llmProviders'],
    queryFn: getAllLLMProviders,
    select: (data: LLMProvider[]) => data.filter((p) => p.is_active === 1),
  });
  const providers = providersQuery.data ?? [];
  // A default pointing at a deactivated provider must never reach a request
  const activeProviderId = providers.some((p) => p.id === selectedProviderId) ? selectedProviderId : '';
  const activeProvider = providers.find((p) => p.id === activeProviderId);
  const providerStatus: RunInputs['providerStatus'] = providersQuery.isPending
    ? 'pending'
    : providersQuery.isError
      ? 'error'
      : providers.length === 0
        ? 'empty'
        : 'ready';

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

  // Null is a forbidden or unloaded dataset, which is distinct key material from
  // a loaded but empty one. A case without an id cannot be selected or compared
  const caseRows: CaseRow[] | null = useMemo(() => {
    const data = goldCasesQuery.data;
    if (!Array.isArray(data)) return null;
    return data
      .filter((c): c is TestCase & { id: string } => !!c.id)
      .map((c) => ({
        id: c.id,
        input_data: c.input_data,
        expected_output: c.expected_output ?? null,
        source_conversation_id: c.source_conversation_id ?? null,
        turn_index: c.turn_index ?? null,
      }))
      .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  }, [goldCasesQuery.data]);

  // Memoised so a keystroke re-keys only the small run object, not the whole dataset
  const caseRowsKey = useMemo(
    () => (caseRows === null ? null : canonicalJson(caseRows)),
    [caseRows],
  );

  const phrases = useMemo(() => splitForbiddenPhrases(phrasesText), [phrasesText]);
  const notContainsSelected = selectedTechniques.includes('not_contains');
  const phrasesIssue = notContainsSelected ? phrasesProblem(phrases) : null;
  const techniqueConfigs = useMemo<PromptTechniqueConfigs>(
    () => (notContainsSelected ? { not_contains: { phrases } } : {}),
    [notContainsSelected, phrases],
  );

  const split = useMemo(() => splitCasesByConversation(caseRows ?? []), [caseRows]);
  const splitActive = splitEnabled && split.feasible;
  const evalCaseIds = useMemo(
    () => (splitActive ? split.dev.slice(0, MAX_CHECK_CASES).map((c) => c.id) : null),
    [splitActive, split],
  );
  const holdoutCaseIds = useMemo(
    () => split.holdout.slice(0, MAX_CHECK_CASES).map((c) => c.id),
    [split],
  );

  const buildEvalRequest = (prompt: string, caseIds: string[] | null): EvalRequest => ({
    key: evalKeyOf({
      prompt,
      providerId: activeProviderId,
      techniques: selectedTechniques,
      techniqueConfigs,
      caseIds,
      maxCases: casesToCheck,
      caseRowsKey,
    }),
    prompt,
    providerId: activeProviderId,
    techniques: selectedTechniques,
    techniqueConfigs,
    caseIds,
    maxCases: casesToCheck,
  });

  const toggleTechnique = (key: string) => {
    setSelectedTechniques((prev) => (prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]));
  };

  const showError = (action: string, err: unknown) => {
    setError(`Failed to ${action}: ${extractErrorMessage(err, 'Request failed')}`);
    setSuccessMessage(null);
    if (errorKeyOf(err) === 'PROMPT_CASE_SELECTION_INVALID') {
      queryClient.invalidateQueries({ queryKey: ['goldCases', goldSuiteId] });
      setHoldoutRun(null);
    }
  };

  const currentEvalKey = buildEvalRequest(value, evalCaseIds).key;
  const evalStale = evalRun !== null && staleOf(evalRun.key, currentEvalKey);
  const failedCases = evalRun && !evalStale ? failedCasesOf(evalRun.results.results) : [];
  const failedTotal = evalRun && !evalStale ? failedCaseCount(evalRun.results.results) : 0;
  const failuresKey = failuresKeyOf(failedCases);

  const currentOptimizeKey = optimizeKeyOf({
    prompt: value,
    providerId: activeProviderId,
    instructions: optimizeInstructions,
    caseSplit: splitActive ? { holdoutShare: DEFAULT_HOLDOUT_SHARE, holdoutIds: holdoutCaseIds } : null,
    caseRowsKey,
  });
  const optimizeResult = optimizeRun?.result ?? null;
  const optimizeStale =
    optimizeRun !== null &&
    !isOptimizeCurrent(optimizeRun.request, { key: currentOptimizeKey, failuresKey });
  const suggestion = optimizeResult?.suggested_prompt ?? '';

  // Off a split the suggestion reuses the current run's cases, so both sides match
  // One value, because the key must be built from exactly what the run is sent
  const suggestedCaseIds = splitActive
    ? evalCaseIds
    : evalRun && !evalStale
      ? evalRun.results.provenance.evaluated_case_ids
      : null;
  const currentSuggestedKey =
    suggestion === '' ? null : buildEvalRequest(suggestion, suggestedCaseIds).key;
  const suggestedStale =
    suggestedEvalRun !== null &&
    (optimizeStale || currentSuggestedKey === null || staleOf(suggestedEvalRun.key, currentSuggestedKey));

  const runEvaluation = async (vars: EvalRequest) => {
    setError(null);
    const result = await evaluatePrompt(workflowId, nodeId, promptField, {
      prompt_content: vars.prompt,
      techniques: vars.techniques,
      provider_id: vars.providerId,
      technique_configs: vars.techniqueConfigs,
      ...(vars.caseIds ? { case_ids: vars.caseIds } : { max_cases: vars.maxCases }),
    });
    if (!result) throw new Error('Server returned empty response — check permissions.');
    return result;
  };

  const evalMutation = useMutation({
    mutationFn: runEvaluation,
    onSuccess: (data, vars) => setEvalRun({ key: vars.key, results: data }),
    onError: (err) => showError('evaluate prompt', err),
  });

  const optimizeMutation = useMutation({
    mutationFn: async (vars: OptimizeRequest) => {
      setError(null);
      const result = await optimizePrompt(workflowId, nodeId, promptField, {
        provider_id: vars.providerId,
        current_prompt: vars.prompt,
        instructions: vars.instructions || undefined,
        failed_cases: vars.failedCases?.map((c) => ({ case_id: c.caseId, actual: c.actual })),
        case_split: vars.caseSplit
          ? { holdout_case_ids: [...vars.caseSplit.holdoutIds] }
          : undefined,
      });
      if (!result) throw new Error('Server returned empty response — check permissions.');
      return result;
    },
    onSuccess: (data, vars) => {
      acceptTokenRef.current += 1;
      setOptimizeRun({ request: vars, result: data });
      // A new suggestion invalidates the old one's scores; the baseline is keyed to
      // the current prompt and stays valid
      setSuggestedEvalRun(null);
      setHoldoutRun((prev) => (prev ? { ...prev, suggestion: null, error: null } : prev));
    },
    onError: (err) => showError('optimize prompt', err),
  });

  const evalOptimizedMutation = useMutation({
    mutationFn: (vars: EvalRequest & { token: number }) => runEvaluation(vars),
    onSuccess: (data, vars) => {
      if (vars.token !== acceptTokenRef.current) return;
      setSuggestedEvalRun({ key: vars.key, results: data });
    },
    onError: (err) => showError('evaluate suggested prompt', err),
  });

  const holdoutMutation = useMutation({
    mutationFn: (vars: { half: 'baseline' | 'suggestion'; request: EvalRequest; token: number }) =>
      runEvaluation(vars.request),
    onSuccess: (data, vars) => {
      const half: PairedHalf = { key: vars.request.key, results: data };
      const superseded = vars.token !== acceptTokenRef.current;

      if (vars.half === 'suggestion') {
        setHoldoutRun((prev) =>
          prev ? { ...prev, suggestion: superseded ? prev.suggestion : half, pending: null } : prev,
        );
        return;
      }
      setHoldoutRun((prev) =>
        prev ? { ...prev, baseline: half, pending: superseded ? null : 'suggestion' } : prev,
      );
      if (superseded) return;
      holdoutMutation.mutate({
        half: 'suggestion',
        request: buildEvalRequest(suggestion, vars.request.caseIds),
        token: vars.token,
      });
    },
    onError: (err, vars) => {
      setHoldoutRun((prev) =>
        prev
          ? {
              ...prev,
              pending: null,
              error: {
                half: vars.half,
                message: extractErrorMessage(err, 'Request failed'),
                vars: vars.request,
              },
            }
          : prev,
      );
      showError(`evaluate the ${vars.half === 'baseline' ? 'current' : 'suggested'} prompt`, err);
    },
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

  const runInputs: EvalInputs = {
    content: value,
    contentNoun: 'prompt',
    providerStatus,
    providerId: activeProviderId,
    techniqueCount: selectedTechniques.length,
    phrasesProblem: phrasesIssue,
  };

  const evaluate = evaluateGate(historyState, casesState, caps, runInputs);
  const optimize = optimizeGate(historyState, caps, runInputs);
  const evaluateSuggested = evaluateGate(historyState, casesState, caps, {
    ...runInputs,
    content: suggestion,
    contentNoun: 'suggested prompt',
    stale: optimizeStale,
  });
  const accept = acceptGate(historyState, caps, suggestion, {
    pending: acceptOptimizedMutation.isPending,
    stale: optimizeStale,
  });

  const suggestedPending = evalOptimizedMutation.isPending || holdoutMutation.isPending;
  const hasRuns =
    evalRun !== null || optimizeRun !== null || suggestedEvalRun !== null || holdoutRun !== null;
  const pairedRun = holdoutRun?.baseline && holdoutRun.suggestion ? holdoutRun : null;

  /** Runs the hold-out under the current prompt, then under the suggestion */
  const startPairedRun = () => {
    const token = acceptTokenRef.current;
    const baseline = buildEvalRequest(value, holdoutCaseIds);
    const reuseBaseline = holdoutRun?.baseline?.key === baseline.key;
    setHoldoutRun((prev) => ({
      caseIds: holdoutCaseIds,
      baseline: reuseBaseline && prev ? prev.baseline : null,
      suggestion: null,
      pending: reuseBaseline ? 'suggestion' : 'baseline',
      error: null,
    }));
    holdoutMutation.mutate(
      reuseBaseline
        ? { half: 'suggestion', request: buildEvalRequest(suggestion, holdoutCaseIds), token }
        : { half: 'baseline', request: baseline, token },
    );
  };

  const handleEvaluateSuggested = () => {
    if (!evaluateSuggested.enabled) return;
    if (splitActive) {
      startPairedRun();
      return;
    }
    evalOptimizedMutation.mutate({
      ...buildEvalRequest(suggestion, suggestedCaseIds),
      token: acceptTokenRef.current,
    });
  };

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
            setOptimizeRun(null);
            setSuggestedEvalRun(null);
            setHoldoutRun(null);
          }
        },
      },
    );
  };

  const providerFallback = activeProvider
    ? {
        name: activeProvider.name,
        llm_model_provider: activeProvider.llm_model_provider,
        llm_model: activeProvider.llm_model,
      }
    : undefined;

  const runMarkers = (results: PromptEvalResponse, stale: boolean) =>
    `${results.provenance.deadline_hit ? ' · cut by the time budget' : ''}${
      stale ? ' · inputs changed' : ''
    }`;

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
        <Label>LLM Provider</Label>
        <Select value={activeProviderId} onValueChange={setSelectedProviderId}>
          <SelectTrigger className="w-full">
            <SelectValue
              placeholder={
                providerStatus === 'empty'
                  ? 'No active LLM providers are available'
                  : 'Select provider for evaluation/optimization'
              }
            />
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
        <div className="text-xs text-muted-foreground text-right">{promptLength(value)} characters</div>
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
                    {failedTotal > failedCases.length && (
                      <p className="text-xs text-muted-foreground">
                        {failedCases.length} of {failedTotal} failures included.
                      </p>
                    )}
                    {evalStale && (
                      <p className="text-xs text-muted-foreground">
                        The draft changed since the last run, so its failures were left out.
                      </p>
                    )}
                  </div>
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
                        The draft changed since this suggestion. Run Optimize again.
                      </div>
                    )}
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
                        <GateTooltip reason={evaluateSuggested.reason}>
                        <Button
                          size="sm"
                          onClick={handleEvaluateSuggested}
                          disabled={!evaluateSuggested.enabled || suggestedPending}
                          variant="outline"
                        >
                          {suggestedPending ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4 mr-2" />
                          )}
                          {suggestedPending ? 'Evaluating...' : 'Evaluate Suggested'}
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
                          setOptimizeRun(null);
                          setSuggestedEvalRun(null);
                          setHoldoutRun(null);
                        }}
                      >
                        Dismiss
                      </Button>
                    </div>

                    {holdoutRun?.error && (
                      <div className="flex items-center justify-between gap-2 text-destructive text-sm bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                        <span>
                          The {holdoutRun.error.half === 'baseline' ? 'current' : 'suggested'} prompt
                          could not be evaluated: {holdoutRun.error.message}
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const retry = holdoutRun.error!;
                            setHoldoutRun((prev) =>
                              prev ? { ...prev, pending: retry.half, error: null } : prev,
                            );
                            holdoutMutation.mutate({
                              half: retry.half,
                              request: retry.vars,
                              token: acceptTokenRef.current,
                            });
                          }}
                        >
                          Retry
                        </Button>
                      </div>
                    )}

                    {pairedRun && (
                      <div className="border-t pt-3">
                        <PromptEvalResults
                          results={pairedRun.suggestion!.results}
                          title="Hold-out comparison"
                          stale={staleOf(
                            pairedRun.suggestion!.key,
                            buildEvalRequest(suggestion, pairedRun.caseIds).key,
                          )}
                          providerFallback={providerFallback}
                          comparison={{ baseline: pairedRun.baseline!.results }}
                        />
                      </div>
                    )}

                    {!pairedRun && suggestedEvalRun && (
                      <div className="border-t pt-3">
                        <PromptEvalResults
                          results={suggestedEvalRun.results}
                          title="Suggested Prompt Evaluation"
                          stale={suggestedStale}
                          providerFallback={providerFallback}
                          leaky
                        />
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
                        const caseSplit = splitActive
                          ? { holdoutShare: DEFAULT_HOLDOUT_SHARE, holdoutIds: holdoutCaseIds }
                          : null;
                        optimizeMutation.mutate({
                          key: currentOptimizeKey,
                          prompt: value,
                          providerId: activeProviderId,
                          instructions: optimizeInstructions,
                          failedCases: failedCases.length > 0 ? failedCases : undefined,
                          sourceFailuresKey: failuresKey,
                          caseSplit,
                        });
                      }}
                      disabled={!optimize.enabled || optimizeMutation.isPending}
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
                      onClick={() => {
                        if (!evaluate.enabled) return;
                        evalMutation.mutate(buildEvalRequest(value, evalCaseIds));
                      }}
                      disabled={!evaluate.enabled || evalMutation.isPending}
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

                {evalRun && (
                  <PromptEvalResults
                    results={evalRun.results}
                    stale={evalStale}
                    providerFallback={providerFallback}
                    leaky={splitActive}
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
