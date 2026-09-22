import React, { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { AlertCircle, Database, Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { Skeleton } from "@/components/skeleton";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  addConversationToDatasets,
  listDatasetsForConversation,
} from "@/services/testSuites";
import {
  MAX_CONVERSATION_DATASETS,
  datasetTurnsById,
  describeDatasetAddConfirm,
  describeDatasetAddPlan,
  describeDatasetMembership,
  filterDatasets,
  planDatasetAdd,
  selectAllDatasets,
  summarizeDatasetAddOutcome,
  toggleDataset,
} from "../helpers/conversationDatasets";
import {
  areAllSelected,
  countHiddenSelections,
} from "../helpers/conversationImportSelection";
import type { ConversationDataset } from "@/interfaces/testSuite.interface";

/** Stands in for a row while the datasets load, in the same shape. */
const DatasetRowSkeleton = () => (
  <div className="border rounded p-3 flex items-center gap-3">
    <Skeleton className="h-4 w-4 rounded-sm" />
    <div className="min-w-0 flex-1 space-y-1.5">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-3 w-48" />
    </div>
  </div>
);

interface AddToDatasetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The conversation being added. Nothing loads until it is set. */
  conversationId: string | null;
  /** Shown in the title, e.g. "Chat #a3f2". */
  conversationLabel?: string;
}

/** Adds one conversation to any number of datasets: the mirror of
 *  ImportFromConversationDialog, which picks conversations for one dataset.
 *  A dataset already holding it has its copy replaced, not duplicated. */
export const AddToDatasetDialog: React.FC<AddToDatasetDialogProps> = ({
  open,
  onOpenChange,
  conversationId,
  conversationLabel,
}) => {
  const [datasets, setDatasets] = useState<ConversationDataset[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  // apiRequest resolves to null only on a 403, so this says "refused", not "failed".
  const [isForbidden, setIsForbidden] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  // Dataset id -> why its last add failed. Cleared when a run starts.
  const [failureById, setFailureById] = useState<Map<string, string>>(new Map());
  // Set before the first await: the confirm button is a Radix close and fires
  // onOpenChange in the same click, before any state has re-rendered.
  const isSavingRef = useRef(false);

  // The picker hides behind the confirm rather than closing, so the selection
  // and the search survive a cancel.
  const isPickerVisible = open && !isConfirmOpen;

  const turnsByDataset = datasetTurnsById(datasets);
  const nameById = new Map(datasets.map((d) => [d.suite_id, d.name]));
  const selectedList = [...selectedIds];
  const plan = planDatasetAdd(selectedList, turnsByDataset);
  const confirmCopy = describeDatasetAddConfirm(plan);
  const isAtSelectionCap = selectedIds.size >= MAX_CONVERSATION_DATASETS;
  const visibleDatasets = filterDatasets(datasets, searchQuery);
  const visibleIds = visibleDatasets.map((dataset) => dataset.suite_id);
  const hiddenSelections = countHiddenSelections(selectedIds, visibleIds);

  const loadDatasets = useCallback(async (id: string) => {
    setIsLoading(true);
    setLoadError(false);
    try {
      // apiRequest resolves to null on a 403 rather than throwing, so a caller
      // without dataset access lands here, not in the catch.
      const result = await listDatasetsForConversation(id);
      setIsForbidden(result === null);
      setDatasets(result ?? []);
    } catch {
      // Without this the dialog would sit on its skeleton forever.
      setIsForbidden(false);
      setDatasets([]);
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Reset and reload each time the host opens the picker.
  useEffect(() => {
    if (!open || !conversationId) return;
    setSearchQuery("");
    setSelectedIds(new Set());
    setFailureById(new Map());
    loadDatasets(conversationId);
  }, [open, conversationId, loadDatasets]);

  const handleConfirm = async () => {
    if (!conversationId || selectedList.length === 0) return;
    isSavingRef.current = true;
    setIsSaving(true);
    setFailureById(new Map());
    try {
      const result = await addConversationToDatasets(conversationId, selectedList);
      if (!result) throw new Error("The datasets were not updated.");

      const outcome = summarizeDatasetAddOutcome(result, nameById);
      if (outcome.successMessage) toast.success(outcome.successMessage);
      if (outcome.errorMessage) toast.error(outcome.errorMessage);

      if (outcome.anySucceeded) await loadDatasets(conversationId);

      // Only what failed stays selected, so a retry repeats just those and the
      // reason sits on the row the user has to look at anyway.
      const failed = new Map(
        outcome.failures.map((entry) => [
          entry.suite_id,
          entry.detail ?? "Could not be updated.",
        ]),
      );
      setFailureById(failed);
      setSelectedIds(new Set(failed.keys()));
      setIsConfirmOpen(false);
      if (failed.size === 0) onOpenChange(false);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(
        axiosErr?.response?.data?.error ?? "Failed to update the datasets.",
      );
      setIsConfirmOpen(false);
    } finally {
      isSavingRef.current = false;
      setIsSaving(false);
    }
  };

  return (
    <>
      <Dialog open={isPickerVisible} onOpenChange={onOpenChange}>
        {/* Raised above the conversation dialog this opens from, so the scrim
            dims it instead of sliding under it. */}
        <DialogContent
          overlayClassName="z-[1310]"
          className="sm:max-w-[560px] z-[1320] p-0 overflow-hidden flex flex-col max-h-[80vh]"
        >
          <DialogHeader className="p-6 pb-4 shrink-0">
            <DialogTitle>
              Add {conversationLabel ?? "this conversation"} to a dataset
            </DialogTitle>
          </DialogHeader>

          {/* Search stays out of the way until the list is long enough to need it. */}
          {!isLoading && datasets.length > 5 && (
            <div className="px-6 pb-2 shrink-0">
              <Input
                placeholder="Search datasets"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          )}

          {/* Select-all speaks for the search results, not the whole list, so
              picks it cannot see are reported by the count instead. */}
          {!isLoading && !isForbidden && !loadError && datasets.length > 0 && (
            <div className="px-6 py-2 shrink-0 flex items-center justify-between gap-3 border-b">
              {/* A pair rather than one tri-state box: the checkbox has no
                  indeterminate mark, so a half-selected list would look
                  identical to a full one. */}
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  disabled={
                    visibleIds.length === 0 ||
                    areAllSelected(visibleIds, selectedIds) ||
                    isAtSelectionCap
                  }
                  onClick={() =>
                    setSelectedIds((prev) => selectAllDatasets(prev, visibleIds))
                  }
                >
                  Select all
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  disabled={selectedIds.size === 0}
                  onClick={() => setSelectedIds(new Set())}
                >
                  Clear all
                </Button>
              </div>
              {selectedIds.size > 0 && (
                <span className="text-xs text-right leading-tight">
                  <span className="font-medium text-foreground">
                    {selectedIds.size} selected
                  </span>
                  {/* Searching narrows the list, so some picks can be off
                      screen. Saying so beats a total that implies they are all
                      here. */}
                  {hiddenSelections > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {hiddenSelections} not shown
                    </span>
                  )}
                  {isAtSelectionCap && (
                    <span className="text-muted-foreground">
                      {" "}
                      ({MAX_CONVERSATION_DATASETS} maximum)
                    </span>
                  )}
                  {/* Says it here too, because a dataset being replaced may be
                      filtered out of view. */}
                  {plan.refreshed > 0 && (
                    <span className="block text-amber-700">
                      {plan.refreshed} will be replaced
                    </span>
                  )}
                </span>
              )}
            </div>
          )}

          <div className="flex-1 min-h-0 overflow-y-auto px-6">
            {isLoading ? (
              <div className="space-y-2 py-2" aria-busy="true">
                {Array.from({ length: 4 }, (_, i) => (
                  <DatasetRowSkeleton key={i} />
                ))}
              </div>
            ) : loadError ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <AlertCircle className="h-7 w-7 text-muted-foreground" />
                <p className="text-sm font-medium">Could not load datasets</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => conversationId && loadDatasets(conversationId)}
                >
                  Try again
                </Button>
              </div>
            ) : isForbidden ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <Lock className="h-7 w-7 text-muted-foreground" />
                <p className="text-sm font-medium">No access to datasets</p>
                <p className="text-sm text-muted-foreground">
                  You don't have permission to view or change evaluation datasets.
                </p>
              </div>
            ) : datasets.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <Database className="h-7 w-7 text-muted-foreground" />
                <p className="text-sm font-medium">No datasets yet</p>
                <p className="text-sm text-muted-foreground">
                  Create one first, then come back to add this conversation.
                </p>
                <Link
                  to="/tests/datasets"
                  className="text-sm font-medium text-primary underline-offset-4 hover:underline"
                >
                  Go to Datasets
                </Link>
              </div>
            ) : visibleDatasets.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4">
                No datasets match "{searchQuery}".
              </div>
            ) : (
              <div className="space-y-2 py-2">
                {visibleDatasets.map((dataset) => {
                  const isSelected = selectedIds.has(dataset.suite_id);
                  const isSelectDisabled = isAtSelectionCap && !isSelected;
                  const failure = failureById.get(dataset.suite_id);
                  return (
                    <div
                      key={dataset.suite_id}
                      className={`border rounded overflow-hidden ${
                        failure
                          ? "border-destructive/50"
                          : isSelected
                            ? "border-primary ring-1 ring-primary/30"
                            : dataset.turns
                              ? "border-blue-300 bg-blue-50/40"
                              : ""
                      }`}
                    >
                      {/* The label carries the click, so the whole row selects
                          and the checkbox is only the state it is in. */}
                      <label
                        className={`p-3 flex items-center gap-3 ${
                          isSelectDisabled ? "cursor-not-allowed" : "cursor-pointer"
                        }`}
                      >
                        <Checkbox
                          checked={isSelected}
                          disabled={isSelectDisabled}
                          onCheckedChange={() =>
                            setSelectedIds((prev) =>
                              toggleDataset(prev, dataset.suite_id),
                            )
                          }
                          aria-label={`Add to ${dataset.name}`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-foreground truncate">
                            {dataset.name}
                          </p>
                          {dataset.description && (
                            <p className="text-xs text-muted-foreground mt-0.5 truncate">
                              {dataset.description}
                            </p>
                          )}
                        </div>
                        {/* Reads as state until it is picked, then as the
                            consequence of picking it. */}
                        {/* No turn count: the number only matters once you
                            commit, and the confirm step gives the exact one.
                            The tooltip carries it for anyone who wants it. */}
                        {dataset.turns > 0 ? (
                          isSelected ? (
                            <span
                              className="shrink-0 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                              title={describeDatasetMembership(dataset)}
                            >
                              Replaces existing
                            </span>
                          ) : (
                            <span
                              className="shrink-0 rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700"
                              title={describeDatasetMembership(dataset)}
                            >
                              In dataset
                            </span>
                          )
                        ) : null}
                      </label>

                      {failure && (
                        <div className="flex items-start gap-1.5 border-t border-destructive/30 bg-destructive/5 px-3 py-1.5">
                          <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-px" />
                          <p className="text-xs text-destructive">{failure}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* sm:justify-between is required: DialogFooter ships sm:justify-end,
              which outranks a plain justify-between above 640px. */}
          <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between sm:justify-between">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {datasets.length} dataset{datasets.length === 1 ? "" : "s"}
            </span>
            <Button
              size="sm"
              disabled={selectedIds.size === 0 || isSaving}
              onClick={() => setIsConfirmOpen(true)}
            >
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm add — appends this conversation's turns to each picked dataset */}
      <ConfirmDialog
        isOpen={isConfirmOpen}
        onOpenChange={(next) => {
          // A cancel drops back to the picker with the selection intact. The ref,
          // not the state, is what says a save is running.
          if (!next && !isSavingRef.current) setIsConfirmOpen(false);
        }}
        onConfirm={handleConfirm}
        isInProgress={isSaving}
        title={confirmCopy.title}
        description={describeDatasetAddPlan(plan)}
        primaryButtonText={confirmCopy.primaryButtonText}
      />
    </>
  );
};

export default AddToDatasetDialog;
