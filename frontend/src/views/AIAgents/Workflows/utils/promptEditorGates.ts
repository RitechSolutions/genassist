import type { PromptEditorCapabilities } from "./promptEditorCapabilities";

/** One decision per control; button and handler stay in sync */
export interface Gate {
  enabled: boolean;
  reason: string | null;
}

/** The history query projected to what the gates need */
export interface HistoryState {
  status: "pending" | "error" | "forbidden" | "ready";
  nodeMissing: boolean;
  inlineCheckSupported: boolean;
  unsupportedReason: string | null;
  goldSuiteId: string | null;
}

export interface CasesState {
  status: "idle" | "pending" | "error" | "forbidden" | "success";
  count: number;
}

/** Run inputs formatted to match gate checks */
export interface RunInputs {
  content: string;
  /** Content name in blocking reason ("prompt" or "suggested prompt") */
  contentNoun: string;
  providerStatus: "pending" | "error" | "empty" | "ready";
  /** Empty when nothing is selected or the selection is no longer active */
  providerId: string;
}

export interface EvalInputs extends RunInputs {
  techniqueCount: number;
}

export const MAX_PROMPT_LENGTH = 200_000;

/** Code points, matching the backend bound; JS `.length` double-counts astral characters */
export const promptLength = (content: string): number =>
  Array.from(content).length;

/** Shared with the dialog banner, which reports the same failures */
export const HISTORY_ERROR_REASON = "Prompt history could not be loaded.";
export const HISTORY_FORBIDDEN_REASON =
  "You don't have permission to view prompt history.";

const NODE_MISSING_REASON =
  "This node isn't in the saved workflow. Save the workflow first.";

const OPEN: Gate = { enabled: true, reason: null };

const blocked = (reason: string): Gate => ({ enabled: false, reason });

/** Shared conditions: capability, loaded history, live node */
const contextGate = (
  history: HistoryState,
  hasCapability: boolean,
  missingCapabilityReason: string,
): Gate | null => {
  if (!hasCapability) return blocked(missingCapabilityReason);
  if (history.status === "pending") return blocked("Loading prompt history…");
  if (history.status === "forbidden") return blocked(HISTORY_FORBIDDEN_REASON);
  if (history.status === "error") return blocked(HISTORY_ERROR_REASON);
  if (history.nodeMissing) return blocked(NODE_MISSING_REASON);
  return null;
};

const blankGate = (content: string, noun: string): Gate | null =>
  content.trim() ? null : blocked(`The ${noun} is empty.`);

/** POST body bounds prevent invalid requests. Version writes only — the
 *  evaluate and optimize endpoints set no maximum */
const versionBodyGate = (content: string, noun: string): Gate | null => {
  const blank = blankGate(content, noun);
  if (blank) return blank;
  // Quick check first; code-point walk only if already over
  if (
    content.length > MAX_PROMPT_LENGTH &&
    promptLength(content) > MAX_PROMPT_LENGTH
  )
    return blocked(
      `The ${noun} is longer than ${MAX_PROMPT_LENGTH.toLocaleString()} characters.`,
    );
  return null;
};

/** A run needs a provider the user can actually see selected */
const providerGate = (run: RunInputs): Gate | null => {
  if (run.providerStatus === "pending")
    return blocked("Loading LLM providers…");
  if (run.providerStatus === "error")
    return blocked("LLM providers could not be loaded.");
  if (run.providerStatus === "empty")
    return blocked("No active LLM providers are available.");
  if (!run.providerId) return blocked("Select an LLM provider.");
  return null;
};

/** Isolated check only works for system-role fields */
const inlineCheckGate = (history: HistoryState): Gate | null =>
  history.inlineCheckSupported
    ? null
    : blocked(
        history.unsupportedReason ??
          "The isolated check is not supported for this field.",
      );

export const saveGate = (
  history: HistoryState,
  caps: PromptEditorCapabilities,
  draft: string,
): Gate => {
  const context = contextGate(
    history,
    caps.canEditPrompt,
    "Saving versions needs the update:evaluation permission.",
  );
  if (context) return context;
  return versionBodyGate(draft, "prompt") ?? OPEN;
};

export const evaluateGate = (
  history: HistoryState,
  cases: CasesState,
  caps: PromptEditorCapabilities,
  run: EvalInputs,
): Gate => {
  const context = contextGate(
    history,
    caps.canEvaluate,
    "Running evaluations needs the run:evaluation permission.",
  );
  if (context) return context;
  const inline = inlineCheckGate(history);
  if (inline) return inline;
  if (!history.goldSuiteId)
    return blocked("Link a gold dataset before running an evaluation.");
  if (cases.status === "pending") return blocked("Loading cases…");
  if (cases.status === "success" && cases.count === 0)
    return blocked("The gold dataset has no cases yet.");
  const provider = providerGate(run);
  if (provider) return provider;
  if (run.techniqueCount === 0)
    return blocked("Select at least one matching technique.");
  return blankGate(run.content, run.contentNoun) ?? OPEN;
};

export const optimizeGate = (
  history: HistoryState,
  caps: PromptEditorCapabilities,
  run: RunInputs,
): Gate => {
  const context = contextGate(
    history,
    caps.canOptimize,
    "Optimizing needs the update:evaluation permission.",
  );
  if (context) return context;
  const inline = inlineCheckGate(history);
  if (inline) return inline;
  return providerGate(run) ?? blankGate(run.content, run.contentNoun) ?? OPEN;
};

/**
 * Accept saves and applies the suggestion (follows save contract)
 * Not gated on inline check—suggestions only appear where Optimize is allowed
 */
export const acceptGate = (
  history: HistoryState,
  caps: PromptEditorCapabilities,
  pending: boolean,
  suggestion: string,
): Gate => {
  const context = contextGate(
    history,
    caps.canEditPrompt,
    "Saving versions needs the update:evaluation permission.",
  );
  if (context) return context;
  if (pending) return blocked("A save is already running.");
  return versionBodyGate(suggestion, "suggested prompt") ?? OPEN;
};
