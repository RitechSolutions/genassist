import React, { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/button";
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
import { importCasesFromConversation, listTestCases } from "@/services/testSuites";
import { fetchConversationById, fetchTranscripts } from "@/services/transcripts";
import { IMPORTED_TAG } from "../helpers/datasetConversations";
import { getWorkflowsMinimal } from "@/services/workflows";
import type { TestCase, TestSuite } from "@/interfaces/testSuite.interface";
import type {
  BackendTranscript,
  TranscriptEntry,
} from "@/interfaces/transcript.interface";
import type { WorkflowMinimal } from "@/interfaces/workflow.interface";
import { groupWorkflowVersions } from "../helpers/workflowVersions";

const CONV_PAGE_SIZE = 20;

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
  const [conversations, setConversations] = useState<BackendTranscript[]>([]);
  const [convPage, setConvPage] = useState(0);
  const [convTotal, setConvTotal] = useState(0);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<TranscriptEntry[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [pendingImportConv, setPendingImportConv] =
    useState<BackendTranscript | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  // Conversation id -> number of turns already imported into this dataset.
  const [importedConversations, setImportedConversations] = useState<
    Map<string, number>
  >(new Map());
  const importSucceededRef = useRef(false);
  const idSuffixDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const suiteId = suite?.id;

  // The picker hides behind a confirm rather than closing, so `open` never
  // flips during the confirm round trip and the filter, page and expansion
  // all survive a cancel.
  const isPickerVisible = open && !pendingImportConv;

  const loadConversations = useCallback(
    async (page: number, agentId: string, idSuffix: string) => {
      setIsLoadingConversations(true);
      const result = await fetchTranscripts({
        skip: page * CONV_PAGE_SIZE,
        limit: CONV_PAGE_SIZE,
        agent_id: agentId || undefined,
        id_suffix: idSuffix || undefined,
      });
      setConversations(result.items);
      setConvTotal(result.total);
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
    setConvPage(0);
    setSelectedAgentId("");
    setConvIdSuffix("");
    setExpandedConvId(null);
    setExpandedMessages([]);
    setImportedConversations(new Map());
    loadImportedConversations(suiteId);
    getWorkflowsMinimal().then((wfs) => setWorkflows(wfs ?? []));
    loadConversations(0, "", "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, suiteId]);

  const handleAgentFilterChange = (agentId: string) => {
    setSelectedAgentId(agentId);
    setConvPage(0);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(0, agentId, convIdSuffix);
  };

  const handleConvIdSuffixChange = (suffix: string) => {
    setConvIdSuffix(suffix);
    if (idSuffixDebounceRef.current) clearTimeout(idSuffixDebounceRef.current);
    idSuffixDebounceRef.current = setTimeout(() => {
      setConvPage(0);
      setExpandedConvId(null);
      setExpandedMessages([]);
      loadConversations(0, selectedAgentId, suffix);
    }, 700);
  };

  const handleConvPageChange = (next: number) => {
    setConvPage(next);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(next, selectedAgentId, convIdSuffix);
  };

  const toggleExpandConversation = async (convId: string) => {
    if (expandedConvId === convId) {
      setExpandedConvId(null);
      setExpandedMessages([]);
      return;
    }
    setExpandedConvId(convId);
    setExpandedMessages([]);
    setIsLoadingMessages(true);
    const conv = await fetchConversationById(convId);
    setExpandedMessages((conv?.messages ?? []) as TranscriptEntry[]);
    setIsLoadingMessages(false);
  };

  const handleConfirmImport = async () => {
    if (!suiteId || !pendingImportConv) return;
    importSucceededRef.current = true;
    setIsImporting(true);
    try {
      await importCasesFromConversation(suiteId, pendingImportConv.id);
      toast.success("Conversation imported.");
      setPendingImportConv(null);
      await loadImportedConversations(suiteId);
    } catch (err: unknown) {
      importSucceededRef.current = false;
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(
        axiosErr?.response?.data?.error ?? "Failed to import the conversation.",
      );
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <>
      <Dialog open={isPickerVisible} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[760px] p-0 overflow-hidden flex flex-col max-h-[80vh]">
          <DialogHeader className="p-6 pb-4 shrink-0">
            {/* No summary line: each row carries its own "In dataset" badge. */}
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

          <div className="flex-1 min-h-0 overflow-y-auto px-6">
            {isLoadingConversations ? (
              <div className="text-sm text-muted-foreground py-4">
                Loading conversations...
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
                  return (
                    <div
                      key={conv.id}
                      className={`border rounded overflow-hidden ${
                        importedTurns ? "border-blue-300 bg-blue-50/40" : ""
                      }`}
                    >
                      <div className="p-3 flex items-center justify-between gap-3">
                        <button
                          className="flex items-center gap-2 min-w-0 text-left flex-1"
                          onClick={() => toggleExpandConversation(conv.id)}
                        >
                          <ChevronDown
                            className={`h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform ${isExpanded ? "" : "-rotate-90"}`}
                          />
                          <div className="min-w-0">
                            {/* No "in dataset" badge: the row tint and the
                                Re-import label already say so. */}
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
                        </button>
                        {/* Removing a conversation belongs on the dataset page,
                            where its turns are visible. */}
                        <Button
                          size="sm"
                          className="shrink-0"
                          variant={importedTurns ? "outline" : "default"}
                          onClick={() => setPendingImportConv(conv)}
                        >
                          {importedTurns ? "Re-import" : "Import"}
                        </Button>
                      </div>

                      {isExpanded && (
                        <div className="border-t bg-muted px-3 py-2 max-h-60 overflow-y-auto space-y-1.5">
                          {isLoadingMessages ? (
                            <p className="text-xs text-muted-foreground">
                              Loading messages...
                            </p>
                          ) : expandedMessages.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                              No messages found.
                            </p>
                          ) : (
                            expandedMessages.map((msg, idx) => {
                              const isAgent =
                                msg.speaker?.toLowerCase() === "agent";
                              return (
                                <div
                                  key={(msg as { id?: string }).id ?? idx}
                                  className={`flex flex-col ${isAgent ? "items-end" : "items-start"}`}
                                >
                                  <span className="text-[10px] text-foreground font-medium mb-0.5 capitalize">
                                    {msg.speaker}
                                  </span>
                                  <div
                                    className={`max-w-[80%] rounded-lg px-2.5 py-1.5 text-xs leading-tight break-words ${
                                      isAgent
                                        ? "bg-blue-500 text-white rounded-tr-none"
                                        : "bg-muted text-foreground rounded-tl-none"
                                    }`}
                                  >
                                    {msg.text}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {convTotal} conversation{convTotal !== 1 ? "s" : ""} total
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={convPage === 0}
                onClick={() => handleConvPageChange(convPage - 1)}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {convPage + 1}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(convPage + 1) * CONV_PAGE_SIZE >= convTotal}
                onClick={() => handleConvPageChange(convPage + 1)}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm import — appends one conversation's turns to the dataset */}
      <ConfirmDialog
        isOpen={!!pendingImportConv}
        onOpenChange={(next) => {
          if (!next) {
            const succeeded = importSucceededRef.current;
            importSucceededRef.current = false;
            setPendingImportConv(null);
            // A cancel drops back to the picker; a success is the end of the job.
            if (succeeded) onOpenChange(false);
          }
        }}
        onConfirm={handleConfirmImport}
        isInProgress={isImporting}
        title={
          pendingImportConv && importedConversations.has(pendingImportConv.id)
            ? `Re-import conversation #${pendingImportConv.id.slice(-6)}`
            : `Import from conversation #${pendingImportConv?.id.slice(-6) ?? ""}`
        }
        description={
          pendingImportConv && importedConversations.has(pendingImportConv.id)
            ? `This replaces the ${importedConversations.get(pendingImportConv.id)} turn(s) already imported from conversation #${pendingImportConv.id.slice(-6)} with a fresh copy of the transcript. Any edits or turns you added are lost, and past evaluation results stop matching them.`
            : `This adds the turns of conversation #${pendingImportConv?.id.slice(-6) ?? ""} (${pendingImportConv?.word_count ?? 0} words) to "${suite?.name ?? ""}", keeping everything already in the dataset.`
        }
        primaryButtonText={
          pendingImportConv && importedConversations.has(pendingImportConv.id)
            ? "Replace Turns"
            : "Add to Dataset"
        }
      />
    </>
  );
};

export default ImportFromConversationDialog;
