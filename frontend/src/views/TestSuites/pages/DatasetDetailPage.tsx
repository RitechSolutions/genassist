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
import { ChevronLeft, Plus, ListOrdered, Pencil, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import JsonViewer from "@/components/JsonViewer";
import { JsonInput } from "@/components/JsonInput";
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
  const [isInputValid, setIsInputValid] = useState(false);
  const [isOutputValid, setIsOutputValid] = useState(true);
  const [parsedInput, setParsedInput] = useState<unknown>(undefined);
  const [parsedOutput, setParsedOutput] = useState<unknown>(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingCase, setEditingCase] = useState<TestCase | null>(null);
  const [editInput, setEditInput] = useState("");
  const [editExpectedOutput, setEditExpectedOutput] = useState("");
  const [isEditInputValid, setIsEditInputValid] = useState(false);
  const [isEditOutputValid, setIsEditOutputValid] = useState(true);
  const [parsedEditInput, setParsedEditInput] = useState<unknown>(undefined);
  const [parsedEditOutput, setParsedEditOutput] = useState<unknown>(undefined);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState<TestCase | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [expandedRecords, setExpandedRecords] = useState<Set<string>>(new Set());

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
    if (!datasetId || !isInputValid) return;

    const created = await addTestCase(datasetId, {
      input_data: parsedInput as Record<string, unknown>,
      expected_output: parsedOutput as Record<string, unknown> | undefined,
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
    if (!editingCase?.id || !isEditInputValid) return;

    const updated = await updateTestCase(editingCase.id, {
      input_data: (parsedEditInput as Record<string, unknown>) ?? editingCase.input_data,
      expected_output: parsedEditOutput as Record<string, unknown> | undefined,
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

  const getPreviewText = (data: Record<string, unknown> | undefined, maxLength = 60): string => {
    if (!data) return "—";
    const str = JSON.stringify(data);
    if (str.length <= maxLength) return str;
    return str.slice(0, maxLength) + "…";
  };

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
          {/* Left Column: Add Record Form */}
          <div className="bg-white rounded-lg border p-4 space-y-3">
            <h2 className="text-lg font-semibold">Add Dataset Record</h2>
            <JsonInput
              value={caseInput}
              onChange={setCaseInput}
              onValidChange={(valid, parsed) => {
                setIsInputValid(valid);
                setParsedInput(parsed);
              }}
              label="Input"
              placeholder='{"message":"What are your support hours?"}'
              rows={6}
            />
            <JsonInput
              value={caseExpectedOutput}
              onChange={setCaseExpectedOutput}
              onValidChange={(valid, parsed) => {
                setIsOutputValid(valid);
                setParsedOutput(parsed);
              }}
              label="Expected Output"
              placeholder='{"text":"We are available 24/7"}'
              rows={6}
              allowEmpty
            />
            <Button onClick={handleAddCase} disabled={!isInputValid}>
              <Plus className="h-4 w-4 mr-2" />
              Add Record
            </Button>
          </div>

          {/* Right Column: Records List */}
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
                  <div key={entry.id} className="border rounded p-3">
                    <div
                      className="flex items-center justify-between gap-2 cursor-pointer"
                      onClick={() => entry.id && toggleRecordExpansion(entry.id)}
                    >
                      <div className="flex items-center gap-2 text-gray-600 flex-1 min-w-0">
                        <button type="button" className="text-gray-400 hover:text-gray-600">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                        <ListOrdered className="h-3.5 w-3.5 shrink-0" />
                        <span className="text-sm font-medium shrink-0">#{entry.id?.slice(-4)}</span>
                        {!isExpanded && (
                          <span className="text-xs text-gray-400 font-mono truncate ml-2">
                            {getPreviewText(entry.input_data)}
                          </span>
                        )}
                      </div>
                      <div
                        className="flex items-center gap-1 shrink-0"
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
                      <div className="mt-3 ml-6 space-y-2">
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

        {/* Edit Dialog */}
        <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
          <DialogContent className="w-[95vw] max-w-2xl h-[80vh] max-h-[80vh] overflow-hidden p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
              <DialogTitle>Edit Record #{editingCase?.id?.slice(-4) ?? ""}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
              <JsonInput
                value={editInput}
                onChange={setEditInput}
                onValidChange={(valid, parsed) => {
                  setIsEditInputValid(valid);
                  setParsedEditInput(parsed);
                }}
                label="Input"
                rows={8}
              />
              <JsonInput
                value={editExpectedOutput}
                onChange={setEditExpectedOutput}
                onValidChange={(valid, parsed) => {
                  setIsEditOutputValid(valid);
                  setParsedEditOutput(parsed);
                }}
                label="Expected Output"
                rows={8}
                allowEmpty
              />
            </div>
            <DialogFooter className="border-t px-6 py-4 shrink-0">
              <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveEditCase} disabled={!isEditInputValid}>
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
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
