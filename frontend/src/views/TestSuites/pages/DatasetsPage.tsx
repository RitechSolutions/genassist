import React, {useEffect, useState} from "react";
import toast from "react-hot-toast";
import {PageLayout} from "@/components/PageLayout";
import {PageHeader} from "@/components/PageHeader";
import {
  createTestSuite,
  deleteTestSuite,
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
import {CRUDDialog} from "@/components/ui/crud-dialog";
import {
  ArrowRightLeft,
  Clock,
  Database,
  MessagesSquare,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import {ConfirmDialog} from "@/components/ConfirmDialog";
import {PageListSkeleton} from "@/components/skeletons";
import {EntityTitle} from "../components/EntityTitle";
import {countConversations} from "../helpers/datasetConversations";

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
  // Conversations and turns per suite, so a row says what its detail page does.
  const [suiteCounts, setSuiteCounts] = useState<
    Record<string, { conversations: number; turns: number }>
  >({});
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
      setIsLoading(true);
      try {
        const suiteData = await listTestSuites();
        setSuites(suiteData ?? []);
        // Load conversation and turn counts for each suite
        const counts: Record<string, { conversations: number; turns: number }> = {};
        await Promise.all(
          (suiteData ?? []).map(async (suite) => {
            if (suite.id) {
              const cases = (await listTestCases(suite.id)) ?? [];
              counts[suite.id] = {
                conversations: countConversations(cases),
                turns: cases.length,
              };
            }
          })
        );
        setSuiteCounts(counts);
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
        subtitle="Create reusable golden datasets and manage their conversations."
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
                : "Datasets hold the conversations you evaluate your AI agents against. Create your first dataset to get started."}
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
              const counts = (suite.id ? suiteCounts[suite.id] : null) ?? {
                conversations: 0,
                turns: 0,
              };
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
                      <EntityTitle>{suite.name}</EntityTitle>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
                        {suite.description || "No description"}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <MessagesSquare className="h-3 w-3" />
                          {counts.conversations} conversation
                          {counts.conversations !== 1 ? "s" : ""}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          {/* A turn is one exchange, so it reads as a
                              back-and-forth rather than as a message. */}
                          <ArrowRightLeft className="h-3 w-3" />
                          {counts.turns} turn{counts.turns !== 1 ? "s" : ""}
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
                placeholder="What this dataset covers"
                size="hint"
              />
            </div>
          </>
        )}
      </CRUDDialog>

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
