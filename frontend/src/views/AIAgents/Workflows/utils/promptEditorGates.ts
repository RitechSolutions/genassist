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

export const MAX_PROMPT_LENGTH = 200_000;

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
  if (history.status === "forbidden")
    return blocked("You don't have permission to view prompt history.");
  if (history.status === "error")
    return blocked("Prompt history could not be loaded.");
  if (history.nodeMissing) return blocked(NODE_MISSING_REASON);
  return null;
};

/** POST body bounds prevent invalid requests */
const contentGate = (content: string, noun: string): Gate | null => {
  if (!content.trim()) return blocked(`The ${noun} is empty.`);
  if (content.length > MAX_PROMPT_LENGTH)
    return blocked(
      `The ${noun} is longer than ${MAX_PROMPT_LENGTH.toLocaleString()} characters.`,
    );
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
  return contentGate(draft, "prompt") ?? OPEN;
};

export const evaluateGate = (
  history: HistoryState,
  cases: CasesState,
  caps: PromptEditorCapabilities,
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
  return OPEN;
};

export const optimizeGate = (
  history: HistoryState,
  caps: PromptEditorCapabilities,
): Gate => {
  const context = contextGate(
    history,
    caps.canOptimize,
    "Optimizing needs the update:evaluation permission.",
  );
  if (context) return context;
  return inlineCheckGate(history) ?? OPEN;
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
  return contentGate(suggestion, "suggested prompt") ?? OPEN;
};
