import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import {
  addTestCase,
  deleteTestCase,
  getTestSuite,
  listTestCases,
  updateTestCase,
} from "@/services/testSuites";
import { TestCase, TestSuite } from "@/interfaces/testSuite.interface";
import { Button } from "@/components/button";
import { SimpleTextarea as Textarea } from "@/components/ui/simpleTextarea";
import { Label } from "@/components/label";
import { ChevronLeft, ChevronDown, ChevronRight, Plus, ListOrdered, Pencil, Trash2 } from "lucide-react";
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
  const [expandedRecords, setExpandedRecords] = useState<Set<string>>(new Set());
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
      const [suiteData, caseData] = await Promise.all([
        getTestSuite(datasetId),
        listTestCases(datasetId),
      ]);
      setSuite(suiteData ?? null);
      const records = caseData ?? [];
      setCases(records);
      if (records.length > 0) {
        setExpandedRecords(new Set([records[0].id]));
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
      setCases((prev) => [...prev, created]);
      setExpandedRecords((prev) => new Set([...prev, created.id]));
      setNewestId(created.id);
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
        expectedOutput = JSON.parse(editExpectedOutput) as Record<string, unknown>;
      } catch {
        expectedOutput = { value: editExpectedOutput };
      }
    }

    const updated = await updateTestCase(editingCase.id, {
      input_data: inputData ?? editingCase.input_data,
      expected_output: expectedOutput,
    });

    setCases((prev) => prev.map((c) => (c.id === editingCase.id ? updated : c)));
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
            <Button onClick={handleAddCase} disabled={!caseInput.trim()}>
              <Plus className="h-4 w-4 mr-2" />
              Add Record
            </Button>
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
              {filteredCases.map((entry) => {
                const isExpanded = expandedRecords.has(entry.id ?? "");
                return (
                  <div key={entry.id} id={`record-${entry.id}`} className="border rounded p-3">
                    <div
                      className="flex items-center justify-between gap-2 cursor-pointer"
                      onClick={() => entry.id && toggleRecordExpansion(entry.id)}
                    >
                      <div className="flex items-center gap-2 text-gray-600">
                        <button type="button" className="text-gray-400 hover:text-gray-600">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                        <ListOrdered className="h-3.5 w-3.5" />
                        <span className="text-sm font-medium">#{entry.id?.slice(-4)}</span>
                      </div>
                      <div
                        className="flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
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
                    {isExpanded && (
                      <div className="mt-3 space-y-2">
                        <div className="text-xs text-gray-500 mb-1">Input</div>
                        <JsonViewer data={(entry.input_data ?? {}) as unknown as never} />
                        <div className="text-xs text-gray-500 mt-2 mb-1">Expected Output</div>
                        <JsonViewer data={(entry.expected_output ?? {}) as unknown as never} />
                      </div>
                    )}
                  </div>
                );
              })}
              {filteredCases.length === 0 && (
                <div className="text-sm text-gray-400">No records found.</div>
              )}
            </div>
          </div>
        </div>

        <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
          <DialogContent className="w-[95vw] max-w-2xl h-[80vh] max-h-[80vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
              <DialogTitle>Edit Record #{editingCase?.id?.slice(-4) ?? ""}</DialogTitle>
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
              <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
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
      </div>
    </PageLayout>
  );
};

export default DatasetDetailPage;