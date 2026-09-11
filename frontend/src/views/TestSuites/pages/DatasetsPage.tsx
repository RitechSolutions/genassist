import React, {useCallback, useEffect, useRef, useState} from "react";
import toast from "react-hot-toast";
import {PageLayout} from "@/components/PageLayout";
import {PageHeader} from "@/components/PageHeader";
import {
  createTestSuite,
  deleteTestSuite,
  importCasesFromConversation,
  listTestCases,
  removeConversationFromSuite,
  listTestSuites,
  updateTestSuite,
} from "@/services/testSuites";
import {TestSuite} from "@/interfaces/testSuite.interface";
import {Button} from "@/components/button";
import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";
import {Label} from "@/components/label";
import {useNavigate} from "react-router-dom";
import {Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,} from "@/components/dialog";
import {CRUDDialog} from "@/components/ui/crud-dialog";
import {ChevronDown, ChevronRight, Clock, Database, Import, Pencil, Plus, Trash2} from "lucide-react";
import {ConfirmDialog} from "@/components/ConfirmDialog";
import {fetchConversationById, fetchTranscripts} from "@/services/transcripts";
import type {BackendTranscript, TranscriptEntry} from "@/interfaces/transcript.interface";
import {getWorkflowsMinimal} from "@/services/workflows";
import type {WorkflowMinimal} from "@/interfaces/workflow.interface";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue,} from "@/components/select";
import {PageListSkeleton} from "@/components/skeletons";
import {EntityTitle} from "../components/EntityTitle";

const CONV_PAGE_SIZE = 20;

const getTimeAgo = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins} min${diffMins !== 1 ? "s" : ""} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
};

// Named after the agent, as the workflow picker does; the version keeps two
// entries apart, and the workflow name settles versions that still collide.
const workflowFilterOptions = (workflows: WorkflowMinimal[]) => {
  const options = workflows.map((workflow) => ({
    id: workflow.id,
    label: `${workflow.agent_name || workflow.name} · v${workflow.version}`,
    workflowName: workflow.name,
  }));
  const counts = new Map<string, number>();
  options.forEach((o) => counts.set(o.label, (counts.get(o.label) ?? 0) + 1));

  return options
    .map((option) =>
      (counts.get(option.label) ?? 0) > 1
        ? { ...option, label: `${option.label} (${option.workflowName})` }
        : option,
    )
    .sort((a, b) => a.label.localeCompare(b.label));
};

const DatasetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [recordCounts, setRecordCounts] = useState<Record<string, number>>({});
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [datasetToDelete, setDatasetToDelete] = useState<TestSuite | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editingDatasetId, setEditingDatasetId] = useState<string | null>(null);
  const [suiteName, setSuiteName] = useState("");
  const [suiteDescription, setSuiteDescription] = useState("");

  // Import from conversation state
  const [importTargetSuite, setImportTargetSuite] = useState<TestSuite | null>(null);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowMinimal[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [convIdSuffix, setConvIdSuffix] = useState("");
  const [conversations, setConversations] = useState<BackendTranscript[]>([]);
  const [convPage, setConvPage] = useState(0);
  const [convTotal, setConvTotal] = useState(0);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<TranscriptEntry[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [pendingImportConv, setPendingImportConv] = useState<BackendTranscript | null>(null);
  const [importMode, setImportMode] = useState<"append" | "replace">("append");
  const [isImporting, setIsImporting] = useState(false);
  const [pendingRemoveConv, setPendingRemoveConv] = useState<BackendTranscript | null>(null);
  const [isRemovingConv, setIsRemovingConv] = useState(false);
  // Conversation id -> number of turns already imported into the target dataset.
  const [importedConversations, setImportedConversations] = useState<Map<string, number>>(
    new Map(),
  );
  const importSucceededRef = useRef(false);
  const idSuffixDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const suiteData = await listTestSuites();
        setSuites(suiteData ?? []);
        // Load record counts for each suite
        const counts: Record<string, number> = {};
        await Promise.all(
          (suiteData ?? []).map(async (suite) => {
            if (suite.id) {
              const cases = await listTestCases(suite.id);
              counts[suite.id] = (cases ?? []).length;
            }
          })
        );
        setRecordCounts(counts);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  // ---- Dataset CRUD -------------------------------------------------------

  const handleOpenEditDataset = (suite: TestSuite) => {
    setEditingDatasetId(suite.id ?? null);
    setSuiteName(suite.name);
    setSuiteDescription(suite.description ?? "");
    setIsEditDialogOpen(true);
  };

  const closeDatasetDialog = () => {
    setIsCreateDialogOpen(false);
    setIsEditDialogOpen(false);
    setEditingDatasetId(null);
    setSuiteName("");
    setSuiteDescription("");
  };

  const handleDeleteDataset = async () => {
    if (!datasetToDelete?.id) return;
    setIsDeleting(true);
    try {
      await deleteTestSuite(datasetToDelete.id);
      setSuites((prev) => prev.filter((s) => s.id !== datasetToDelete.id));
      toast.success("Dataset deleted successfully.");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(axiosErr?.response?.data?.error ?? "Failed to delete dataset.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setDatasetToDelete(null);
    }
  };

  // ---- Conversation picker -------------------------------------------------

  const loadConversations = useCallback(async (page: number, workflowId: string, idSuffix: string) => {
    setIsLoadingConversations(true);
    const result = await fetchTranscripts({
      skip: page * CONV_PAGE_SIZE,
      limit: CONV_PAGE_SIZE,
      workflow_id: workflowId || undefined,
      id_suffix: idSuffix || undefined,
    });
    setConversations(result.items);
    setConvTotal(result.total);
    setIsLoadingConversations(false);
  }, []);

  /** Refreshes both the dataset's record count and its imported conversations. */
  const loadImportedConversations = async (suiteId: string) => {
    const cases = (await listTestCases(suiteId)) ?? [];
    const turnsByConversation = new Map<string, number>();
    for (const entry of cases) {
      const conversationId = entry.source_conversation_id;
      if (!conversationId) continue;
      turnsByConversation.set(
        conversationId,
        (turnsByConversation.get(conversationId) ?? 0) + 1,
      );
    }
    setImportedConversations(turnsByConversation);
    setRecordCounts((prev) => ({ ...prev, [suiteId]: cases.length }));
  };

  const openImportDialog = async (suite: TestSuite) => {
    setImportTargetSuite(suite);
    setConvPage(0);
    setSelectedWorkflowId("");
    setConvIdSuffix("");
    setExpandedConvId(null);
    setExpandedMessages([]);
    setImportedConversations(new Map());
    // Always reopen on the non-destructive mode so a previous "Replace all"
    // cannot silently wipe the next dataset.
    setImportMode("append");
    setIsImportDialogOpen(true);
    if (suite.id) loadImportedConversations(suite.id);
    const wfs = await getWorkflowsMinimal();
    setWorkflows(wfs ?? []);
    loadConversations(0, "", "");
  };

  const handleWorkflowFilterChange = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setConvPage(0);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(0, workflowId, convIdSuffix);
  };

  const handleConvIdSuffixChange = (suffix: string) => {
    setConvIdSuffix(suffix);
    if (idSuffixDebounceRef.current) clearTimeout(idSuffixDebounceRef.current);
    idSuffixDebounceRef.current = setTimeout(() => {
      setConvPage(0);
      setExpandedConvId(null);
      setExpandedMessages([]);
      loadConversations(0, selectedWorkflowId, suffix);
    }, 700);
  };

  const handleConvPageChange = (next: number) => {
    setConvPage(next);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(next, selectedWorkflowId, convIdSuffix);
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
    if (!importTargetSuite?.id || !pendingImportConv) return;
    importSucceededRef.current = true;
    setIsImporting(true);
    try {
      await importCasesFromConversation(
        importTargetSuite.id,
        pendingImportConv.id,
        importMode === "replace",
      );
      toast.success("Cases imported successfully.");
      setPendingImportConv(null);
      await loadImportedConversations(importTargetSuite.id);
    } catch (err: unknown) {
      importSucceededRef.current = false;
      const axiosErr = err as { response?: { data?: { error?: string } } };
      const msg = axiosErr?.response?.data?.error ?? "Failed to import cases.";
      toast.error(msg);
    } finally {
      setIsImporting(false);
    }
  };

  const handleConfirmRemoveConversation = async () => {
    if (!importTargetSuite?.id || !pendingRemoveConv) return;
    setIsRemovingConv(true);
    try {
      await removeConversationFromSuite(importTargetSuite.id, pendingRemoveConv.id);
      toast.success("Conversation removed from dataset.");
      await loadImportedConversations(importTargetSuite.id);
      setPendingRemoveConv(null);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      toast.error(axiosErr?.response?.data?.error ?? "Failed to remove conversation.");
    } finally {
      setIsRemovingConv(false);
    }
  };

  // ---- Filtering -----------------------------------------------------------

  const filteredSuites = suites.filter((suite) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;
    return (
      suite.name.toLowerCase().includes(query) ||
      (suite.description ?? "").toLowerCase().includes(query)
    );
  });

  return (
    <PageLayout>
      <PageHeader
        title="Datasets"
        subtitle="Create reusable golden datasets and manage their records."
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search datasets..."
        actionButtonText="New Dataset"
        onActionClick={() => setIsCreateDialogOpen(true)}
      />

      <div className="rounded-lg border bg-card dark:bg-zinc-900 overflow-hidden">
        {isLoading ? (
          <PageListSkeleton bordered={false} />
        ) : filteredSuites.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-muted p-4">
              <Database className="h-12 w-12 text-muted-foreground" />
            </div>
            <h3 className="font-medium text-lg">No datasets yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              {searchQuery
                ? "No datasets match your search. Try adjusting your query."
                : "Datasets contain test cases for evaluating your AI agents. Create your first dataset to get started."}
            </p>
            {!searchQuery && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create your first dataset
              </Button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredSuites.map((suite) => {
              const recordCount = suite.id ? recordCounts[suite.id] ?? 0 : 0;
              const updatedAt = suite.updated_at
                ? new Date(suite.updated_at)
                : null;
              const timeAgo = updatedAt
                ? getTimeAgo(updatedAt)
                : null;

              return (
                <div
                  key={suite.id}
                  className="w-full py-4 px-6 text-left hover:bg-muted transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/tests/datasets/${suite.id}`)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex items-center gap-2">
                        <EntityTitle>{suite.name}</EntityTitle>
                        <span className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-bold text-foreground shrink-0">
                          DATASET
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
                        {suite.description || "No description"}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <Database className="h-3 w-3" />
                          {recordCount} record{recordCount !== 1 ? "s" : ""}
                        </span>
                        {timeAgo && (
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            Updated {timeAgo}
                          </span>
                        )}
                      </div>
                    </button>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        aria-label="Import from Conversation"
                        onClick={() => openImportDialog(suite)}
                      >
                        <Import className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        aria-label="Edit dataset"
                        onClick={() => handleOpenEditDataset(suite)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-500"
                        aria-label="Delete dataset"
                        onClick={() => {
                          setDatasetToDelete(suite);
                          setIsDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create / edit dataset dialog */}
      <CRUDDialog<{ name: string; description: string }>
        open={isCreateDialogOpen || isEditDialogOpen}
        onOpenChange={(next) => {
          if (!next) closeDatasetDialog();
        }}
        mode={isEditDialogOpen ? "edit" : "create"}
        maxWidth="560px"
        resetKey={isEditDialogOpen ? editingDatasetId : "create"}
        initialValues={{ name: "", description: "" }}
        editValues={
          isEditDialogOpen
            ? { name: suiteName, description: suiteDescription }
            : null
        }
        title={{ create: "Create Dataset", edit: "Edit Dataset" }}
        submitLabel={{ create: "Create Dataset", edit: "Save Changes" }}
        loadingLabel={{ create: "Creating...", edit: "Saving..." }}
        successMessage={null}
        errorMessage="Failed to save dataset."
        submitDisabled={(form) => !form.values.name.trim()}
        onSubmit={async (values, { mode }) => {
          if (mode === "create") {
            const created = await createTestSuite({
              name: values.name.trim(),
              description: values.description.trim() || undefined,
            });
            if (created) {
              setSuites((prev) => [created, ...prev]);
              if (created.id) navigate(`/tests/datasets/${created.id}`);
            }
          } else {
            if (!editingDatasetId) return;
            const updated = await updateTestSuite(editingDatasetId, {
              name: values.name.trim(),
              description: values.description.trim() || undefined,
            });
            setSuites((prev) =>
              prev.map((s) => (s.id === editingDatasetId ? updated : s))
            );
          }
        }}
      >
        {({ values, setField }) => (
          <>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Dataset name</Label>
              <Input
                value={values.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="e.g. FAQ Gold Set"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Description</Label>
              <Textarea
                value={values.description}
                onChange={(e) => setField("description", e.target.value)}
                size="hint"
              />
            </div>
          </>
        )}
      </CRUDDialog>

      {/* Import from conversation dialog */}
      <Dialog open={isImportDialogOpen} onOpenChange={setIsImportDialogOpen}>
        <DialogContent className="sm:max-w-[760px] p-0 overflow-hidden flex flex-col max-h-[80vh]">
          <DialogHeader className="p-6 pb-4 shrink-0">
            <DialogTitle>
              Import into "{importTargetSuite?.name}"
            </DialogTitle>
            <p className="text-xs text-gray-500 mt-1">
              {importedConversations.size === 0
                ? "No conversations imported into this dataset yet."
                : `Already in this dataset: ${importedConversations.size} conversation${
                    importedConversations.size === 1 ? "" : "s"
                  } — ${[...importedConversations.entries()]
                    .map(([id, turns]) => `#${id.slice(-4)} (${turns})`)
                    .join(", ")}`}
            </p>
          </DialogHeader>

          <div className="px-6 pb-2 shrink-0 flex gap-3">
            <div className="flex-1">
              <Label className="text-xs mb-1 block">Filter by Workflow</Label>
              <Select
                value={selectedWorkflowId || "__all__"}
                onValueChange={(v) => handleWorkflowFilterChange(v === "__all__" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All workflows" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All workflows</SelectItem>
                  {workflowFilterOptions(workflows).map((option) => (
                    <SelectItem key={option.id} value={option.id ?? ""}>
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
            <div className="w-44">
              <Label className="text-xs mb-1 block">Import mode</Label>
              <Select
                value={importMode}
                onValueChange={(v) => setImportMode(v as "append" | "replace")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="append">Add to dataset</SelectItem>
                  <SelectItem value="replace">Replace all</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-6">
            {isLoadingConversations ? (
              <div className="text-sm text-muted-foreground py-4">Loading conversations…</div>
            ) : conversations.length === 0 ? (
              <div className="text-sm text-muted-foreground py-4">No conversations found.</div>
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
                            <p className="text-sm font-medium text-foreground flex items-center gap-2">
                              #{conv.id.slice(-4)}
                              {importedTurns && (
                                <span className="inline-flex items-center text-xs rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 font-normal">
                                  In dataset · {importedTurns} turn
                                  {importedTurns === 1 ? "" : "s"}
                                </span>
                              )}
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {conv.conversation_date
                                ? new Date(conv.conversation_date).toLocaleDateString()
                                : "—"}{" "}
                              · {conv.word_count ?? 0} words · {conv.status}
                            </p>
                          </div>
                        </button>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            size="sm"
                            variant={importedTurns ? "outline" : "default"}
                            onClick={() => {
                              setIsImportDialogOpen(false);
                              setPendingImportConv(conv);
                            }}
                          >
                            {importedTurns ? "Re-import" : "Import"}
                          </Button>
                          {importedTurns && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-red-500"
                              title="Remove this conversation from the dataset"
                              onClick={() => {
                                setIsImportDialogOpen(false);
                                setPendingRemoveConv(conv);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="border-t bg-muted px-3 py-2 max-h-60 overflow-y-auto space-y-1.5">
                          {isLoadingMessages ? (
                            <p className="text-xs text-muted-foreground">Loading messages…</p>
                          ) : expandedMessages.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No messages found.</p>
                          ) : (
                            expandedMessages.map((msg, idx) => {
                              const isAgent = msg.speaker?.toLowerCase() === "agent";
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
              <span className="text-xs text-muted-foreground">Page {convPage + 1}</span>
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

      {/* Confirm import — appends a conversation or replaces the whole dataset */}
      <ConfirmDialog
        isOpen={!!pendingImportConv}
        onOpenChange={(open) => {
          if (!open) {
            const succeeded = importSucceededRef.current;
            importSucceededRef.current = false;
            setPendingImportConv(null);
            if (!succeeded) setIsImportDialogOpen(true);
          }
        }}
        onConfirm={handleConfirmImport}
        isInProgress={isImporting}
        title={`Import from conversation #${pendingImportConv?.id.slice(-4) ?? ""}`}
        description={
          importMode === "replace"
            ? `This will replace all existing records in "${importTargetSuite?.name ?? ""}" with Q&A pairs from conversation #${pendingImportConv?.id.slice(-4) ?? ""} (${pendingImportConv?.word_count ?? 0} words).`
            : `This will add Q&A pairs from conversation #${pendingImportConv?.id.slice(-4) ?? ""} (${pendingImportConv?.word_count ?? 0} words) to "${importTargetSuite?.name ?? ""}", keeping conversations already in the dataset. Re-importing the same conversation refreshes its turns.`
        }
        primaryButtonText={importMode === "replace" ? "Replace & Import" : "Add to Dataset"}
      />

      {/* Confirm removing one conversation's records from the dataset */}
      <ConfirmDialog
        isOpen={!!pendingRemoveConv}
        onOpenChange={(open) => {
          if (!open) {
            setPendingRemoveConv(null);
            setIsImportDialogOpen(true);
          }
        }}
        onConfirm={handleConfirmRemoveConversation}
        isInProgress={isRemovingConv}
        title={`Remove conversation #${pendingRemoveConv?.id.slice(-4) ?? ""}`}
        description={`This removes the records imported from conversation #${pendingRemoveConv?.id.slice(-4) ?? ""} from "${importTargetSuite?.name ?? ""}". Other conversations in the dataset are kept.`}
        primaryButtonText="Remove"
      />

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteDataset}
        isInProgress={isDeleting}
        itemName={datasetToDelete?.name || ""}
        description={`This will delete dataset "${datasetToDelete?.name}" along with all related evaluations and their runs.`}
        requireConfirmText="delete"
      />
    </PageLayout>
  );
};

export default DatasetsPage;