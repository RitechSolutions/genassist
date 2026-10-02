import { useCallback, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { evaluatePrompt, optimizePrompt } from "@/services/promptEditor";
import { extractErrorMessage } from "@/helpers/apiError";
import type { LLMProvider } from "@/interfaces/llmProvider.interface";
import type {
  PreviousAttemptPayload,
  PromptOptimizeResponse,
  PromptTechniqueConfigs,
} from "@/interfaces/promptEditor.interface";
import type { PromptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import {
  acceptGate,
  evaluateGate,
  HOLDOUT_OFF_REASON,
  HOLDOUT_STALE_REASON,
  optimizeGate,
  pairedKeysMatch,
  retryGate,
  type EvalInputs,
  type Gate,
  type HistoryState,
  type RunInputs,
} from "../../utils/promptEditorGates";
import {
  DEFAULT_HOLDOUT_SHARE,
  type CaseSplitResult,
} from "../../utils/caseSplit";
import {
  DEFAULT_CASES_TO_CHECK,
  entailScoreProblem,
  MAX_CHECK_CASES,
  parseEntailScore,
  phrasesProblem,
  splitForbiddenPhrases,
} from "../../utils/promptEditorTechniques";
import {
  canonicalJson,
  evalKeyOf,
  failedCaseCount,
  failedCasesOf,
  failuresKeyOf,
  isOptimizeCurrent,
  measurementContextKeyOf,
  optimizeKeyOf,
  staleOf,
  type EvalRequest,
  type EvalRunState,
  type OptimizeRequest,
  type RunSnapshot,
  type SuggestedRunState,
} from "../../utils/promptEditorRuns";
import {
  compareRuns,
  type ChallengerComparison,
} from "../../utils/promptEditorResults";
import {
  baselineOf,
  countsOf,
  MAX_ROUNDS,
  optimizerHistoryOf,
  regressionsOf,
  type Baseline,
  type Round,
} from "../../utils/promptEditorRounds";
import {
  bindingChangeNote,
  comparePromptBindings,
} from "../../utils/templateVariableDiagnostics";
import { usePromptGoldCases } from "./usePromptGoldCases";
import { usePromptProviders } from "./usePromptProviders";

type PairedHalf = EvalRunState | null;

/**
 * Both requests built before sending, so config changes mid-flight don't affect
 * the second. Baseline carries `next`, the chained request, and both halves share
 * one snapshot: same provider, same split
 */
type HoldoutVars =
  | {
      half: "baseline";
      request: EvalRequest;
      next: EvalRequest;
      snapshot: RunSnapshot;
      token: number;
    }
  | {
      half: "suggestion";
      request: EvalRequest;
      snapshot: RunSnapshot;
      token: number;
    };

type OptimizeVars = OptimizeRequest & {
  previousAttempts: PreviousAttemptPayload[];
  token: number;
  draftAtSubmit: string;
};

interface HoldoutRun {
  baseline: PairedHalf;
  suggestion: PairedHalf;
  pending: "baseline" | "suggestion" | null;
  /** Keeps the variables, because TanStack clears them when the mutation resets */
  error: {
    half: "baseline" | "suggestion";
    message: string;
    vars: HoldoutVars;
  } | null;
}

/** A 500 and the duplicate-version 400 carry no key, so a missing one is normal */
const errorKeyOf = (err: unknown): string | null => {
  const data = (err as { response?: { data?: { error_key?: unknown } } })
    ?.response?.data;
  return typeof data?.error_key === "string" ? data.error_key : null;
};

/** A gate and the action it guards, so a button reads one object */
export interface PromptAction extends Gate {
  run: () => void;
  /** In flight, for the button's own label and spinner */
  pending: boolean;
}

export interface UsePromptMeasurementArgs {
  workflowId: string;
  nodeId: string;
  promptField: string;
  /** The live draft */
  draft: string;
  /** Accepted suggestion, applied to the draft */
  onAccepted: (newValue: string) => void;
  historyState: HistoryState;
  caps: PromptEditorCapabilities;
  defaultProviderId?: string;
}

export interface PromptMeasurementState {
  error: string | null;
  successMessage: string | null;

  providers: LLMProvider[];
  activeEvalProviderId: string;
  setEvalProviderId: (id: string) => void;
  activeOptimizeProviderId: string;
  setOptimizeProviderId: (id: string) => void;
  providerStatus: RunInputs["providerStatus"];

  selectedTechniques: string[];
  toggleTechnique: (key: string) => void;
  notContainsSelected: boolean;
  phrasesText: string;
  setPhrasesText: (text: string) => void;
  phrasesIssue: string | null;
  nliSelected: boolean;
  nliScoreText: string;
  setNliScoreText: (text: string) => void;
  nliScoreIssue: string | null;
  casesToCheck: number;
  setCasesToCheck: (count: number) => void;
  split: CaseSplitResult;
  splitActive: boolean;
  setSplitEnabled: (enabled: boolean) => void;
  optimizeInstructions: string;
  setOptimizeInstructions: (text: string) => void;

  evalRun: EvalRunState | null;
  evalStale: boolean;
  /** Failures actually sent to the optimizer, against how many the run found */
  failedIncluded: number;
  failedTotal: number;
  optimizeResult: PromptOptimizeResponse | null;
  optimizeStale: boolean;
  baseScored: boolean;
  draftDiverged: boolean;
  comparison: ChallengerComparison | null;
  baseline: Baseline | null;
  rounds: Round[];
  contextKey: string;
  restoreRound: (id: number) => void;
  restoreBlocked: boolean;
  suggestion: string;
  /** Original prompt sent to optimizer (suggestion rewrites this)
   * Not live draft; drift flagged by `optimizeStale` */
  optimizedFrom: string;
  suggestionEdited: boolean;
  editSuggestion: (text: string) => void;
  /** Warns that the rewrite changed the draft's {{placeholders}} */
  placeholderNote: string | null;
  suggestedEvalRun: SuggestedRunState | null;
  suggestedStale: boolean;
  pairedRun: { baseline: EvalRunState; suggestion: EvalRunState } | null;
  pairedStale: boolean;
  holdoutLook: { consumed: boolean; continuedAfter: boolean };
  holdoutError: {
    half: "baseline" | "suggestion";
    message: string;
    /** Replaying the stored request is only honest while its inputs still hold */
    retry: Gate;
  } | null;
  hasRuns: boolean;

  evaluate: PromptAction;
  optimize: PromptAction;
  evaluateSuggested: PromptAction;
  validateHoldout: PromptAction;
  accept: PromptAction;
  retryHoldout: () => void;
  dismiss: () => void;
}

/**
 * Every prompt measurement in one owner: the runs, the mutations that produce them,
 * the staleness each is judged by, and the gates that guard them. Called once, so the
 * draft and the results it describes can live in different panes
 */
export const usePromptMeasurement = ({
  workflowId,
  nodeId,
  promptField,
  draft,
  onAccepted,
  historyState,
  caps,
  defaultProviderId,
}: UsePromptMeasurementArgs): PromptMeasurementState => {
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedTechniques, setSelectedTechniques] = useState<string[]>([
    "contains",
  ]);
  const [phrasesText, setPhrasesText] = useState("");
  const [nliScoreText, setNliScoreText] = useState("");
  const [casesToCheck, setCasesToCheck] = useState<number>(
    DEFAULT_CASES_TO_CHECK,
  );
  const [splitEnabled, setSplitEnabled] = useState(false);
  // Each run keeps the inputs it was produced from, so changing any of them makes it stale
  const [evalRun, setEvalRun] = useState<EvalRunState | null>(null);
  const [optimizeRun, setOptimizeRun] = useState<{
    request: OptimizeRequest;
    result: PromptOptimizeResponse;
  } | null>(null);
  const [suggestedEvalRun, setSuggestedEvalRun] =
    useState<SuggestedRunState | null>(null);
  const [holdoutRun, setHoldoutRun] = useState<HoldoutRun | null>(null);
  const [suggestionEdit, setSuggestionEdit] = useState<string | null>(null);
  const [optimizeInstructions, setOptimizeInstructions] = useState("");
  // Cases and selection for chain rounds. Set from run data, not from current render
  const [pin, setPin] = useState<{
    ids: string[];
    selectionKey: string;
  } | null>(null);
  const [rounds, setRounds] = useState<Round[]>([]);
  const roundIdRef = useRef(0);
  // Incremented when suggestion is superseded, dismissed, replaced, or accepted
  // Always clears runs together
  const acceptTokenRef = useRef(0);
  const [chainOriginDraft, setChainOriginDraft] = useState<string | null>(null);
  const [holdoutLook, setHoldoutLook] = useState({
    consumed: false,
    continuedAfter: false,
  });
  // Mutation callbacks are reinstalled by an effect, so a request that resolves
  // before it runs would judge the current state by the previous render. What the
  // callbacks read is mirrored here instead
  const holdoutRunRef = useRef(holdoutRun);
  holdoutRunRef.current = holdoutRun;

  const {
    providers,
    activeEvalProviderId,
    setEvalProviderId,
    activeOptimizeProviderId,
    setOptimizeProviderId,
    providerStatus,
    fallbackFor,
    revisionOf,
  } = usePromptProviders(defaultProviderId);

  const goldSuiteId = historyState.goldSuiteId;
  const { casesState, caseRowsKey, split } = usePromptGoldCases(
    goldSuiteId,
    caps.canReadCases,
  );

  // Sent, keyed and gated trimmed, blank means no instructions
  const instructions = optimizeInstructions.trim();

  const phrases = useMemo(
    () => splitForbiddenPhrases(phrasesText),
    [phrasesText],
  );
  const notContainsSelected = selectedTechniques.includes("not_contains");
  const phrasesIssue = notContainsSelected ? phrasesProblem(phrases) : null;
  const nliSelected = selectedTechniques.includes("nli_eval");
  const nliScore = parseEntailScore(nliScoreText);
  const nliScoreIssue = nliSelected ? entailScoreProblem(nliScore) : null;
  const sentNliScore = nliSelected && nliScoreIssue === null ? nliScore : null;
  const techniqueConfigs = useMemo<PromptTechniqueConfigs>(
    () => ({
      ...(notContainsSelected ? { not_contains: { phrases } } : {}),
      ...(sentNliScore === null
        ? {}
        : { nli_eval: { min_entail_score: sentNliScore } }),
    }),
    [notContainsSelected, phrases, sentNliScore],
  );
  const sentTechniqueConfigs = useMemo<PromptTechniqueConfigs>(
    () => (phrasesIssue === null ? techniqueConfigs : {}),
    [phrasesIssue, techniqueConfigs],
  );

  const splitActive = splitEnabled && split.feasible;
  const evalCaseIds = useMemo(
    () =>
      splitActive ? split.dev.slice(0, MAX_CHECK_CASES).map((c) => c.id) : null,
    [splitActive, split],
  );
  const holdoutCaseIds = useMemo(
    () => split.holdout.slice(0, MAX_CHECK_CASES).map((c) => c.id),
    [split],
  );

  const evalProviderRevision = revisionOf(activeEvalProviderId);
  const optimizeProviderRevision = revisionOf(activeOptimizeProviderId);

  const buildEvalRequest = useCallback(
    (prompt: string, caseIds: string[] | null): EvalRequest => ({
      key: evalKeyOf({
        prompt,
        providerId: activeEvalProviderId,
        providerRevision: evalProviderRevision,
        techniques: selectedTechniques,
        techniqueConfigs,
        caseIds,
        maxCases: casesToCheck,
        caseRowsKey,
      }),
      prompt,
      providerId: activeEvalProviderId,
      techniques: selectedTechniques,
      techniqueConfigs,
      caseIds,
      maxCases: casesToCheck,
    }),
    [
      activeEvalProviderId,
      evalProviderRevision,
      selectedTechniques,
      techniqueConfigs,
      casesToCheck,
      caseRowsKey,
    ],
  );

  const toggleTechnique = (key: string) => {
    setSelectedTechniques((prev) =>
      prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key],
    );
  };

  const searchContinued = () =>
    setHoldoutLook((prev) =>
      prev.consumed && !prev.continuedAfter
        ? { ...prev, continuedAfter: true }
        : prev,
    );

  const editSuggestion = (text: string) => {
    setSuggestionEdit(text);
    searchContinued();
  };

  const showError = (action: string, err: unknown) => {
    setError(
      `Failed to ${action}: ${extractErrorMessage(err, "Request failed")}`,
    );
    setSuccessMessage(null);
    if (errorKeyOf(err) === "PROMPT_CASE_SELECTION_INVALID") {
      queryClient.invalidateQueries({ queryKey: ["goldCases", goldSuiteId] });
      setHoldoutRun(null);
    }
  };

  const evalStale =
    evalRun !== null &&
    staleOf(evalRun.key, buildEvalRequest(draft, evalCaseIds).key);

  const optimizeResult = optimizeRun?.result ?? null;
  const suggestion = suggestionEdit ?? optimizeResult?.suggested_prompt ?? "";
  const base = suggestion !== "" ? suggestion : draft;

  const caseSplit = useMemo(
    () =>
      splitActive
        ? { holdoutShare: DEFAULT_HOLDOUT_SHARE, holdoutIds: holdoutCaseIds }
        : null,
    [splitActive, holdoutCaseIds],
  );

  const contextKeyFor = useCallback(
    (caseIds: readonly string[] | null): string =>
      measurementContextKeyOf({
        providerId: activeEvalProviderId,
        providerRevision: evalProviderRevision,
        techniques: selectedTechniques,
        techniqueConfigs,
        caseIds,
        maxCases: casesToCheck,
        caseRowsKey,
        holdoutIds: splitActive ? holdoutCaseIds : null,
      }),
    [
      activeEvalProviderId,
      evalProviderRevision,
      selectedTechniques,
      techniqueConfigs,
      casesToCheck,
      caseRowsKey,
      splitActive,
      holdoutCaseIds,
    ],
  );

  const evalContextKey = useMemo(
    () => contextKeyFor(evalCaseIds),
    [contextKeyFor, evalCaseIds],
  );
  const optimizeKeyInputs = useMemo(
    () => ({
      providerId: activeOptimizeProviderId,
      providerRevision: optimizeProviderRevision,
      instructions,
      caseSplit,
      caseRowsKey,
      techniques: selectedTechniques,
      techniqueConfigs: sentTechniqueConfigs,
      sourceEvalKey: evalContextKey,
    }),
    [
      activeOptimizeProviderId,
      optimizeProviderRevision,
      instructions,
      caseSplit,
      caseRowsKey,
      selectedTechniques,
      sentTechniqueConfigs,
      evalContextKey,
    ],
  );
  // Editing the draft or the suggestion don't stales the rewrite
  const optimizeStale = useMemo(
    () =>
      optimizeRun !== null &&
      !isOptimizeCurrent(
        optimizeRun.request,
        optimizeKeyOf({
          ...optimizeKeyInputs,
          prompt: optimizeRun.request.prompt,
        }),
      ),
    [optimizeRun, optimizeKeyInputs],
  );

  // The note is about what the rewrite changed
  const placeholderNote = useMemo(
    () =>
      optimizeRun
        ? bindingChangeNote(
            comparePromptBindings(optimizeRun.request.prompt, suggestion),
          )
        : null,
    [optimizeRun, suggestion],
  );

  const selectionKey = useMemo(
    () =>
      canonicalJson({
        splitActive,
        holdoutIds: splitActive ? holdoutCaseIds : null,
        caseRowsKey,
        casesToCheck,
      }),
    [splitActive, holdoutCaseIds, caseRowsKey, casesToCheck],
  );
  const chainCaseIds = pin && pin.selectionKey === selectionKey ? pin.ids : null;

  const suggestedCaseIds =
    chainCaseIds ??
    (splitActive
      ? evalCaseIds
      : evalRun && !evalStale
        ? evalRun.results.provenance.evaluated_case_ids
        : null);
  const contextKey = useMemo(
    () => contextKeyFor(suggestedCaseIds),
    [contextKeyFor, suggestedCaseIds],
  );
  const suggestedRunKey = useMemo(
    () =>
      suggestedEvalRun === null || suggestion === ""
        ? null
        : buildEvalRequest(suggestion, suggestedEvalRun.caseIds).key,
    [buildEvalRequest, suggestion, suggestedEvalRun],
  );
  const suggestedStale =
    suggestedEvalRun !== null &&
    (optimizeStale ||
      suggestedRunKey === null ||
      staleOf(suggestedEvalRun.key, suggestedRunKey));

  const baseRun =
    suggestion !== ""
      ? suggestedEvalRun && !suggestedStale
        ? suggestedEvalRun
        : null
      : evalRun && !evalStale
        ? evalRun
        : null;
  const failedCases = useMemo(
    () => (baseRun ? failedCasesOf(baseRun.results.results) : []),
    [baseRun],
  );
  const failedTotal = baseRun ? failedCaseCount(baseRun.results.results) : 0;
  // Requires matching context; model switch mid-chain leaves nothing to compare. Memoized to skip recomputation
  const baseline = useMemo(
    () => baselineOf(rounds, contextKey, evalRun, evalStale),
    [rounds, contextKey, evalRun, evalStale],
  );
  const comparison = useMemo(
    () =>
      baseline && suggestedEvalRun && !suggestedStale
        ? compareRuns(baseline.run.results, suggestedEvalRun.results)
        : null,
    [baseline, suggestedEvalRun, suggestedStale],
  );

  /** Captured in the same expression that builds the request: resolving either field
   *  in a callback would read whatever the form holds when the run returns. The
   *  fallback names the request's own provider, never whichever selector moved since */
  const runSnapshotOf = (leaky: boolean, providerId: string): RunSnapshot => ({
    leaky,
    providerFallback: fallbackFor(providerId),
  });

  /** Both halves a paired run would send right now. Null when the paired flow does
   *  not apply, which also disables retry */
  const pairedRequests = useMemo(
    () =>
      splitActive && suggestion !== "" && holdoutCaseIds.length > 0
        ? {
            baseline: buildEvalRequest(draft, holdoutCaseIds),
            suggestion: buildEvalRequest(suggestion, holdoutCaseIds),
          }
        : null,
    [splitActive, suggestion, draft, holdoutCaseIds, buildEvalRequest],
  );
  const pairedKeys = pairedRequests
    ? {
        baselineKey: pairedRequests.baseline.key,
        suggestionKey: pairedRequests.suggestion.key,
      }
    : null;
  // Mirrored for the callbacks, as above
  const pairedKeysRef = useRef(pairedKeys);
  pairedKeysRef.current = pairedKeys;

  const runEvaluation = async (vars: EvalRequest) => {
    setError(null);
    const result = await evaluatePrompt(workflowId, nodeId, promptField, {
      prompt_content: vars.prompt,
      techniques: vars.techniques,
      provider_id: vars.providerId,
      technique_configs: vars.techniqueConfigs,
      ...(vars.caseIds
        ? { case_ids: vars.caseIds }
        : { max_cases: vars.maxCases }),
    });
    if (!result)
      throw new Error("Server returned empty response — check permissions.");
    return result;
  };

  const evalMutation = useMutation({
    mutationFn: (vars: EvalRequest & { snapshot: RunSnapshot }) =>
      runEvaluation(vars),
    onSuccess: (data, vars) =>
      setEvalRun({ key: vars.key, results: data, ...vars.snapshot }),
    onError: (err) => showError("evaluate prompt", err),
  });

  const optimizeMutation = useMutation({
    mutationFn: async (vars: OptimizeVars) => {
      setError(null);
      const result = await optimizePrompt(workflowId, nodeId, promptField, {
        provider_id: vars.providerId,
        current_prompt: vars.prompt,
        instructions: vars.instructions || undefined,
        failed_cases: vars.failedCases?.map((c) => ({
          case_id: c.caseId,
          actual: c.actual,
          failed_metrics: c.failedMetrics,
          feedback: c.feedback ?? undefined,
        })),
        case_split: vars.caseSplit
          ? { holdout_case_ids: [...vars.caseSplit.holdoutIds] }
          : undefined,
        techniques: vars.techniques,
        technique_configs: vars.techniqueConfigs,
        previous_attempts:
          vars.previousAttempts.length > 0 ? vars.previousAttempts : undefined,
      });
      if (!result)
        throw new Error("Server returned empty response — check permissions.");
      return result;
    },
    onSuccess: (data, vars) => {
      const { previousAttempts, token, draftAtSubmit, ...request } = vars;
      if (token !== acceptTokenRef.current) return;
      const outgoing = outgoingRoundRef.current();
      if (outgoing) pushRound(outgoing);
      setChainOriginDraft((prev) => prev ?? draftAtSubmit);
      acceptTokenRef.current += 1;
      setOptimizeRun({ request, result: data });
      // A new suggestion invalidates the old one's scores; the baseline is keyed to
      // the current prompt and stays valid
      setSuggestedEvalRun(null);
      setSuggestionEdit(null);
      setHoldoutRun((prev) =>
        prev ? { ...prev, suggestion: null, error: null } : prev,
      );
      searchContinued();
    },
    onError: (err) => showError("optimize prompt", err),
  });

  const evalOptimizedMutation = useMutation({
    mutationFn: (
      vars: EvalRequest & {
        token: number;
        selectionKey: string;
        snapshot: RunSnapshot;
      },
    ) => runEvaluation(vars),
    onSuccess: (data, vars) => {
      if (vars.token !== acceptTokenRef.current) return;
      setSuggestedEvalRun({
        key: vars.key,
        caseIds: vars.caseIds,
        results: data,
        ...vars.snapshot,
      });
      setPin((prev) =>
        prev && prev.selectionKey === vars.selectionKey
          ? prev
          : {
              ids: data.provenance.evaluated_case_ids,
              selectionKey: vars.selectionKey,
            },
      );
    },
    onError: (err) => showError("evaluate suggested prompt", err),
  });

  const holdoutMutation = useMutation({
    mutationFn: (vars: HoldoutVars) => runEvaluation(vars.request),
    onSuccess: (data, vars) => {
      const half: PairedHalf = {
        key: vars.request.key,
        results: data,
        ...vars.snapshot,
      };
      const superseded = vars.token !== acceptTokenRef.current;

      if (vars.half === "suggestion") {
        if (!superseded) setHoldoutLook((prev) => ({ ...prev, consumed: true }));
        setHoldoutRun((prev) =>
          prev
            ? {
                ...prev,
                suggestion: superseded ? prev.suggestion : half,
                pending: null,
              }
            : prev,
        );
        return;
      }
      // The chained half was built before the baseline left, so it only runs while
      // both sides still describe the current inputs
      const chainStale = !pairedKeysMatch(
        { baselineKey: vars.request.key, suggestionKey: vars.next.key },
        pairedKeysRef.current,
      );
      // Only replace the banner where the row carrying the reason will render: a run
      // dropped mid-flight has none, and a skipped half is not worth reporting there
      const chainSkipped = chainStale && !superseded;
      if (chainSkipped && holdoutRunRef.current !== null)
        setSuccessMessage(null);
      setHoldoutRun((prev) =>
        prev
          ? {
              ...prev,
              baseline: half,
              pending: superseded || chainStale ? null : "suggestion",
              error: chainSkipped
                ? {
                    half: "suggestion",
                    message: HOLDOUT_STALE_REASON,
                    vars: {
                      half: "suggestion",
                      request: vars.next,
                      snapshot: vars.snapshot,
                      token: vars.token,
                    },
                  }
                : prev.error,
            }
          : prev,
      );
      if (superseded || chainStale) return;
      holdoutMutation.mutate({
        half: "suggestion",
        request: vars.next,
        snapshot: vars.snapshot,
        token: vars.token,
      });
    },
    onError: (err, vars) => {
      const noun = vars.half === "baseline" ? "current" : "suggested";
      // The inline row owns this message, so the banner writes it only when there is
      // no row to write: an invalid case selection drops the run, and Dismiss or
      // Accept can drop it while the half is still in flight
      if (
        holdoutRunRef.current === null ||
        errorKeyOf(err) === "PROMPT_CASE_SELECTION_INVALID"
      ) {
        showError(`evaluate the ${noun} prompt`, err);
        return;
      }
      setSuccessMessage(null);
      setHoldoutRun((prev) =>
        prev
          ? {
              ...prev,
              pending: null,
              error: {
                half: vars.half,
                message: extractErrorMessage(err, "Request failed"),
                vars,
              },
            }
          : prev,
      );
    },
  });

  // One base, two providers, every evaluation is gated on the model that scores it,
  // the rewrite on the model that writes it
  const runInputs: Omit<EvalInputs, "providerId"> = {
    content: draft,
    contentNoun: "prompt",
    providerStatus,
    techniqueCount: selectedTechniques.length,
    phrasesProblem: phrasesIssue,
    entailScoreProblem: nliScoreIssue,
  };
  const evalInputs: EvalInputs = {
    ...runInputs,
    providerId: activeEvalProviderId,
  };

  const evaluate = evaluateGate(historyState, casesState, caps, evalInputs);
  const optimize = optimizeGate(historyState, caps, {
    ...runInputs,
    content: base,
    providerId: activeOptimizeProviderId,
    instructions,
  });
  const evaluateSuggested = evaluateGate(historyState, casesState, caps, {
    ...evalInputs,
    content: suggestion,
    contentNoun: "suggested prompt",
    stale: optimizeStale,
  });
  const holdoutOff = !splitActive || holdoutCaseIds.length === 0;
  const validateHoldout: Gate = !evaluateSuggested.enabled
    ? evaluateSuggested
    : holdoutOff
      ? { enabled: false, reason: HOLDOUT_OFF_REASON }
      : evaluate;
  const accept = acceptGate(historyState, caps, suggestion, {
    pending: false,
    stale: optimizeStale,
  });

  const hasRuns =
    evalRun !== null ||
    optimizeRun !== null ||
    suggestedEvalRun !== null ||
    holdoutRun !== null;
  const pairedRun =
    holdoutRun?.baseline && holdoutRun.suggestion
      ? { baseline: holdoutRun.baseline, suggestion: holdoutRun.suggestion }
      : null;
  const pairedStale =
    pairedRun !== null &&
    !pairedKeysMatch(
      {
        baselineKey: pairedRun.baseline.key,
        suggestionKey: pairedRun.suggestion.key,
      },
      pairedKeys,
    );

  const storedRetry = holdoutRun?.error ?? null;
  const holdoutError = storedRetry
    ? {
        half: storedRetry.half,
        message: storedRetry.message,
        // A replay is still an evaluation, so whatever blocks one blocks the other
        retry: evaluate.enabled
          ? retryGate(
              {
                half: storedRetry.half,
                requestKey: storedRetry.vars.request.key,
                nextKey:
                  storedRetry.vars.half === "baseline"
                    ? storedRetry.vars.next.key
                    : undefined,
                storedBaselineKey: holdoutRun?.baseline?.key ?? null,
              },
              pairedKeys,
            )
          : evaluate,
      }
    : null;

  const nextRoundId = () => (roundIdRef.current += 1);

  /** The round currently on screen, as a filing record. Null when there is no suggestion */
  const outgoingRound = (): Omit<Round, "id"> | null =>
    optimizeRun && {
      source: optimizeRun,
      suggestion,
      run: suggestedStale ? null : suggestedEvalRun,
      incomplete: comparison?.incomplete ?? null,
      counts: comparison ? countsOf(comparison.comparison) : null,
      regressions: comparison ? regressionsOf(comparison.comparison) : [],
      contextKey,
    };
  const outgoingRoundRef = useRef(outgoingRound);
  outgoingRoundRef.current = outgoingRound;

  const pushRound = (round: Omit<Round, "id">) => {
    const filed = { ...round, id: nextRoundId() };
    setRounds((prev) => [filed, ...prev].slice(0, MAX_ROUNDS));
  };

  // Restores earlier round (saves current). Blocked if rewrite in-flight
  const restoreRound = (id: number) => {
    const round = rounds.find((r) => r.id === id);
    if (!round || optimizeMutation.isPending) return;
    const outgoing = outgoingRound();
    const filed = outgoing ? { ...outgoing, id: nextRoundId() } : null;
    acceptTokenRef.current += 1;
    setRounds((prev) => {
      const kept = prev.filter((r) => r.id !== id);
      return filed ? [filed, ...kept].slice(0, MAX_ROUNDS) : kept;
    });
    setOptimizeRun(round.source);
    setSuggestionEdit(
      round.suggestion === round.source.result.suggested_prompt
        ? null
        : round.suggestion,
    );
    setSuggestedEvalRun(round.run);
    setHoldoutRun((prev) =>
      prev ? { ...prev, suggestion: null, error: null } : prev,
    );
    searchContinued();
  };

  const clearChain = () => {
    setRounds([]);
    setPin(null);
    setChainOriginDraft(null);
    setHoldoutLook({ consumed: false, continuedAfter: false });
  };

  /** Runs the hold-out under the current prompt, then under the suggestion */
  const startPairedRun = () => {
    if (!validateHoldout.enabled || !pairedRequests) return;
    const token = acceptTokenRef.current;
    const { baseline, suggestion: suggested } = pairedRequests;
    const snapshot = runSnapshotOf(false, baseline.providerId);
    const reuseBaseline = holdoutRun?.baseline?.key === baseline.key;
    setHoldoutRun((prev) => ({
      baseline: reuseBaseline && prev ? prev.baseline : null,
      suggestion: null,
      pending: reuseBaseline ? "suggestion" : "baseline",
      error: null,
    }));
    holdoutMutation.mutate(
      reuseBaseline
        ? { half: "suggestion", request: suggested, snapshot, token }
        : {
            half: "baseline",
            request: baseline,
            next: suggested,
            snapshot,
            token,
          },
    );
  };

  const handleEvaluateSuggested = () => {
    if (!evaluateSuggested.enabled) return;
    const request = buildEvalRequest(suggestion, suggestedCaseIds);
    evalOptimizedMutation.mutate({
      ...request,
      token: acceptTokenRef.current,
      selectionKey,
      snapshot: runSnapshotOf(true, request.providerId),
    });
  };

  // Applies the suggestion to the draft and ends the chain
  const handleAcceptOptimized = () => {
    if (!optimizeResult || !accept.enabled) return;
    onAccepted(suggestion);
    setError(null);
    setSuccessMessage("Applied to the draft. Save a version to keep it.");
    acceptTokenRef.current += 1;
    setOptimizeRun(null);
    setSuggestedEvalRun(null);
    setSuggestionEdit(null);
    setHoldoutRun(null);
    clearChain();
  };

  const runOptimize = () => {
    if (!optimize.enabled) return;
    optimizeMutation.mutate({
      key: optimizeKeyOf({ ...optimizeKeyInputs, prompt: base }),
      prompt: base,
      providerId: activeOptimizeProviderId,
      instructions,
      failedCases: failedCases.length > 0 ? failedCases : undefined,
      sourceFailuresKey: failuresKeyOf(failedCases),
      caseSplit,
      techniques: selectedTechniques,
      techniqueConfigs: sentTechniqueConfigs,
      previousAttempts: optimizerHistoryOf(rounds, contextKey),
      token: acceptTokenRef.current,
      draftAtSubmit: draft,
    });
  };

  const retryHoldout = () => {
    if (!storedRetry || !holdoutError?.retry.enabled) return;
    setHoldoutRun((prev) =>
      prev ? { ...prev, pending: storedRetry.half, error: null } : prev,
    );
    holdoutMutation.mutate({
      ...storedRetry.vars,
      token: acceptTokenRef.current,
    });
  };

  const dismiss = () => {
    acceptTokenRef.current += 1;
    setOptimizeRun(null);
    setSuggestedEvalRun(null);
    setSuggestionEdit(null);
    setHoldoutRun(null);
    clearChain();
  };

  return {
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
    nliSelected,
    nliScoreText,
    setNliScoreText,
    nliScoreIssue,
    casesToCheck,
    setCasesToCheck,
    split,
    splitActive,
    setSplitEnabled,
    optimizeInstructions,
    setOptimizeInstructions,

    evalRun,
    evalStale,
    failedIncluded: failedCases.length,
    failedTotal,
    optimizeResult,
    optimizeStale,
    baseScored: baseRun !== null,
    draftDiverged: chainOriginDraft !== null && draft !== chainOriginDraft,
    comparison,
    baseline,
    rounds,
    contextKey,
    restoreRound,
    restoreBlocked: optimizeMutation.isPending,
    suggestion,
    optimizedFrom: optimizeRun?.request.prompt ?? "",
    suggestionEdited: suggestion !== (optimizeResult?.suggested_prompt ?? ""),
    editSuggestion,
    placeholderNote,
    suggestedEvalRun,
    suggestedStale,
    pairedRun,
    pairedStale,
    holdoutLook,
    holdoutError,
    hasRuns,

    evaluate: {
      ...evaluate,
      run: () => {
        if (!evaluate.enabled) return;
        const request = buildEvalRequest(draft, evalCaseIds);
        evalMutation.mutate({
          ...request,
          snapshot: runSnapshotOf(splitActive, request.providerId),
        });
      },
      pending: evalMutation.isPending,
    },
    optimize: {
      ...optimize,
      run: runOptimize,
      pending: optimizeMutation.isPending,
    },
    evaluateSuggested: {
      ...evaluateSuggested,
      run: handleEvaluateSuggested,
      pending: evalOptimizedMutation.isPending,
    },
    validateHoldout: {
      ...validateHoldout,
      run: startPairedRun,
      pending: holdoutMutation.isPending,
    },
    accept: { ...accept, run: handleAcceptOptimized, pending: false },
    retryHoldout,
    dismiss,
  };
};
