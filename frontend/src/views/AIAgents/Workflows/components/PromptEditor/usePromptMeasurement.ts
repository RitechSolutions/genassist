import { useCallback, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPromptVersion,
  evaluatePrompt,
  optimizePrompt,
} from "@/services/promptEditor";
import { extractErrorMessage } from "@/helpers/apiError";
import type { LLMProvider } from "@/interfaces/llmProvider.interface";
import type {
  PromptOptimizeResponse,
  PromptTechniqueConfigs,
} from "@/interfaces/promptEditor.interface";
import type { PromptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import {
  acceptGate,
  evaluateGate,
  HOLDOUT_STALE_REASON,
  optimizeGate,
  pairedKeysMatch,
  retryGate,
  type EvalInputs,
  type Gate,
  type HistoryState,
  type RunInputs,
} from "../../utils/promptEditorGates";
import { draftUnchangedSince } from "../../utils/promptEditorHistory";
import {
  DEFAULT_HOLDOUT_SHARE,
  type CaseSplitResult,
} from "../../utils/caseSplit";
import {
  DEFAULT_CASES_TO_CHECK,
  MAX_CHECK_CASES,
  phrasesProblem,
  splitForbiddenPhrases,
} from "../../utils/promptEditorTechniques";
import {
  acceptPayloadOf,
  evalKeyOf,
  failedCaseCount,
  failedCasesOf,
  failuresKeyOf,
  isOptimizeCurrent,
  optimizeKeyOf,
  staleOf,
  type AcceptPayload,
  type EvalRequest,
  type EvalRunState,
  type OptimizeRequest,
  type RunSnapshot,
  type SuggestedRunState,
} from "../../utils/promptEditorRuns";
import {
  bindingChangeNote,
  comparePromptBindings,
} from "../../utils/templateVariableDiagnostics";
import { promptHistoryKey } from "./usePromptHistory";
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
  /** The live draft. Read on every render, so an async apply can see edits made since */
  draft: string;
  /** Accepted optimization that was saved as a version */
  onAccepted: (newValue: string) => void;
  historyState: HistoryState;
  caps: PromptEditorCapabilities;
  defaultProviderId?: string;
}

export interface PromptMeasurementState {
  error: string | null;
  successMessage: string | null;

  providers: LLMProvider[];
  activeProviderId: string;
  setSelectedProviderId: (id: string) => void;
  providerStatus: RunInputs["providerStatus"];

  selectedTechniques: string[];
  toggleTechnique: (key: string) => void;
  notContainsSelected: boolean;
  phrasesText: string;
  setPhrasesText: (text: string) => void;
  phrasesIssue: string | null;
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
  suggestion: string;
  /** Warns that the rewrite changed the draft's {{placeholders}} */
  placeholderNote: string | null;
  suggestedEvalRun: SuggestedRunState | null;
  suggestedStale: boolean;
  pairedRun: { baseline: EvalRunState; suggestion: EvalRunState } | null;
  pairedStale: boolean;
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
  const [optimizeInstructions, setOptimizeInstructions] = useState("");
  // Bumped on Accept/Dismiss/new suggestions to prevent stale applies
  const acceptTokenRef = useRef(0);
  // Guard against stale async overwrites
  const latestDraftRef = useRef(draft);
  latestDraftRef.current = draft;
  // Mutation callbacks are reinstalled by an effect, so a request that resolves
  // before it runs would judge the current state by the previous render. What the
  // callbacks read is mirrored here instead
  const holdoutRunRef = useRef(holdoutRun);
  holdoutRunRef.current = holdoutRun;

  const {
    providers,
    activeProviderId,
    setSelectedProviderId,
    providerStatus,
    providerFallback,
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
  const techniqueConfigs = useMemo<PromptTechniqueConfigs>(
    () => (notContainsSelected ? { not_contains: { phrases } } : {}),
    [notContainsSelected, phrases],
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

  const buildEvalRequest = useCallback(
    (prompt: string, caseIds: string[] | null): EvalRequest => ({
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
    }),
    [
      activeProviderId,
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

  const currentEvalKey = buildEvalRequest(draft, evalCaseIds).key;
  const evalStale = evalRun !== null && staleOf(evalRun.key, currentEvalKey);
  const failedCases =
    evalRun && !evalStale ? failedCasesOf(evalRun.results.results) : [];
  const failedTotal =
    evalRun && !evalStale ? failedCaseCount(evalRun.results.results) : 0;
  const failuresKey = failuresKeyOf(failedCases);

  const currentOptimizeKey = optimizeKeyOf({
    prompt: draft,
    providerId: activeProviderId,
    instructions,
    caseSplit: splitActive
      ? { holdoutShare: DEFAULT_HOLDOUT_SHARE, holdoutIds: holdoutCaseIds }
      : null,
    caseRowsKey,
    techniques: selectedTechniques,
  });
  const optimizeResult = optimizeRun?.result ?? null;
  const optimizeStale =
    optimizeRun !== null &&
    !isOptimizeCurrent(optimizeRun.request, {
      key: currentOptimizeKey,
      failuresKey,
    });
  const suggestion = optimizeResult?.suggested_prompt ?? "";

  // Compared against the prompt the optimizer was given, not the live draft: a
  // changed draft is stale and Accept is already blocked
  const placeholderNote = useMemo(
    () =>
      optimizeRun
        ? bindingChangeNote(
            comparePromptBindings(optimizeRun.request.prompt, suggestion),
          )
        : null,
    [optimizeRun, suggestion],
  );

  // Off a split the suggestion reuses the current run's cases, so both sides match
  const suggestedCaseIds = splitActive
    ? evalCaseIds
    : evalRun && !evalStale
      ? evalRun.results.provenance.evaluated_case_ids
      : null;
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

  /** Captured in the same expression that builds the request: resolving either field
   *  in a callback would read whatever the form holds when the run returns */
  const runSnapshotOf = (leaky: boolean): RunSnapshot => ({
    leaky,
    providerFallback,
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
    mutationFn: async (vars: OptimizeRequest) => {
      setError(null);
      const result = await optimizePrompt(workflowId, nodeId, promptField, {
        provider_id: vars.providerId,
        current_prompt: vars.prompt,
        instructions: vars.instructions || undefined,
        failed_cases: vars.failedCases?.map((c) => ({
          case_id: c.caseId,
          actual: c.actual,
          failed_metrics: c.failedMetrics,
        })),
        case_split: vars.caseSplit
          ? { holdout_case_ids: [...vars.caseSplit.holdoutIds] }
          : undefined,
        techniques: vars.techniques,
      });
      if (!result)
        throw new Error("Server returned empty response — check permissions.");
      return result;
    },
    onSuccess: (data, vars) => {
      acceptTokenRef.current += 1;
      setOptimizeRun({ request: vars, result: data });
      // A new suggestion invalidates the old one's scores; the baseline is keyed to
      // the current prompt and stays valid
      setSuggestedEvalRun(null);
      setHoldoutRun((prev) =>
        prev ? { ...prev, suggestion: null, error: null } : prev,
      );
    },
    onError: (err) => showError("optimize prompt", err),
  });

  const evalOptimizedMutation = useMutation({
    mutationFn: (
      vars: EvalRequest & { token: number; snapshot: RunSnapshot },
    ) => runEvaluation(vars),
    onSuccess: (data, vars) => {
      if (vars.token !== acceptTokenRef.current) return;
      setSuggestedEvalRun({
        key: vars.key,
        caseIds: vars.caseIds,
        results: data,
        ...vars.snapshot,
      });
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

  const acceptOptimizedMutation = useMutation({
    mutationFn: async (vars: AcceptPayload) => {
      setError(null);
      const created = await createPromptVersion(
        workflowId,
        nodeId,
        promptField,
        {
          content: vars.content,
          label: "Optimized prompt",
        },
      );
      if (!created) throw new Error("Not allowed to save a version");
      return created;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: promptHistoryKey(workflowId, nodeId, promptField),
      });
    },
    onError: (err) => showError("accept optimized prompt", err),
  });

  const runInputs: EvalInputs = {
    content: draft,
    contentNoun: "prompt",
    providerStatus,
    providerId: activeProviderId,
    techniqueCount: selectedTechniques.length,
    phrasesProblem: phrasesIssue,
  };

  const evaluate = evaluateGate(historyState, casesState, caps, runInputs);
  const optimize = optimizeGate(historyState, caps, {
    ...runInputs,
    instructions,
  });
  const evaluateSuggested = evaluateGate(historyState, casesState, caps, {
    ...runInputs,
    content: suggestion,
    contentNoun: "suggested prompt",
    stale: optimizeStale,
  });
  const accept = acceptGate(historyState, caps, suggestion, {
    pending: acceptOptimizedMutation.isPending,
    stale: optimizeStale,
  });

  const suggestedPending =
    evalOptimizedMutation.isPending || holdoutMutation.isPending;
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

  /** Runs the hold-out under the current prompt, then under the suggestion */
  const startPairedRun = () => {
    if (!pairedRequests) return;
    const token = acceptTokenRef.current;
    // The hold-out half is the non-leaky one, so the note never reaches a comparison
    const snapshot = runSnapshotOf(false);
    const { baseline, suggestion: suggested } = pairedRequests;
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
    if (splitActive) {
      startPairedRun();
      return;
    }
    evalOptimizedMutation.mutate({
      ...buildEvalRequest(suggestion, suggestedCaseIds),
      token: acceptTokenRef.current,
      snapshot: runSnapshotOf(true),
    });
  };

  // Save, then apply (only if draft/suggestion haven't changed)
  // Callbacks drop on unmount, so closing mid-save is safe
  const handleAcceptOptimized = () => {
    if (!optimizeResult || !accept.enabled) return;
    const token = ++acceptTokenRef.current;
    acceptOptimizedMutation.mutate(acceptPayloadOf(suggestion, draft, token), {
      onSuccess: (created, vars) => {
        const stillCurrent = vars.token === acceptTokenRef.current;
        if (
          stillCurrent &&
          draftUnchangedSince(vars.draftAtSubmit, latestDraftRef.current)
        ) {
          onAccepted(created.content);
          setSuccessMessage(
            `Saved as v${created.version_number} and applied to the draft`,
          );
        } else {
          setSuccessMessage(
            `Saved as v${created.version_number}; the draft was left as it is`,
          );
        }
        if (stillCurrent) {
          setOptimizeRun(null);
          setSuggestedEvalRun(null);
          setHoldoutRun(null);
        }
      },
    });
  };

  const runOptimize = () => {
    if (!optimize.enabled) return;
    const caseSplit = splitActive
      ? { holdoutShare: DEFAULT_HOLDOUT_SHARE, holdoutIds: holdoutCaseIds }
      : null;
    optimizeMutation.mutate({
      key: currentOptimizeKey,
      prompt: draft,
      providerId: activeProviderId,
      instructions,
      failedCases: failedCases.length > 0 ? failedCases : undefined,
      sourceFailuresKey: failuresKey,
      caseSplit,
      techniques: selectedTechniques,
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
    setHoldoutRun(null);
  };

  return {
    error,
    successMessage,

    providers,
    activeProviderId,
    setSelectedProviderId,
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
    failedIncluded: failedCases.length,
    failedTotal,
    optimizeResult,
    optimizeStale,
    suggestion,
    placeholderNote,
    suggestedEvalRun,
    suggestedStale,
    pairedRun,
    pairedStale,
    holdoutError,
    hasRuns,

    evaluate: {
      ...evaluate,
      run: () => {
        if (!evaluate.enabled) return;
        evalMutation.mutate({
          ...buildEvalRequest(draft, evalCaseIds),
          snapshot: runSnapshotOf(splitActive),
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
      pending: suggestedPending,
    },
    accept: {
      ...accept,
      run: handleAcceptOptimized,
      pending: acceptOptimizedMutation.isPending,
    },
    retryHoldout,
    dismiss,
  };
};
