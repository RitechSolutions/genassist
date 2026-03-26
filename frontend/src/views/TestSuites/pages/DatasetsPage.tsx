import React, { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import {
  createTestSuite,
  deleteTestSuite,
  importCasesFromConversation,
  listTestSuites,
  updateTestSuite,
} from "@/services/testSuites";
import { TestSuite } from "@/interfaces/testSuite.interface";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import { Label } from "@/components/label";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Plus, Database, Pencil, Trash2, Import, ChevronRight, ChevronDown } from "lucide-react";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { fetchConversationById, fetchTranscripts } from "@/services/transcripts";
import type { BackendTranscript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { getAllWorkflows } from "@/services/workflows";
import type { Workflow } from "@/interfaces/workflow.interface";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

const CONV_PAGE_SIZE = 20;

const DatasetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
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
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
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

  useEffect(() => {
    const load = async () => {
      const suiteData = await listTestSuites();
      setSuites(suiteData ?? []);
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

  const loadConversations = useCallback(async (page: number, workflowId: string) => {
    setIsLoadingConversations(true);
    const result = await fetchTranscripts({
      skip: page * CONV_PAGE_SIZE,
      limit: CONV_PAGE_SIZE,
      workflow_id: workflowId || undefined,
    });
    setConversations(result.items);
    setConvTotal(result.total);
    setIsLoadingConversations(false);
  }, []);

  const openImportDialog = async (suite: TestSuite) => {
    setImportTargetSuite(suite);
    setConvPage(0);
    setSelectedWorkflowId("");
    setExpandedConvId(null);
    setExpandedMessages([]);
    setIsImportDialogOpen(true);
    const wfs = await getAllWorkflows();
    setWorkflows(wfs ?? []);
    loadConversations(0, "");
  };

  const handleWorkflowFilterChange = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setConvPage(0);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(0, workflowId);
  };

  const handleConvPageChange = (next: number) => {
    setConvPage(next);
    setExpandedConvId(null);
    setExpandedMessages([]);
    loadConversations(next, selectedWorkflowId);
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
        {filteredSuites.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
            <Database className="h-12 w-12 text-gray-400" />
            <h3 className="font-medium text-lg">No datasets found</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              {searchQuery ? "Try adjusting your search query or " : ""}
              create your first dataset.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredSuites.map((suite) => (
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
                    <div className="text-lg font-semibold truncate">{suite.name}</div>
                    <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                      {suite.description || "No description"}
                    </p>
                  </button>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-xs font-bold text-black">
                      DATASET
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Import from Conversation"
                      onClick={() => openImportDialog(suite)}
                    >
                      <Import className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleOpenEditDataset(suite)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-500"
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
            ))}
          </div>
        )}
      </div>

      {/* Create dataset dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="w-[95vw] max-w-lg h-[90vh] max-h-[90vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Create Dataset</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            <Label className="text-xs">Dataset name</Label>
            <Input
              value={suiteName}
              onChange={(e) => setSuiteName(e.target.value)}
              placeholder="e.g. FAQ Gold Set"
            />
            <Label className="text-xs">Description</Label>
            <Textarea
              value={suiteDescription}
              onChange={(e) => setSuiteDescription(e.target.value)}
              rows={2}
            />
          </div>
          <DialogFooter className="border-t px-6 py-4 shrink-0">
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
        <DialogContent className="w-[95vw] max-w-lg h-[60vh] max-h-[60vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Edit Dataset</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            <Label className="text-xs">Dataset name</Label>
            <Input value={suiteName} onChange={(e) => setSuiteName(e.target.value)} />
            <Label className="text-xs">Description</Label>
            <Textarea
              value={suiteDescription}
              onChange={(e) => setSuiteDescription(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter className="border-t px-6 py-4 shrink-0">
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
        <DialogContent className="w-[95vw] max-w-2xl h-[80vh] max-h-[80vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>
              Import into "{importTargetSuite?.name}"
            </DialogTitle>
          </DialogHeader>

          <div className="px-6 pb-2 shrink-0">
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
        description={`This action cannot be undone. This will permanently delete dataset "${datasetToDelete?.name}".`}
      />
    </PageLayout>
  );
};

export default DatasetsPage;