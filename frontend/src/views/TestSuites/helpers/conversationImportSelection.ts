import type {
  ImportFromConversationsResult,
  ImportedConversationResult,
} from "@/interfaces/testSuite.interface";

/** Most conversations one import can carry. Mirrors the API's own cap, which
 *  rejects a longer list outright. */
export const MAX_IMPORT_CONVERSATIONS = 100;

/** Add or remove one conversation, returning a fresh Set for React state.
 *
 * Selecting stops at the cap, so the picker can never build a batch the API
 * would reject.
 */
export const toggleSelected = (
  selected: Set<string>,
  conversationId: string,
  limit = MAX_IMPORT_CONVERSATIONS,
): Set<string> => {
  if (selected.has(conversationId)) {
    const next = new Set(selected);
    next.delete(conversationId);
    return next;
  }
  if (selected.size >= limit) return selected;
  return new Set(selected).add(conversationId);
};

/** True when every one of these conversations is already selected. */
export const areAllSelected = (
  ids: string[],
  selected: Set<string>,
): boolean => ids.length > 0 && ids.every((id) => selected.has(id));

/**
 * Select or clear a group of conversations, leaving the rest of the picks alone.
 *
 * The list loads in batches, so this speaks only for what is currently loaded.
 * Picks made before a filter changed survive, which is what countHiddenSelections
 * exists to report.
 */
export const setManySelected = (
  selected: Set<string>,
  ids: string[],
  isSelected: boolean,
  limit = MAX_IMPORT_CONVERSATIONS,
): Set<string> => {
  const next = new Set(selected);
  for (const id of ids) {
    if (!isSelected) {
      next.delete(id);
      continue;
    }
    // Fills up to the cap rather than refusing the whole group.
    if (next.size >= limit && !next.has(id)) break;
    next.add(id);
  }
  return next;
};

/** How many picks are not in the list the user is looking at.
 *
 * Filtering and searching reload the list, so a selection can include
 * conversations that are no longer on screen. The count says so plainly rather
 * than letting the total imply everything is visible.
 */
export const countHiddenSelections = (
  selected: Set<string>,
  visibleIds: string[],
): number => {
  const visible = new Set(visibleIds);
  let hidden = 0;
  for (const id of selected) if (!visible.has(id)) hidden += 1;
  return hidden;
};

export interface ImportPlan {
  total: number;
  /** Conversations not in the dataset yet. */
  added: number;
  /** Conversations already in the dataset, whose turns get replaced. */
  refreshed: number;
  /** Turns the replacement destroys. */
  replacedTurns: number;
}

/**
 * Split a selection into first-time imports and re-imports.
 *
 * A re-import replaces that conversation's existing turns, so the confirm step
 * has to say how many turns are about to be thrown away.
 */
export const planImport = (
  selectedIds: string[],
  importedTurnsByConversation: Map<string, number>,
): ImportPlan => {
  let refreshed = 0;
  let replacedTurns = 0;
  for (const id of selectedIds) {
    const turns = importedTurnsByConversation.get(id);
    if (!turns) continue;
    refreshed += 1;
    replacedTurns += turns;
  }
  return {
    total: selectedIds.length,
    added: selectedIds.length - refreshed,
    refreshed,
    replacedTurns,
  };
};

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

/** The confirm dialog's body copy for a selection. */
export const describeImportPlan = (plan: ImportPlan, datasetName: string): string => {
  const target = `"${datasetName}"`;
  if (plan.refreshed === 0) {
    return `This adds the turns of ${plural(plan.total, "conversation")} to ${target}, keeping everything already in the dataset.`;
  }
  const replaceClause = `${plural(plan.replacedTurns, "turn")} across ${plural(plan.refreshed, "conversation")} already in this dataset will be replaced from the transcript. Any edits or turns you added to them are lost, and past evaluation results stop matching them.`;
  if (plan.added === 0) return replaceClause;
  return `This adds ${plural(plan.added, "conversation")} to ${target}. ${replaceClause}`;
};

export interface ImportOutcome {
  /** True when at least one conversation made it into the dataset. */
  anySucceeded: boolean;
  /** Success toast, or null when nothing was imported. */
  successMessage: string | null;
  /** Error toast, or null when everything succeeded. */
  errorMessage: string | null;
  failures: ImportedConversationResult[];
}

/** Turn a batch response into the toasts the user sees. */
export const summarizeImportOutcome = (
  result: ImportFromConversationsResult,
): ImportOutcome => {
  const succeeded = result.imported + result.replaced;
  const turns = result.cases.length;
  const failures = result.results.filter((entry) => entry.status === "failed");

  let successMessage: string | null = null;
  if (succeeded > 0) {
    const what =
      result.replaced === 0
        ? `Imported ${plural(result.imported, "conversation")}`
        : result.imported === 0
          ? `Replaced ${plural(result.replaced, "conversation")}`
          : `Imported ${plural(result.imported, "conversation")} and replaced ${result.replaced}`;
    successMessage = `${what} (${plural(turns, "turn")}).`;
  }

  let errorMessage: string | null = null;
  if (failures.length > 0) {
    // One failure names its reason. Several would make an unreadable toast, so
    // the count carries it and each row keeps its own reason.
    errorMessage =
      failures.length === 1
        ? `1 conversation could not be imported. ${failures[0].detail ?? ""}`.trim()
        : `${failures.length} conversations could not be imported.`;
  }

  return {
    anySucceeded: succeeded > 0,
    successMessage,
    errorMessage,
    failures,
  };
};
