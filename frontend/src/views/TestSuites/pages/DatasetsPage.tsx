import React, { useEffect, useState } from "react";
import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import {
  createTestSuite,
  deleteTestSuite,
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
import { Plus, Database, Pencil, Trash2 } from "lucide-react";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";

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

  useEffect(() => {
    const load = async () => {
      const suiteData = await listTestSuites();
      setSuites(suiteData ?? []);
    };
    load();
  }, []);

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
      if (created.id) {
        navigate(`/tests/datasets/${created.id}`);
      }
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
    setSuites((prev) =>
      prev.map((suite) => (suite.id === editingDatasetId ? updated : suite)),
    );
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
      setSuites((prev) => prev.filter((suite) => suite.id !== datasetToDelete.id));
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setDatasetToDelete(null);
    }
  };

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
                      <div className="text-lg font-semibold truncate">
                        {suite.name}
                      </div>
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
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateDataset}
              disabled={!suiteName.trim()}
            >
              Create Dataset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="w-[95vw] max-w-lg h-[60vh] max-h-[60vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
            <DialogTitle>Edit Dataset</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 flex-1 min-h-0 overflow-y-auto">
            <Label className="text-xs">Dataset name</Label>
            <Input
              value={suiteName}
              onChange={(e) => setSuiteName(e.target.value)}
            />
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

