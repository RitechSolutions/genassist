import React, { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { Checkbox } from "@/components/checkbox";
import { Skeleton } from "@/components/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  importCasesFromConversations,
  listTestCases,
} from "@/services/testSuites";
import { fetchConversationById, fetchTranscripts } from "@/services/transcripts";
import { TranscriptThread } from "@/views/Transcripts/components/TranscriptThread";
import { transformTranscript } from "@/views/Transcripts/helpers/transformers";
import { IMPORTED_TAG } from "../helpers/datasetConversations";
import {
  MAX_IMPORT_CONVERSATIONS,
  areAllSelected,
  countHiddenSelections,
  describeImportPlan,
  planImport,
  setManySelected,
  summarizeImportOutcome,
  toggleSelected,
} from "../helpers/conversationImportSelection";
import { getWorkflowsMinimal } from "@/services/workflows";
import type { TestCase, TestSuite } from "@/interfaces/testSuite.interface";
import type {
  BackendTranscript,
  Transcript,
} from "@/interfaces/transcript.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { groupWorkflowVersions } from "../helpers/workflowVersions";

const CONV_BATCH_SIZE = 20;

/** Stands in for a row while the first batch loads, in the same shape, so the
 *  list does not jump when the real conversations arrive. */
const ConversationRowSkeleton = () => (
  <div className="border rounded p-3 flex items-center gap-3">
    <Skeleton className="h-4 w-4 rounded-sm" />
    <div className="min-w-0 flex-1 space-y-1.5">
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-3 w-52" />
    </div>
    <Skeleton className="h-7 w-14 rounded-md" />
  </div>
);

/** One option per agent rather than per workflow version.
 *
 * Conversations carry no version stamp — they reach a workflow only through
 * their agent — so agent_id is the only filter the API can honour. Versions
 * without an agent can never match a conversation and are dropped.
 */
const agentFilterOptions = (workflows: WorkflowMinimal[]) =>
  groupWorkflowVersions(workflows)
    .map((group) => ({
      agentId: group.versions[0]?.agent_id,
      label: group.name,
    }))
    .filter(
      (option): option is { agentId: string; label: string } => !!option.agentId,
    );

interface ImportFromConversationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The dataset being imported into. Nothing loads until it is set. */
  suite: TestSuite | null;
  /** Fires after an import with the dataset's refreshed turns. */
  onDatasetChanged?: (suiteId: string, cases: TestCase[]) => void;
}

export const ImportFromConversationDialog: React.FC<
  ImportFromConversationDialogProps
> = ({ open, onOpenChange, suite, onDatasetChanged }) => {
  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [convIdSuffix, setConvIdSuffix] = useState("");
  // Every batch loaded so far, not just the latest one.
  const [conversations, setConversations] = useState<BackendTranscript[]>([]);
  const [convTotal, setConvTotal] = useState(0);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  // Held as a Transcript, not raw messages, because the preview renders through
  // the same TranscriptThread the Transcripts and Reported Feedback views use.
  const [expandedTranscript, setExpandedTranscript] = useState<Transcript | null>(
    null,
  );
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  // Picks survive paging and filtering, so a batch can be built across pages.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  // Conversation id -> why its last import failed. Cleared when a run starts.
  const [failureById, setFailureById] = useState<Map<string, string>>(new Map());
  // Conversation id -> number of turns already imported into this dataset.
  const [importedConversations, setImportedConversations] = useState<
    Map<string, number>
  >(new Map());
  const idSuffixDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Set before the first await, because the confirm button is a Radix close and
  // fires onOpenChange in the same click, before any state has re-rendered.
  const isImportingRef = useRef(false);
  // Ticket for the newest list request, so slow replies cannot land late.
  const conversationRequestRef = useRef(0);

  const suiteId = suite?.id;

  // The picker hides behind the confirm rather than closing, so `open` never
  // flips during the confirm round trip and the filter, page, expansion and
  // selection all survive a cancel.
  const isPickerVisible = open && !isConfirmOpen;

  const loadedIds = conversations.map((conv) => conv.id);
  const selectedList = [...selectedIds];
  const plan = planImport(selectedList, importedConversations);
  const isAtSelectionCap = selectedIds.size >= MAX_IMPORT_CONVERSATIONS;
  const hiddenSelections = countHiddenSelections(selectedIds, loadedIds);
  const hasMore = conversations.length < convTotal;

  /** Loads the first batch, or appends the next one when `skip` is past zero.
   *
   * Every call takes a ticket. A response only lands if no newer call has
   * started since, or a slow reply would append conversations the current
   * filter excludes, and they could then be selected and imported.
   */
  const loadConversations = useCallback(
    async (agentId: string, idSuffix: string, skip = 0) => {
      const isAppend = skip > 0;
      const requestId = ++conversationRequestRef.current;
      if (isAppend) setIsLoadingMore(true);
      else setIsLoadingConversations(true);

      const result = await fetchTranscripts({
        skip,
        limit: CONV_BATCH_SIZE,
        agent_id: agentId || undefined,
        id_suffix: idSuffix || undefined,
      });

      // A newer request is already in flight; it owns the list now.
      if (requestId !== conversationRequestRef.current) return;

      setConversations((prev) =>
        isAppend ? [...prev, ...result.items] : result.items,
      );
      setConvTotal(result.total);
      setIsLoadingMore(false);
      setIsLoadingConversations(false);
    },
    [],
  );

  /** Refreshes the imported-turn counts and hands the turns back to the host. */
  const loadImportedConversations = useCallback(
    async (id: string) => {
      const cases = (await listTestCases(id)) ?? [];
      const turnsByConversation = new Map<string, number>();
      for (const entry of cases) {
        // Hand-authored threads carry a generated id too, so the tag is what
        // says a real conversation was imported.
        if (!entry.tags?.includes(IMPORTED_TAG)) continue;
        const conversationId = entry.source_conversation_id;
        if (!conversationId) continue;
        turnsByConversation.set(
          conversationId,
          (turnsByConversation.get(conversationId) ?? 0) + 1,
        );
      }
      setImportedConversations(turnsByConversation);
      onDatasetChanged?.(id, cases);
    },
    [onDatasetChanged],
  );

  // Reset and reload each time the host opens the picker.
  useEffect(() => {
    if (!open || !suiteId) return;
    setSelectedAgentId("");
    setConvIdSuffix("");
    setExpandedConvId(null);
    setExpandedTranscript(null);
    setImportedConversations(new Map());
    setSelectedIds(new Set());
    setFailureById(new Map());
    loadImportedConversations(suiteId);
    getWorkflowsMinimal().then((wfs) => setWorkflows(wfs ?? []));
    loadConversations("", "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, suiteId]);

  const handleAgentFilterChange = (agentId: string) => {
    setSelectedAgentId(agentId);
    setExpandedConvId(null);
    setExpandedTranscript(null);
    loadConversations(agentId, convIdSuffix);
  };

  const handleConvIdSuffixChange = (suffix: string) => {
    setConvIdSuffix(suffix);
    if (idSuffixDebounceRef.current) clearTimeout(idSuffixDebounceRef.current);
    idSuffixDebounceRef.current = setTimeout(() => {
      setExpandedConvId(null);
      setExpandedTranscript(null);
      loadConversations(selectedAgentId, suffix);
    }, 700);
  };

  // Appends rather than replaces, so the expanded row and the picks above it
  // stay exactly where they were.
  const handleLoadMore = () =>
    loadConversations(selectedAgentId, convIdSuffix, conversations.length);

  const toggleExpandConversation = async (convId: string) => {
    if (expandedConvId === convId) {
      setExpandedConvId(null);
      setExpandedTranscript(null);
      return;
    }
    setExpandedConvId(convId);
    setExpandedTranscript(null);
    setIsLoadingMessages(true);
    const conv = await fetchConversationById(convId);
    setExpandedTranscript(conv ? transformTranscript(conv) : null);
    setIsLoadingMessages(false);
  };

  const handleConfirmImport = async () => {
    if (!suiteId || selectedList.length === 0) return;
    isImportingRef.current = true;
    setIsImporting(true);
    setFailureById(new Map());
    try {
      const result = await importCasesFromConversations(suiteId, selectedList);
      if (!result) throw new Error("The import did not complete.");

      const outcome = summarizeImportOutcome(result);
      if (outcome.successMessage) toast.success(outcome.successMessage);
      if (outcome.errorMessage) toast.error(outcome.errorMessage);

      if (outcome.anySucceeded) await loadImportedConversations(suiteId);

      // Only what failed stays selected, so a retry repeats just those and the
      // reason sits on the row the user has to look at anyway.
      const failed = new Map(
        outcome.failures.map((entry) => [
          entry.conversation_id,
          entry.detail ?? "Could not be imported.",
        ]),
      );
      setFailureById(failed);
      setSelectedIds(new Set(failed.keys()));
      setIsConfirmOpen(false);
      // A clean run is the end of the job; a partial one stays open so the
      // failures are visible next to the conversations they belong to.
      if (failed.size === 0) onOpenChange(false);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(
        axiosErr?.response?.data?.error ?? "Failed to import the conversations.",
      );
      setIsConfirmOpen(false);
    } finally {
      isImportingRef.current = false;
      setIsImporting(false);
    }
  };

  return (
    <>
      <Dialog open={isPickerVisible} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[760px] p-0 overflow-hidden flex flex-col max-h-[80vh]">
          <DialogHeader className="p-6 pb-4 shrink-0">
            <DialogTitle>Import into "{suite?.name}"</DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-2 shrink-0 flex gap-3">
            <div className="flex-1 min-w-0">
              <Label className="text-xs mb-1 block">Filter by Agent</Label>
              <Select
                value={selectedAgentId || "__all__"}
                onValueChange={(v) =>
                  handleAgentFilterChange(v === "__all__" ? "" : v)
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="All agents" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All agents</SelectItem>
                  {agentFilterOptions(workflows).map((option) => (
                    <SelectItem key={option.agentId} value={option.agentId}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-36">
              <Label className="text-xs mb-1 block">Search by ID</Label>
              <Input
                placeholder="e.g. a3f2"
                value={convIdSuffix}
                onChange={(e) => handleConvIdSuffixChange(e.target.value)}
                maxLength={36}
              />
            </div>
          </div>

          {/* Select-all speaks for this page only, because paging is server
              side. Picks made on other pages are reported by the count. It stays
              out of the way during a fetch, when `conversations` still holds the
              page the user has already navigated away from. */}
          {!isLoadingConversations && conversations.length > 0 && (
            <div className="px-6 py-2 shrink-0 flex items-center justify-between gap-3 border-b">
              {/* A pair rather than one tri-state box: the checkbox has no
                  indeterminate mark, so a half-selected page would look
                  identical to a full one. */}
              <div className="flex items-center gap-1">
                {/* Outline, not ghost: these have disabled states, and a
                    disabled ghost button reads as absent rather than
                    unavailable. Matches the View button on every row. */}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  disabled={
                    areAllSelected(loadedIds, selectedIds) || isAtSelectionCap
                  }
                  onClick={() =>
                    setSelectedIds((prev) => setManySelected(prev, loadedIds, true))
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
                  {/* Filtering reloads the list, so some picks can be off screen.
                      Saying so beats a total that implies they are all here. */}
                  {hiddenSelections > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {hiddenSelections} not shown
                    </span>
                  )}
                  {isAtSelectionCap && (
                    <span className="text-muted-foreground">
                      {" "}
                      ({MAX_IMPORT_CONVERSATIONS} maximum)
                    </span>
                  )}
                  {/* Says it here too, because the conversation being replaced
                      may be sitting on a page the user cannot see. */}
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
            {isLoadingConversations ? (
              <div className="space-y-2 py-2" aria-busy="true">
                {Array.from({ length: 5 }, (_, i) => (
                  <ConversationRowSkeleton key={i} />
                ))}
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4">
                No conversations found.
              </div>
            ) : (
              <div className="space-y-2 py-2">
                {conversations.map((conv) => {
                  const isExpanded = expandedConvId === conv.id;
                  const importedTurns = importedConversations.get(conv.id);
                  const isSelected = selectedIds.has(conv.id);
                  const isSelectDisabled = isAtSelectionCap && !isSelected;
                  const failure = failureById.get(conv.id);
                  return (
                    <div
                      key={conv.id}
                      className={`border rounded overflow-hidden ${
                        failure
                          ? "border-destructive/50"
                          : isSelected
                            ? "border-primary ring-1 ring-primary/30"
                            : importedTurns
                              ? "border-blue-300 bg-blue-50/40"
                              : ""
                      }`}
                    >
                      <div className="p-3 flex items-center gap-3">
                        {/* The label carries the click, so the whole row selects
                            and the checkbox is only the state it is in. Preview
                            stays outside it to keep the two actions apart. */}
                        <label
                          className={`flex items-center gap-3 min-w-0 flex-1 ${
                            isSelectDisabled ? "cursor-not-allowed" : "cursor-pointer"
                          }`}
                        >
                          <Checkbox
                            checked={isSelected}
                            disabled={isSelectDisabled}
                            onCheckedChange={() =>
                              setSelectedIds((prev) =>
                                toggleSelected(prev, conv.id),
                              )
                            }
                            aria-label={`Select conversation ${conv.id.slice(-6)}`}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-foreground">
                              #{conv.id.slice(-6)}
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {conv.conversation_date
                                ? new Date(
                                    conv.conversation_date,
                                  ).toLocaleDateString()
                                : "—"}{" "}
                              · {conv.word_count ?? 0} words · {conv.status}
                            </p>
                          </div>
                          {/* Reads as state until it is picked, then as the
                              consequence of picking it. Removing a conversation
                              belongs on the dataset page, where its turns show. */}
                          {/* No turn count: the number only matters once you
                              commit, and the confirm step gives the exact one. */}
                          {importedTurns ? (
                            isSelected ? (
                              <span className="shrink-0 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                                Replaces existing
                              </span>
                            ) : (
                              <span className="shrink-0 rounded-full border border-blue-300 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                                In dataset
                              </span>
                            )
                          ) : null}
                        </label>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2.5 text-xs shrink-0"
                          onClick={() => toggleExpandConversation(conv.id)}
                        >
                          {isExpanded ? "Hide" : "View"}
                        </Button>
                      </div>

                      {failure && (
                        <div className="flex items-start gap-1.5 border-t border-destructive/30 bg-destructive/5 px-3 py-1.5">
                          <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0 mt-px" />
                          <p className="text-xs text-destructive">{failure}</p>
                        </div>
                      )}

                      {/* The same thread the Transcripts and Reported Feedback
                          views render, read-only. Importing is a decision about
                          a conversation, so it should look like the conversation
                          does everywhere else. */}
                      {isExpanded && (
                        <div className="border-t bg-muted/50">
                          {/* A spinner, not skeleton bubbles: the shape of a
                              thread is not known before it arrives. */}
                          {isLoadingMessages ? (
                            <p className="flex items-center gap-2 px-3 py-3 text-xs text-muted-foreground">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Loading messages...
                            </p>
                          ) : !expandedTranscript?.messages?.length ? (
                            <p className="px-3 py-2 text-xs text-muted-foreground">
                              No messages found.
                            </p>
                          ) : (
                            <TranscriptThread
                              transcript={expandedTranscript}
                              variant="compact"
                              // The row above already states the date and status.
                              showConversationMarkers={false}
                              className="max-h-60"
                            />
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Lives at the end of the list rather than in the footer, so it
                    sits where the reading stops. Absent once everything is in. */}
                {hasMore && (
                  <div className="flex flex-col items-center gap-1 pt-1 pb-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isLoadingMore}
                      onClick={handleLoadMore}
                    >
                      {isLoadingMore ? "Loading..." : "Load more"}
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      Showing {conversations.length} of {convTotal}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* sm:justify-between is required: DialogFooter ships sm:justify-end,
              which outranks a plain justify-between above 640px and would bunch
              the count against the button. */}
          <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between sm:justify-between">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {convTotal} conversation{convTotal === 1 ? "" : "s"}
            </span>
            <Button
              size="sm"
              disabled={selectedIds.size === 0 || isImporting}
              onClick={() => setIsConfirmOpen(true)}
            >
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm import — appends the selected conversations' turns to the dataset */}
      <ConfirmDialog
        isOpen={isConfirmOpen}
        onOpenChange={(next) => {
          // A cancel drops back to the picker with the selection intact. The ref,
          // not the state, is what says an import is running: the confirm button
          // closes the dialog in the same click that starts one.
          if (!next && !isImportingRef.current) setIsConfirmOpen(false);
        }}
        onConfirm={handleConfirmImport}
        isInProgress={isImporting}
        title={
          plan.refreshed > 0
            ? `Import ${plan.total} conversation${plan.total === 1 ? "" : "s"}, replacing ${plan.refreshed}`
            : `Import ${plan.total} conversation${plan.total === 1 ? "" : "s"}`
        }
        description={describeImportPlan(plan, suite?.name ?? "")}
        primaryButtonText={plan.refreshed > 0 ? "Import and Replace" : "Add to Dataset"}
      />
    </>
  );
};

export default ImportFromConversationDialog;
