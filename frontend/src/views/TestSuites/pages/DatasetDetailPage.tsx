import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import toast from "react-hot-toast";
import {
  addTestCase,
  deleteTestCase,
  getTestSuite,
  listTestCases,
  removeConversationFromSuite,
  updateTestCase,
} from "@/services/testSuites";
import { TestCase, TestSuite } from "@/interfaces/testSuite.interface";
import { Button } from "@/components/button";
import { ChevronLeft, Import, MessagesSquare, Plus } from "lucide-react";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ListEmptyState } from "@/components/ListEmptyState";
import { PageListSkeleton } from "@/components/skeletons";
import { ConversationRecordGroup } from "../components/ConversationRecordGroup";
import { ImportFromConversationDialog } from "../components/ImportFromConversationDialog";
import { RecordDialog, RecordPayload } from "../components/RecordDialog";
import {
  countConversations,
  groupCasesByConversation,
  type ConversationGroup,
} from "../helpers/datasetConversations";

const DatasetDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { datasetId } = useParams<{ datasetId: string }>();
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  // The card shows a skeleton until the first load settles, like every other list.
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  // Set when appending to an existing hand-authored thread; null starts a new one.
  const [pendingThread, setPendingThread] = useState<{
    id: string;
    nextTurn: number;
  } | null>(null);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<TestCase | null>(null);
  const [deletingTurn, setDeletingTurn] = useState<number | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [conversationToRemove, setConversationToRemove] = useState<{
    id: string;
    label: string;
    turns: number;
  } | null>(null);
  const [isRemovingConversation, setIsRemovingConversation] = useState(false);
  // Everything starts collapsed, so a large dataset opens as a readable list
  // and nothing is open that the user did not open.
  const [expandedRecords, setExpandedRecords] = useState<Set<string>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [newestId, setNewestId] = useState<string | null>(null);

  useEffect(() => {
    if (!newestId) return;
    const el = document.getElementById(`record-${newestId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setNewestId(null);
  }, [newestId]);

  useEffect(() => {
    const load = async () => {
      if (!datasetId) return;
      try {
        const [suiteData, caseData] = await Promise.all([
          getTestSuite(datasetId),
          listTestCases(datasetId),
        ]);
        setSuite(suiteData ?? null);
        setCases(caseData ?? []);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [datasetId]);

  const toggleRecordExpansion = (id: string) => {
    setExpandedRecords((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleAddCase = async (payload: RecordPayload) => {
    if (!datasetId) return;
    // Every hand-written turn gets a thread id, so it is already a
    // conversation of one and can grow a second turn without being re-threaded.
    const thread = pendingThread ?? { id: crypto.randomUUID(), nextTurn: 0 };
    const created = await addTestCase(datasetId, {
      ...payload,
      source_conversation_id: thread.id,
      turn_index: thread.nextTurn,
    });
    if (!created) throw new Error("The turn was not saved.");

    setCases((prev) => [...prev, created]);
    setExpandedRecords((prev) => new Set([...prev, created.id]));
    // Open the thread too, or a brand-new conversation renders collapsed and
    // there is nothing for the scroll below to find.
    setExpandedGroups((prev) => new Set(prev).add(thread.id));
    setNewestId(created.id);
  };

  const openEditDialog = (entry: TestCase) => {
    setEditingCase(entry);
    setIsEditDialogOpen(true);
  };

  const handleSaveEditCase = async (payload: RecordPayload) => {
    if (!editingCase?.id) return;
    const updated = await updateTestCase(editingCase.id, payload);
    if (!updated) throw new Error("The turn was not saved.");

    setCases((prev) => prev.map((c) => (c.id === editingCase.id ? updated : c)));
    setEditingCase(null);
  };

  const handleDeleteCase = async () => {
    if (!caseToDelete?.id) return;
    setIsDeleting(true);
    try {
      await deleteTestCase(caseToDelete.id);
      setCases((prev) => prev.filter((c) => c.id !== caseToDelete.id));
      toast.success(`Turn ${deletingTurn ?? ""} deleted.`);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(axiosErr?.response?.data?.error ?? "Failed to delete the turn.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setCaseToDelete(null);
      setDeletingTurn(null);
    }
  };

  const handleRemoveConversation = async () => {
    if (!datasetId || !conversationToRemove) return;
    setIsRemovingConversation(true);
    try {
      await removeConversationFromSuite(datasetId, conversationToRemove.id);
      setCases((prev) =>
        prev.filter((c) => c.source_conversation_id !== conversationToRemove.id),
      );
      toast.success(`${conversationToRemove.label} removed.`);
      setConversationToRemove(null);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(
        axiosErr?.response?.data?.error ?? "Failed to remove conversation.",
      );
    } finally {
      setIsRemovingConversation(false);
    }
  };

  const filteredCases = cases.filter((entry) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;
    const inputText = JSON.stringify(entry.input_data ?? {}).toLowerCase();
    const expectedText = JSON.stringify(entry.expected_output ?? {}).toLowerCase();
    return inputText.includes(query) || expectedText.includes(query);
  });

  const conversationGroups = groupCasesByConversation(filteredCases);
  // The header counts describe the dataset, so they ignore the search filter.
  const conversationCount = countConversations(cases);
  const countLabel = `${conversationCount} conversation${
    conversationCount === 1 ? "" : "s"
  } · ${cases.length} turn${cases.length === 1 ? "" : "s"}`;
  const isSearching = searchQuery.trim().length > 0;

  // Opens or closes every turn in one conversation, opening the group itself
  // when expanding so the turns are actually visible.
  const setTurnsExpanded = (group: ConversationGroup, expand: boolean) => {
    const ids = group.cases.map((entry) => entry.id ?? "");
    setExpandedRecords((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (expand ? next.add(id) : next.delete(id)));
      return next;
    });
    if (expand) setExpandedGroups((prev) => new Set(prev).add(group.key));
  };

  const toggleGroupExpansion = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <PageLayout>
      {/* Header: back, identity, then search and the conversation actions.
          PageHeader has no back slot, so detail pages hand-roll this row. */}
      <div className="flex flex-wrap items-start gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/tests/datasets")}
          aria-label="Back to Datasets"
          className="shrink-0"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div className="min-w-0 flex-1">
          {/* Counts trail the name in muted type, as on Agent Studio. Too narrow
              to sit beside it, they drop below the description instead. */}
          <h1 className="text-2xl font-bold tracking-tight animate-fade-down md:text-3xl">
            {suite?.name ?? "Dataset"}{" "}
            {!isLoading && (
              <span className="hidden sm:inline text-lg md:text-xl text-muted-foreground font-normal">
                {countLabel}
              </span>
            )}
          </h1>
          {suite?.description && (
            <p className="mt-1 text-sm text-muted-foreground animate-fade-up">
              {suite.description}
            </p>
          )}
          {!isLoading && (
            <div className="mt-2 sm:hidden">
              <span className="text-base font-normal text-muted-foreground">
                {countLabel}
              </span>
            </div>
          )}
        </div>
        {/* One gap for search and both buttons, as on Agent Studio. */}
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <SearchInput
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={setSearchQuery}
          />
          <Button
            variant="outline"
            className="w-full justify-center rounded-full sm:w-auto"
            icon={<Import className="h-4 w-4" />}
            disabled={!suite}
            onClick={() => setIsImportDialogOpen(true)}
          >
            Import conversation
          </Button>
          <Button
            className="w-full justify-center rounded-full sm:w-auto"
            icon={<Plus className="h-4 w-4" />}
            onClick={() => {
              setPendingThread(null);
              setIsAddDialogOpen(true);
            }}
          >
            New conversation
          </Button>
        </div>
      </div>

      {isLoading || conversationGroups.length === 0 ? (
        <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
          {isLoading ? <PageListSkeleton bordered={false} /> : null}
          {!isLoading && (
            <ListEmptyState
              icon={<MessagesSquare className="h-12 w-12 text-muted-foreground" />}
              title={
                isSearching ? "No matching conversations" : "No conversations yet"
              }
              description={
                isSearching
                  ? "No conversations match your search. Try adjusting your query."
                  : "A dataset holds the conversations you evaluate an agent against. Import one from a real transcript, or write your own."
              }
              action={
                isSearching ? undefined : (
                  <Button
                    className="rounded-full"
                    icon={<Plus className="h-4 w-4" />}
                    onClick={() => {
                      setPendingThread(null);
                      setIsAddDialogOpen(true);
                    }}
                  >
                    Create your first conversation
                  </Button>
                )
              }
            />
          )}
        </div>
      ) : (
        // Each conversation is its own card, so they read as separate threads.
        <div className="space-y-3">
          {conversationGroups.map((group) => (
            <ConversationRecordGroup
              key={group.key}
              group={group}
              isCollapsed={!expandedGroups.has(group.key)}
              onToggleCollapse={() => toggleGroupExpansion(group.key)}
              expandedRecords={expandedRecords}
              onToggleRecord={toggleRecordExpansion}
              onEdit={openEditDialog}
              onDelete={(entry, turnNumber) => {
                setCaseToDelete(entry);
                setDeletingTurn(turnNumber);
                setIsDeleteDialogOpen(true);
              }}
              onRemoveConversation={setConversationToRemove}
              onSetTurnsExpanded={(expand) => setTurnsExpanded(group, expand)}
              onAddTurn={() => {
                if (!group.conversationId) return;
                setPendingThread({
                  id: group.conversationId,
                  nextTurn:
                    Math.max(
                      ...group.cases.map((entry) => entry.turn_index ?? 0),
                    ) + 1,
                });
                setIsAddDialogOpen(true);
              }}
            />
          ))}
        </div>
      )}

      <RecordDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        startsConversation={!pendingThread}
        onSubmit={handleAddCase}
      />

      <RecordDialog
        open={isEditDialogOpen}
        onOpenChange={(next) => {
          setIsEditDialogOpen(next);
          if (!next) setEditingCase(null);
        }}
        record={editingCase}
        onSubmit={handleSaveEditCase}
      />

      <ImportFromConversationDialog
        open={isImportDialogOpen}
        onOpenChange={setIsImportDialogOpen}
        suite={suite}
        onDatasetChanged={(_suiteId, records) => setCases(records)}
      />

      <ConfirmDialog
        isOpen={!!conversationToRemove}
        onOpenChange={(open) => {
          if (!open) setConversationToRemove(null);
        }}
        onConfirm={handleRemoveConversation}
        isInProgress={isRemovingConversation}
        title={`Remove ${conversationToRemove?.label ?? "conversation"}?`}
        description={`This will permanently delete its ${conversationToRemove?.turns ?? 0} turn${
          conversationToRemove?.turns === 1 ? "" : "s"
        }. Everything else in "${suite?.name ?? ""}" is kept.`}
        primaryButtonText="Remove"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteCase}
        isInProgress={isDeleting}
        title={`Delete turn ${deletingTurn ?? ""}?`}
        description={`This will permanently delete turn ${deletingTurn ?? ""}. Later turns will be renumbered.`}
      />
    </PageLayout>
  );
};

export default DatasetDetailPage;
