import React, {useCallback, useEffect, useRef, useState} from "react";
import toast from "react-hot-toast";
import {PageLayout} from "@/components/PageLayout";
import {PageHeader} from "@/components/PageHeader";
import {
  createTestSuite,
  deleteTestSuite,
  importCasesFromConversation,
  listTestCases,
  listTestSuites,
  updateTestSuite,
} from "@/services/testSuites";
import {TestSuite} from "@/interfaces/testSuite.interface";
import {Button} from "@/components/button";
import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";
import {Label} from "@/components/label";
import {useNavigate} from "react-router-dom";
import {Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,} from "@/components/ui/dialog";
import {ChevronDown, ChevronRight, Clock, Database, Import, Pencil, Plus, Trash2} from "lucide-react";
import {ConfirmDialog} from "@/components/ConfirmDialog";
import {fetchConversationById, fetchTranscripts} from "@/services/transcripts";
import type {BackendTranscript, TranscriptEntry} from "@/interfaces/transcript.interface";
import {getWorkflowsMinimal} from "@/services/workflows";
import type {WorkflowMinimal} from "@/interfaces/workflow.interface";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue,} from "@/components/select";
import {Skeleton} from "@/components/skeleton";

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
  const [isImporting, setIsImporting] = useState(false);
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

  const handleCreateDataset = async () => {
    if (!suiteName.trim()) return;
    const created = await createTestSuite({
      name: suiteName.trim(),
      description: suiteDescription.trim() || undefined,
    });
    if (created) {
      setSuites((prev) => [created, ...prev]);
      setSuiteName("");
      setSuiteDescription("");
      setIsCreateDialogOpen(false);
      if (created.id) navigate(`/tests/datasets/${created.id}`);
    }
  };

  const handleOpenEditDataset = (suite: TestSuite) => {
    setEditingDatasetId(suite.id ?? null);
    setSuiteName(suite.name);
    setSuiteDescription(suite.description ?? "");
    setIsEditDialogOpen(true);
  };

  const handleSaveEditDataset = async () => {
    if (!editingDatasetId || !suiteName.trim()) return;
    const updated = await updateTestSuite(editingDatasetId, {
      name: suiteName.trim(),
      description: suiteDescription.trim() || undefined,
    });
    setSuites((prev) => prev.map((s) => (s.id === editingDatasetId ? updated : s)));
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

  const openImportDialog = async (suite: TestSuite) => {
    setImportTargetSuite(suite);
    setConvPage(0);
    setSelectedWorkflowId("");
    setConvIdSuffix("");
    setExpandedConvId(null);
    setExpandedMessages([]);
    setIsImportDialogOpen(true);
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
      await importCasesFromConversation(importTargetSuite.id, pendingImportConv.id, true);
      toast.success("Cases imported successfully.");
      setPendingImportConv(null);
    } catch (err: unknown) {
      importSucceededRef.current = false;
      const axiosErr = err as { response?: { data?: { error?: string } } };
      const msg = axiosErr?.response?.data?.error ?? "Failed to import cases.";
      toast.error(msg);
    } finally {
      setIsImporting(false);
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

      <div className="rounded-lg border bg-white overflow-hidden">
        {isLoading ? (
          <div className="divide-y divide-gray-100">
            {[1, 2, 3].map((i) => (
              <div key={i} className="py-4 px-6">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-4 w-64" />
                    <Skeleton className="h-3 w-32 mt-2" />
                  </div>
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-6 w-16 rounded-md" />
                    <Skeleton className="h-8 w-8 rounded" />
                    <Skeleton className="h-8 w-8 rounded" />
                    <Skeleton className="h-8 w-8 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredSuites.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
            <div className="rounded-full bg-gray-100 p-4">
              <Database className="h-12 w-12 text-gray-400" />
            </div>
            <h3 className="font-medium text-lg">No datasets yet</h3>
            <p className="text-sm text-gray-500 max-w-sm">
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
          <div className="divide-y divide-gray-100">
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
                  className="w-full py-4 px-6 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/tests/datasets/${suite.id}`)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex items-center gap-2">
                        <div className="text-lg font-semibold truncate">{suite.name}</div>
                        <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black shrink-0">
                          DATASET
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                        {suite.description || "No description"}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
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

      {/* Create dataset dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="sm:max-w-[560px] p-0 overflow-hidden">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>Create Dataset</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 px-6 pb-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Dataset name</Label>
              <Input
                value={suiteName}
                onChange={(e) => setSuiteName(e.target.value)}
                placeholder="e.g. FAQ Gold Set"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">Description</Label>
              <Textarea
                value={suiteDescription}
                onChange={(e) => setSuiteDescription(e.target.value)}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter className="border-t px-6 py-4">
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateDataset} disabled={!suiteName.trim()}>
              Create Dataset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit dataset dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[560px] p-0 overflow-hidden">
          <DialogHeader className="p-6 pb-4">
            <DialogTitle>Edit Dataset</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 pb-6">
            <Label className="text-xs">Dataset name</Label>
            <Input value={suiteName} onChange={(e) => setSuiteName(e.target.value)} />
            <Label className="text-xs">Description</Label>
            <Textarea
              value={suiteDescription}
              onChange={(e) => setSuiteDescription(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter className="border-t px-6 py-4">
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEditDataset} disabled={!suiteName.trim()}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import from conversation dialog */}
      <Dialog open={isImportDialogOpen} onOpenChange={setIsImportDialogOpen}>
        <DialogContent className="sm:max-w-[760px] p-0 overflow-hidden flex flex-col max-h-[80vh]">
          <DialogHeader className="p-6 pb-4 shrink-0">
            <DialogTitle>
              Import into "{importTargetSuite?.name}"
            </DialogTitle>
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
                  {workflows.map((wf) => (
                    <SelectItem key={wf.id} value={wf.id ?? ""}>
                      {wf.name}
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
              <div className="text-sm text-gray-400 py-4">Loading conversations…</div>
            ) : conversations.length === 0 ? (
              <div className="text-sm text-gray-400 py-4">No conversations found.</div>
            ) : (
              <div className="space-y-2 py-2">
                {conversations.map((conv) => {
                  const isExpanded = expandedConvId === conv.id;
                  return (
                    <div key={conv.id} className="border rounded overflow-hidden">
                      <div className="p-3 flex items-center justify-between gap-3">
                        <button
                          className="flex items-center gap-2 min-w-0 text-left flex-1"
                          onClick={() => toggleExpandConversation(conv.id)}
                        >
                          <ChevronDown
                            className={`h-3.5 w-3.5 text-gray-400 shrink-0 transition-transform ${isExpanded ? "" : "-rotate-90"}`}
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-foreground">
                              #{conv.id.slice(-4)}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">
                              {conv.conversation_date
                                ? new Date(conv.conversation_date).toLocaleDateString()
                                : "—"}{" "}
                              · {conv.word_count ?? 0} words · {conv.status}
                            </p>
                          </div>
                        </button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setIsImportDialogOpen(false);
                            setPendingImportConv(conv);
                          }}
                        >
                          Import
                        </Button>
                      </div>

                      {isExpanded && (
                        <div className="border-t bg-gray-50 px-3 py-2 max-h-60 overflow-y-auto space-y-1.5">
                          {isLoadingMessages ? (
                            <p className="text-xs text-gray-400">Loading messages…</p>
                          ) : expandedMessages.length === 0 ? (
                            <p className="text-xs text-gray-400">No messages found.</p>
                          ) : (
                            expandedMessages.map((msg, idx) => {
                              const isAgent = msg.speaker?.toLowerCase() === "agent";
                              return (
                                <div
                                  key={(msg as { id?: string }).id ?? idx}
                                  className={`flex flex-col ${isAgent ? "items-end" : "items-start"}`}
                                >
                                  <span className="text-[10px] text-black font-medium mb-0.5 capitalize">
                                    {msg.speaker}
                                  </span>
                                  <div
                                    className={`max-w-[80%] rounded-lg px-2.5 py-1.5 text-xs leading-tight break-words ${
                                      isAgent
                                        ? "bg-blue-500 text-white rounded-tr-none"
                                        : "bg-gray-200 text-gray-900 rounded-tl-none"
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
            <span className="text-xs text-gray-500">
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
              <span className="text-xs text-gray-500">Page {convPage + 1}</span>
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

      {/* Confirm import — replaces all existing records */}
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
        description={`This will replace all existing records in "${importTargetSuite?.name ?? ""}" with Q&A pairs from conversation #${pendingImportConv?.id.slice(-4) ?? ""} (${pendingImportConv?.word_count ?? 0} words).`}
        primaryButtonText="Replace & Import"
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