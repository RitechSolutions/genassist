import { setManySelected } from "./conversationImportSelection";
import type {
  AddConversationToDatasetsResult,
  ConversationDataset,
  ConversationDatasetResult,
} from "@/interfaces/testSuite.interface";

/** Most datasets one conversation can be added to at once. Mirrors the API cap. */
export const MAX_CONVERSATION_DATASETS = 50;

/** Permission the add-to-dataset API enforces on the write. */
export const ADD_TO_DATASET_PERMISSION = "update:workflow";

/** Offer the action only to a writer, and never for transformTranscript's
 *  "error" stub, whose id would reach the API as a malformed UUID. */
export const canAddConversationToDataset = (
  permissions: string[],
  conversationId: string | null | undefined,
): boolean => {
  if (!conversationId || conversationId === "error") return false;
  return (
    permissions.includes("*") || permissions.includes(ADD_TO_DATASET_PERMISSION)
  );
};

/** Add or remove one dataset, returning a fresh Set for React state. */
export const toggleDataset = (
  selected: Set<string>,
  suiteId: string,
  limit = MAX_CONVERSATION_DATASETS,
): Set<string> => {
  if (selected.has(suiteId)) {
    const next = new Set(selected);
    next.delete(suiteId);
    return next;
  }
  if (selected.size >= limit) return selected;
  return new Set(selected).add(suiteId);
};

/** Select every dataset in `ids`, filling up to the cap rather than refusing. */
export const selectAllDatasets = (
  selected: Set<string>,
  ids: string[],
  limit = MAX_CONVERSATION_DATASETS,
): Set<string> => setManySelected(selected, ids, true, limit);

/** Datasets whose name or description matches, case-insensitively. */
export const filterDatasets = (
  datasets: ConversationDataset[],
  query: string,
): ConversationDataset[] => {
  const needle = query.trim().toLowerCase();
  if (!needle) return datasets;
  return datasets.filter(
    (dataset) =>
      dataset.name.toLowerCase().includes(needle) ||
      (dataset.description ?? "").toLowerCase().includes(needle),
  );
};

/** Turns already held, keyed by dataset. Datasets holding none are left out. */
export const datasetTurnsById = (
  datasets: ConversationDataset[],
): Map<string, number> => {
  const turns = new Map<string, number>();
  for (const dataset of datasets) {
    if (dataset.turns > 0) turns.set(dataset.suite_id, dataset.turns);
  }
  return turns;
};

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

/** What a dataset already holds of the conversation, for the badge's tooltip. */
export const describeDatasetMembership = (
  dataset: ConversationDataset,
): string => {
  const held = `${plural(dataset.turns, "turn")} of this conversation`;
  if (!dataset.added_at) return `Already holds ${held}.`;
  const added = new Date(dataset.added_at);
  if (Number.isNaN(added.getTime())) return `Already holds ${held}.`;
  return `Already holds ${held}, added ${added.toLocaleDateString()}.`;
};

export interface DatasetAddPlan {
  total: number;
  /** Datasets the conversation is not in yet. */
  added: number;
  /** Datasets that already hold it, whose copy gets replaced. */
  refreshed: number;
  /** Turns the replacement destroys, across all of them. */
  replacedTurns: number;
}

/** Split a selection into first-time adds and re-imports, so the confirm step
 *  can say how many turns a replacement throws away. */
export const planDatasetAdd = (
  selectedIds: string[],
  turnsByDataset: Map<string, number>,
): DatasetAddPlan => {
  let refreshed = 0;
  let replacedTurns = 0;
  for (const id of selectedIds) {
    const turns = turnsByDataset.get(id);
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

/** The confirm dialog's title and primary button for a selection. */
export const describeDatasetAddConfirm = (
  plan: DatasetAddPlan,
): { title: string; primaryButtonText: string } => ({
  title:
    plan.refreshed > 0
      ? `Add to ${plural(plan.total, "dataset")}, replacing ${plan.refreshed}`
      : `Add to ${plural(plan.total, "dataset")}`,
  primaryButtonText:
    plan.refreshed > 0
      ? "Add and Replace"
      : `Add to ${plan.total === 1 ? "Dataset" : "Datasets"}`,
});

/** The confirm dialog's body copy for a selection. */
export const describeDatasetAddPlan = (plan: DatasetAddPlan): string => {
  if (plan.refreshed === 0) {
    return `This adds the conversation's turns to ${plural(plan.total, "dataset")}, keeping everything already there.`;
  }
  // Leads with the turns so "replaced" is used once, and so the sentence agrees
  // for one dataset and for many.
  const replaceClause = `${plural(plan.replacedTurns, "turn")} in ${plural(plan.refreshed, "dataset")} already holding this conversation will be replaced from the transcript. Any edits made to those turns are lost, and past evaluation results stop matching them.`;
  if (plan.added === 0) return replaceClause;
  return `This adds the conversation to ${plural(plan.added, "dataset")}. ${replaceClause}`;
};

export interface DatasetAddOutcome {
  /** True when the conversation reached at least one dataset. */
  anySucceeded: boolean;
  /** Success toast, or null when nothing was added. */
  successMessage: string | null;
  /** Error toast, or null when everything succeeded. */
  errorMessage: string | null;
  failures: ConversationDatasetResult[];
}

/** Turn an add-to-datasets response into the toasts the user sees. */
export const summarizeDatasetAddOutcome = (
  result: AddConversationToDatasetsResult,
  nameById: Map<string, string>,
): DatasetAddOutcome => {
  const succeeded = result.imported + result.replaced;
  const failures = result.results.filter((entry) => entry.status === "failed");

  let successMessage: string | null = null;
  if (succeeded > 0) {
    // One dataset is named, because that is the thing the user just changed.
    const only =
      succeeded === 1
        ? result.results.find((entry) => entry.status !== "failed")
        : undefined;
    const where = only
      ? `"${nameById.get(only.suite_id) ?? "the dataset"}"`
      : plural(succeeded, "dataset");
    successMessage =
      result.replaced === 0
        ? `Added the conversation to ${where}.`
        : result.imported === 0
          ? `Replaced the conversation in ${where}.`
          : `Added the conversation to ${plural(result.imported, "dataset")} and replaced it in ${result.replaced}.`;
  }

  let errorMessage: string | null = null;
  if (failures.length > 0) {
    errorMessage =
      failures.length === 1
        ? `"${nameById.get(failures[0].suite_id) ?? "One dataset"}" could not be updated. ${failures[0].detail ?? ""}`.trim()
        : `${failures.length} datasets could not be updated.`;
  }

  return { anySucceeded: succeeded > 0, successMessage, errorMessage, failures };
};
