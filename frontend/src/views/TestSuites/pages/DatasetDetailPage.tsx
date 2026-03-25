import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import {
  addTestCase,
  deleteTestCase,
  getTestSuite,
  importCasesFromConversation,
  listTestCases,
  updateTestCase,
} from "@/services/testSuites";
import { TestCase, TestSuite } from "@/interfaces/testSuite.interface";
import { Button } from "@/components/button";
import { Textarea } from "@/components/textarea";
import { Label } from "@/components/label";
import { ChevronLeft, Plus, ListOrdered, Pencil, Trash2, MessageSquareQuote, ChevronRight, ChevronDown } from "lucide-react";
import JsonViewer from "@/components/JsonViewer";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchConversationById, fetchTranscripts } from "@/services/transcripts";
import type { BackendTranscript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { getAllWorkflows } from "@/services/workflows";
import type { Workflow } from "@/interfaces/workflow.interface";

const PAGE_SIZE = 10;

const DatasetDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { datasetId } = useParams<{ datasetId: string }>();
  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [caseInput, setCaseInput] = useState("");
  const [caseExpectedOutput, setCaseExpectedOutput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [editInput, setEditInput] = useState("");
  const [editExpectedOutput, setEditExpectedOutput] = useState("");
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<TestCase | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Import from conversation dialog state
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
  const [conversations, setConversations] = useState<BackendTranscript[]>([]);
  const [convPage, setConvPage] = useState(0);
  const [convTotal, setConvTotal] = useState(0);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [importingConvId, setImportingConvId] = useState<string | null>(null);
  const [pendingImportConvs, setPendingImportConvs] = useState<BackendTranscript[]>([]);
  const importSucceededRef = React.useRef(false);
  const [selectedConvIds, setSelectedConvIds] = useState<Set<string>>(new Set());
  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<TranscriptEntry[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

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
    const msgs = (conv?.messages ?? []) as TranscriptEntry[];
    setExpandedMessages(msgs);
    setIsLoadingMessages(false);
  };

  const loadConversations = useCallback(async (page: number, workflowId: string) => {
    setIsLoadingConversations(true);
    const result = await fetchTranscripts({
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      workflow_id: workflowId || undefined,
      conversation_status: ["finalized"],
    });
    setConversations(result.items);
    setConvTotal(result.total);
    setIsLoadingConversations(false);
  }, []);

  const openImportDialog = async () => {
    setIsImportDialogOpen(true);
    setConvPage(0);
    const wfs = await getAllWorkflows();
    setWorkflows(wfs ?? []);
    loadConversations(0, selectedWorkflowId);
  };

  const handleWorkflowFilterChange = (workflowId: string) => {
    setSelectedWorkflowId(workflowId);
    setConvPage(0);
    setExpandedConvId(null);
    setExpandedMessages([]);
    setSelectedConvIds(new Set());
    loadConversations(0, workflowId);
  };

  const handleConvPageChange = (next: number) => {
    setConvPage(next);
    setExpandedConvId(null);
    setExpandedMessages([]);
    setSelectedConvIds(new Set());
    loadConversations(next, selectedWorkflowId);
  };

  const toggleSelectConv = (id: string) => {
    setSelectedConvIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const allSelected = conversations.length > 0 && conversations.every((c) => selectedConvIds.has(c.id));

  const toggleSelectAll = () => {
    setSelectedConvIds(allSelected ? new Set() : new Set(conversations.map((c) => c.id)));
  };

  const handleImportFromConversation = async () => {
    if (!datasetId || pendingImportConvs.length === 0) return;
    importSucceededRef.current = true;
    const allCreated: TestCase[] = [];
    for (const conv of pendingImportConvs) {
      setImportingConvId(conv.id);
      const created = await importCasesFromConversation(datasetId, conv.id);
      if (created && created.length > 0) allCreated.push(...created);
    }
    if (allCreated.length > 0) setCases((prev) => [...allCreated, ...prev]);
    setImportingConvId(null);
    setSelectedConvIds(new Set());
    setPendingImportConvs([]);
  };

  useEffect(() => {
    const load = async () => {
      if (!datasetId) return;
      const [suiteData, caseData] = await Promise.all([
        getTestSuite(datasetId),
        listTestCases(datasetId),
      ]);
      setSuite(suiteData ?? null);
      setCases(caseData ?? []);
    };
    load();
  }, [datasetId]);

  const handleAddCase = async () => {
    if (!datasetId || !caseInput.trim()) return;

    let inputData: Record<string, unknown>;
    let expectedOutput: Record<string, unknown> | undefined;

    try {
      inputData = JSON.parse(caseInput);
    } catch {
      inputData = { message: caseInput };
    }

    if (caseExpectedOutput.trim()) {
      try {
        expectedOutput = JSON.parse(caseExpectedOutput);
      } catch {
        expectedOutput = { value: caseExpectedOutput };
      }
    }

    const created = await addTestCase(datasetId, {
      input_data: inputData,
      expected_output: expectedOutput,
    });

    if (created) {
      setCases((prev) => [created, ...prev]);
      setCaseInput("");
      setCaseExpectedOutput("");
    }
  };

  const openEditDialog = (entry: TestCase) => {
    setEditingCase(entry);
    setEditInput(JSON.stringify(entry.input_data ?? {}, null, 2));
    setEditExpectedOutput(
      entry.expected_output ? JSON.stringify(entry.expected_output, null, 2) : "",
    );
    setIsEditDialogOpen(true);
  };

  const handleSaveEditCase = async () => {
    if (!editingCase?.id) return;

    let inputData: Record<string, unknown> | undefined;
    let expectedOutput: Record<string, unknown> | undefined;

    try {
      inputData = editInput.trim()
        ? (JSON.parse(editInput) as Record<string, unknown>)
        : undefined;
    } catch {
      inputData = { message: editInput };
    }

    if (editExpectedOutput.trim()) {
      try {
        expectedOutput = JSON.parse(
          editExpectedOutput,
        ) as Record<string, unknown>;
      } catch {
        expectedOutput = { value: editExpectedOutput };
      }
    }

    const updated = await updateTestCase(editingCase.id, {
      input_data: inputData ?? editingCase.input_data,
      expected_output: expectedOutput,
    });

    setCases((prev) =>
      prev.map((c) => (c.id === editingCase.id ? updated : c)),
    );
    setIsEditDialogOpen(false);
    setEditingCase(null);
  };

  const handleDeleteCase = async () => {
    if (!caseToDelete?.id) return;
    setIsDeleting(true);
    try {
      await deleteTestCase(caseToDelete.id);
      setCases((prev) => prev.filter((c) => c.id !== caseToDelete.id));
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setCaseToDelete(null);
    }
  };

  const filteredCases = cases.filter((entry) => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return true;
    const inputText = JSON.stringify(entry.input_data ?? {}).toLowerCase();
    const expectedText = JSON.stringify(entry.expected_output ?? {}).toLowerCase();
    return inputText.includes(query) || expectedText.includes(query);
  });

  return (
    <PageLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={() => navigate("/tests/datasets")}>
            <ChevronLeft className="h-4 w-4 mr-2" />
            Back to Datasets
          </Button>
          {suite?.name && (
            <div className="text-right">
              <h1 className="text-xl font-semibold text-gray-900">{suite.name}</h1>
              {suite.description && (
                <p className="text-xs text-gray-500">{suite.description}</p>
              )}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-white rounded-lg border p-4 space-y-3">
            <h2 className="text-lg font-semibold">Add Dataset Record</h2>
            <Label className="text-xs">Input</Label>
            <Textarea
              value={caseInput}
              onChange={(e) => setCaseInput(e.target.value)}
              rows={6}
              placeholder='{"message":"What are your support hours?"}'
              className="font-mono text-xs"
            />
            <Label className="text-xs">Expected Output</Label>
            <Textarea
              value={caseExpectedOutput}
              onChange={(e) => setCaseExpectedOutput(e.target.value)}
              rows={6}
              placeholder='{"text":"We are available 24/7"}'
              className="font-mono text-xs"
            />
            <div className="flex gap-2">
              <Button onClick={handleAddCase} disabled={!caseInput.trim()}>
                <Plus className="h-4 w-4 mr-2" />
                Add Record
              </Button>
              <Button variant="outline" onClick={openImportDialog}>
                <MessageSquareQuote className="h-4 w-4 mr-2" />
                Import from Conversation
              </Button>
            </div>
          </div>

          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Dataset Records</h2>
              <span className="inline-flex items-center text-xs rounded-full bg-gray-100 px-3 py-1">
                {cases.length} total
              </span>
            </div>
            <SearchInput
              placeholder="Search records..."
              value={searchQuery}
              onChange={setSearchQuery}
              className="mb-3"
            />
            <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
              {filteredCases.map((entry) => (
                <div key={entry.id} className="border rounded p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-gray-600">
                      <ListOrdered className="h-3.5 w-3.5" />
                      <span className="text-sm font-medium">#{entry.id?.slice(-4)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => openEditDialog(entry)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-500"
                        onClick={() => {
                          setCaseToDelete(entry);
                          setIsDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mb-1">Input</div>
                  <JsonViewer
                    data={(entry.input_data ?? {}) as unknown as never}
                  />
                  <div className="text-xs text-gray-500 mt-2 mb-1">
                    Expected Output
                  </div>
                  <JsonViewer
                    data={(entry.expected_output ?? {}) as unknown as never}
                  />
                </div>
              ))}
              {filteredCases.length === 0 && (
                <div className="text-sm text-gray-400">No records found.</div>
              )}
            </div>
          </div>
        </div>

        <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
          <DialogContent className="w-[95vw] max-w-2xl h-[80vh] max-h-[80vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
              <DialogTitle>
                Edit Record #{editingCase?.id?.slice(-4) ?? ""}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
              <Label className="text-xs">Input</Label>
              <Textarea
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                rows={8}
                className="font-mono text-xs"
              />
              <Label className="text-xs">Expected Output</Label>
              <Textarea
                value={editExpectedOutput}
                onChange={(e) => setEditExpectedOutput(e.target.value)}
                rows={8}
                className="font-mono text-xs"
              />
            </div>
            <DialogFooter className="border-t px-6 py-4 shrink-0">
              <Button
                variant="outline"
                onClick={() => setIsEditDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleSaveEditCase} disabled={!editInput.trim()}>
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <ConfirmDialog
          isOpen={isDeleteDialogOpen}
          onOpenChange={setIsDeleteDialogOpen}
          onConfirm={handleDeleteCase}
          isInProgress={isDeleting}
          itemName={`#${caseToDelete?.id?.slice(-4) || ""}`}
          description={`This will permanently delete this record from dataset "${suite?.name || ""}".`}
        />

        <ConfirmDialog
          isOpen={pendingImportConvs.length > 0}
          onOpenChange={(open) => {
            if (!open) {
              const succeeded = importSucceededRef.current;
              importSucceededRef.current = false;
              setPendingImportConvs([]);
              if (!succeeded) setIsImportDialogOpen(true);
            }
          }}
          onConfirm={handleImportFromConversation}
          isInProgress={!!importingConvId}
          title={
            pendingImportConvs.length === 1
              ? `Import from conversation #${pendingImportConvs[0].id.slice(-4)}`
              : `Import from ${pendingImportConvs.length} conversations`
          }
          description={
            pendingImportConvs.length === 1
              ? `This will import all Q&A pairs from conversation #${pendingImportConvs[0].id.slice(-4)} (${pendingImportConvs[0].word_count ?? 0} words) into dataset "${suite?.name ?? ""}".`
              : `This will import all Q&A pairs from ${pendingImportConvs.length} conversations (${pendingImportConvs.reduce((sum, c) => sum + (c.word_count ?? 0), 0)} total words) into dataset "${suite?.name ?? ""}".`
          }
          primaryButtonText="Import"
        />

        <Dialog open={isImportDialogOpen} onOpenChange={setIsImportDialogOpen}>
          <DialogContent className="w-[95vw] max-w-2xl h-[80vh] max-h-[80vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
              <DialogTitle>Import from Conversation</DialogTitle>
            </DialogHeader>

            <div className="px-6 pb-2 shrink-0">
              <Label className="text-xs mb-1 block">Filter by Workflow</Label>
              <select
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={selectedWorkflowId}
                onChange={(e) => handleWorkflowFilterChange(e.target.value)}
              >
                <option value="">All workflows</option>
                {workflows.map((wf) => (
                  <option key={wf.id} value={wf.id ?? ""}>
                    {wf.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-6">
              {isLoadingConversations ? (
                <div className="text-sm text-gray-400 py-4">Loading conversations…</div>
              ) : conversations.length === 0 ? (
                <div className="text-sm text-gray-400 py-4">No conversations found.</div>
              ) : (
                <div className="space-y-2 py-2">
                  <div className="flex items-center gap-2 px-1 pb-1 border-b">
                    <input
                      type="checkbox"
                      className="h-3.5 w-3.5 cursor-pointer"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                    />
                    <span className="text-xs text-gray-500">
                      {selectedConvIds.size > 0
                        ? `${selectedConvIds.size} selected`
                        : "Select all on this page"}
                    </span>
                  </div>

                  {conversations.map((conv) => {
                    const isExpanded = expandedConvId === conv.id;
                    const isSelected = selectedConvIds.has(conv.id);
                    return (
                      <div key={conv.id} className="border rounded overflow-hidden">
                        <div className="p-3 flex items-center justify-between gap-3">
                          <input
                            type="checkbox"
                            className="h-3.5 w-3.5 shrink-0 cursor-pointer"
                            checked={isSelected}
                            onChange={() => toggleSelectConv(conv.id)}
                          />
                          <button
                            className="flex items-center gap-2 min-w-0 text-left flex-1"
                            onClick={() => toggleExpandConversation(conv.id)}
                          >
                            <ChevronDown
                              className={`h-3.5 w-3.5 text-gray-400 shrink-0 transition-transform ${isExpanded ? "" : "-rotate-90"}`}
                            />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-foreground shrink-0">
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
                            disabled={importingConvId === conv.id}
                            onClick={() => {
                              setIsImportDialogOpen(false);
                              setPendingImportConvs([conv]);
                            }}
                          >
                            {importingConvId === conv.id ? "Importing…" : "Import"}
                          </Button>
                        </div>

                        {isExpanded && (
                          <div className="border-t bg-gray-50 px-3 py-2 max-h-60 overflow-y-auto space-y-1.5">
                            {isLoadingMessages ? (
                              <p className="text-xs text-gray-400">Loading messages…</p>
                            ) : expandedMessages.length === 0 ? (
                              <p className="text-xs text-gray-400">No messages found.</p>
                            ) : (
                              expandedMessages.map((msg, idx) => (
                                <div
                                  key={(msg as { id?: string }).id ?? idx}
                                  className={`flex gap-2 ${msg.speaker?.toLowerCase() === "agent" ? "justify-end" : "justify-start"}`}
                                >
                                  <div
                                    className={`max-w-[80%] rounded px-2.5 py-1.5 text-xs ${
                                      msg.speaker?.toLowerCase() === "agent"
                                        ? "bg-blue-100 text-blue-900"
                                        : "bg-white border text-gray-800"
                                    }`}
                                  >
                                    <span className="font-semibold capitalize block mb-0.5 opacity-60 text-[10px]">
                                      {msg.speaker}
                                    </span>
                                    {msg.text}
                                  </div>
                                </div>
                              ))
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
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {convTotal} conversation{convTotal !== 1 ? "s" : ""} total
                </span>
                {selectedConvIds.size > 0 && (
                  <Button
                    size="sm"
                    onClick={() => {
                      const selected = conversations.filter((c) => selectedConvIds.has(c.id));
                      setIsImportDialogOpen(false);
                      setPendingImportConvs(selected);
                    }}
                  >
                    Import Selected ({selectedConvIds.size})
                  </Button>
                )}
              </div>
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
                  disabled={(convPage + 1) * PAGE_SIZE >= convTotal}
                  onClick={() => handleConvPageChange(convPage + 1)}
                >
                  Next
                  <ChevronRight className="h-3.5 w-3.5 ml-1" />
                </Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </PageLayout>
  );
};

export default DatasetDetailPage;

