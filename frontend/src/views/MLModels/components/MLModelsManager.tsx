import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";
import { Brain, ChevronLeft, FileCode, Pencil, Trash2 } from "lucide-react";

import { PageLayout } from "@/components/PageLayout";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FormField } from "@/components/ui/form-field";
import { Label } from "@/components/label";
import { TagsFieldInput } from "@/components/TagsFieldInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ListErrorState } from "@/components/ListErrorState";
import { PageListSkeleton } from "@/components/skeletons";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

import { MLModel } from "@/interfaces/ml-model.interface";
import {
  createMLModel,
  deleteMLModel,
  getAllMLModels,
  updateMLModel,
  uploadModelFile,
} from "@/services/mlModels";
import { extractErrorMessage } from "@/helpers/apiError";
import { MLModelType, MODEL_TYPE_OPTIONS, modelTypeLabel } from "../helpers/modelTypes";
import { ModelFilePicker } from "./ModelFilePicker";

const ALL_TYPES = "all";
const MODELS_QUERY_KEY = ["ml-models"];

interface FormValues {
  name: string;
  description: string;
  model_type: MLModelType;
  target_variable: string;
  features: string[];
  pkl_file: string | null;
  pkl_file_id: string | null;
  pendingFile: File | null;
}

type FormErrors = Partial<Record<keyof FormValues, string>>;

const emptyForm = (): FormValues => ({
  name: "",
  description: "",
  model_type: "xgboost",
  target_variable: "",
  features: [],
  pkl_file: null,
  pkl_file_id: null,
  pendingFile: null,
});

const formFromModel = (model: MLModel): FormValues => ({
  name: model.name ?? "",
  description: model.description ?? "",
  model_type: model.model_type,
  target_variable: model.target_variable ?? "",
  features: model.features ?? [],
  pkl_file: model.pkl_file ?? null,
  pkl_file_id: model.pkl_file_id ?? null,
  pendingFile: null,
});

/** Left-hand caption column of a form section (title + explanation). */
const SectionIntro: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <div>
    <h3 className="text-lg font-semibold">{title}</h3>
    <p className="mt-1 text-sm text-muted-foreground">{children}</p>
  </div>
);

const MLModelsManager: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>(ALL_TYPES);

  const [showForm, setShowForm] = useState(false);
  const [editingItem, setEditingItem] = useState<MLModel | null>(null);
  const [values, setValues] = useState<FormValues>(emptyForm);
  // Set when the form was opened from a model's detail page, so leaving the form
  // (via the back arrow or after saving) returns there instead of to the list.
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSaving, setIsSaving] = useState(false);

  const [modelToDelete, setModelToDelete] = useState<MLModel | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const {
    data: models = [],
    isPending,
    isError,
    refetch,
  } = useQuery({
    queryKey: MODELS_QUERY_KEY,
    queryFn: getAllMLModels,
  });

  const filteredItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return models.filter((model) => {
      const matchesType = typeFilter === ALL_TYPES || model.model_type === typeFilter;
      const matchesQuery =
        !query ||
        model.name?.toLowerCase().includes(query) ||
        model.description?.toLowerCase().includes(query);
      return matchesType && matchesQuery;
    });
  }, [models, searchQuery, typeFilter]);

  const setField = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  };

  const openCreateForm = () => {
    setReturnTo(null);
    setEditingItem(null);
    setValues(emptyForm());
    setErrors({});
    setShowForm(true);
  };

  const openEditForm = (model: MLModel, from?: string) => {
    setReturnTo(from ?? null);
    setEditingItem(model);
    setValues(formFromModel(model));
    setErrors({});
    setShowForm(true);
  };

  // The detail page's "Edit" action routes back here with the model to edit, so
  // editing always happens on this full page rather than in a second surface.
  const editModelId = (location.state as { editModelId?: string } | null)?.editModelId;
  useEffect(() => {
    if (!editModelId || models.length === 0) return;
    const target = models.find((model) => model.id === editModelId);
    if (target) openEditForm(target, `/ml-models/${target.id}`);
    navigate(location.pathname, { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editModelId, models]);

  const closeForm = () => {
    const origin = returnTo;
    setShowForm(false);
    setEditingItem(null);
    setValues(emptyForm());
    setErrors({});
    setReturnTo(null);
    if (origin) navigate(origin);
  };

  const validate = (): boolean => {
    const next: FormErrors = {};
    if (!values.name.trim()) next.name = "Name is required.";
    if (!values.description.trim()) next.description = "Description is required.";
    if (!values.model_type) next.model_type = "Model type is required.";
    if (!values.target_variable.trim())
      next.target_variable = "Target variable is required.";
    if (values.features.length === 0) next.features = "Add at least one feature.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      setIsSaving(true);

      let pklFile = values.pkl_file;
      let pklFileId = values.pkl_file_id;
      if (values.pendingFile) {
        const uploaded = await uploadModelFile(values.pendingFile);
        if (!uploaded?.file_path) throw new Error("File upload failed.");
        pklFile = uploaded.file_path;
        pklFileId = uploaded.file_id ?? null;
      }

      const payload = {
        name: values.name.trim(),
        description: values.description.trim(),
        model_type: values.model_type,
        target_variable: values.target_variable.trim(),
        features: values.features,
        pkl_file: pklFile,
        pkl_file_id: pklFileId,
      };

      if (editingItem) {
        await updateMLModel(editingItem.id, payload);
        void queryClient.invalidateQueries({ queryKey: ["ml-model", editingItem.id] });
        toast.success(`ML model "${payload.name}" updated.`);
      } else {
        await createMLModel({ ...payload, id: uuidv4() });
        toast.success(`ML model "${payload.name}" created.`);
      }

      closeForm();
      void refetch();
    } catch (err) {
      const status =
        (err as { status?: number })?.status ??
        (err as { response?: { status?: number } })?.response?.status;
      toast.error(
        status === 400
          ? "An ML model with this name already exists."
          : extractErrorMessage(
              err,
              `Failed to ${editingItem ? "update" : "create"} ML model.`
            )
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!modelToDelete) return;
    try {
      setIsDeleting(true);
      await deleteMLModel(modelToDelete.id);
      toast.success("ML model deleted successfully.");
      void refetch();
    } catch {
      toast.error("Failed to delete ML model.");
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setModelToDelete(null);
    }
  };

  if (showForm) {
    return (
      <PageLayout>
        <div className="flex items-center">
          <Button variant="ghost" size="icon" onClick={closeForm} className="mr-2">
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">
            {editingItem ? "Edit ML Model" : "New ML Model"}
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="divide-y rounded-lg border bg-card dark:bg-zinc-900">
            {/* Basic information */}
            <div className="grid grid-cols-1 gap-6 p-6 md:grid-cols-3">
              <SectionIntro title="Basic Information">
                What this model is and what it predicts.
              </SectionIntro>

              <div className="space-y-6 md:col-span-2">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField id="name" label="Name" error={errors.name}>
                    <Input
                      id="name"
                      value={values.name}
                      onChange={(e) => setField("name", e.target.value)}
                      placeholder="Name for this ML model"
                    />
                  </FormField>

                  <FormField id="model_type" label="Model Type" error={errors.model_type}>
                    <Select
                      value={values.model_type}
                      onValueChange={(value) => setField("model_type", value as MLModelType)}
                    >
                      <SelectTrigger id="model_type">
                        <SelectValue placeholder="Select model type" />
                      </SelectTrigger>
                      <SelectContent>
                        {MODEL_TYPE_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormField>
                </div>

                <FormField id="description" label="Description" error={errors.description}>
                  <Textarea
                    id="description"
                    value={values.description}
                    onChange={(e) => setField("description", e.target.value)}
                    placeholder="Brief description of this ML model"
                    rows={3}
                  />
                </FormField>

                <FormField
                  id="target_variable"
                  label="Target Variable"
                  error={errors.target_variable}
                >
                  <Input
                    id="target_variable"
                    value={values.target_variable}
                    onChange={(e) => setField("target_variable", e.target.value)}
                    placeholder="e.g., price, category, churn"
                  />
                </FormField>

                <div>
                  <Label className="text-sm font-medium">Model File (.pkl)</Label>
                  <div className="mt-1.5">
                    <ModelFilePicker
                      pendingFile={values.pendingFile}
                      existingPath={values.pkl_file}
                      existingFileId={values.pkl_file_id}
                      modelName={values.name}
                      onSelect={(file) => setField("pendingFile", file)}
                      onRemoveExisting={() =>
                        setValues((prev) => ({ ...prev, pkl_file: null, pkl_file_id: null }))
                      }
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Features */}
            <div className="grid grid-cols-1 gap-6 p-6 md:grid-cols-3">
              <SectionIntro title="Features">
                The input columns the model expects, in the order it was trained on.
              </SectionIntro>

              <div className="md:col-span-2">
                <FormField id="features" label="Features" error={errors.features}>
                  <TagsFieldInput
                    id="features"
                    value={values.features}
                    placeholder="Type a feature and press Enter"
                    onChange={(next) => setField("features", next)}
                  />
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {values.features.length > 0
                      ? `${values.features.length} feature${
                          values.features.length !== 1 ? "s" : ""
                        } defined`
                      : "Press Enter or comma to add each feature. Paste a comma-separated list to add several at once."}
                  </p>
                </FormField>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={closeForm}>
              Cancel
            </Button>
            <Button type="submit" loading={isSaving}>
              {editingItem ? "Update ML Model" : "Create ML Model"}
            </Button>
          </div>
        </form>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <PageHeader
        title="ML Models"
        subtitle="Model definitions your workflows can train and run inference against."
        filters={
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-full bg-card sm:w-44" aria-label="Filter by model type">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_TYPES}>All types</SelectItem>
              {MODEL_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search ML models..."
        actionButtonText="Add New"
        onActionClick={openCreateForm}
      />

      <div className="overflow-hidden rounded-lg border bg-card dark:bg-zinc-900">
        {isPending ? (
          <PageListSkeleton variant="rich" bordered={false} />
        ) : isError ? (
          <ListErrorState
            title="Couldn't load ML models"
            message="Something went wrong while loading your ML models."
            onRetry={() => void refetch()}
          />
        ) : filteredItems.length === 0 ? (
          <ListEmptyState
            icon={<Brain className="h-12 w-12 text-muted-foreground" />}
            title={searchQuery ? "No ML models found" : "No ML models yet"}
            description={
              searchQuery
                ? "Try adjusting your search query or filters."
                : "ML models let you configure and run inference pipelines. Create your first ML model to get started."
            }
            action={
              !searchQuery ? (
                <Button onClick={openCreateForm} className="rounded-full">
                  Create your first ML model
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="divide-y divide-border">
            {filteredItems.map((item) => (
              <div
                key={item.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/ml-models/${item.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate(`/ml-models/${item.id}`);
                  }
                }}
                className="cursor-pointer px-4 py-4 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-6"
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex flex-1 flex-col space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="break-words text-base font-semibold sm:text-lg">
                        {item.name}
                      </h4>
                      <span className="inline-flex items-center rounded-md bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-800 dark:bg-blue-500/20 dark:text-blue-400">
                        {modelTypeLabel(item.model_type)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                    <div className="mt-1 flex flex-wrap gap-3 text-sm text-muted-foreground">
                      <span>
                        <strong>Target:</strong> {item.target_variable}
                      </span>
                      <span>
                        <strong>Features:</strong> {item.features?.length ?? 0}
                      </span>
                      {(item.pkl_file || !!item.pkl_file_id) && (
                        <span className="flex items-center gap-1">
                          <FileCode className="h-4 w-4" />
                          Model file uploaded
                        </span>
                      )}
                    </div>
                  </div>
                  <div
                    className="flex w-full justify-end gap-2 md:w-auto"
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      aria-label={`Edit ${item.name}`}
                      onClick={() => openEditForm(item)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-500"
                      aria-label={`Delete ${item.name}`}
                      onClick={() => {
                        setModelToDelete(item);
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

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={modelToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the ML model "${modelToDelete?.name}", along with its pipeline configurations and run history.`}
      />
    </PageLayout>
  );
};

export default MLModelsManager;
