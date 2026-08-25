import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Brain, Loader2, Pencil, Plus, RefreshCcw, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ListEmptyState } from "@/components/ListEmptyState";
import { extractErrorMessage } from "@/helpers/apiError";
import {
  createLlmModelCatalogEntry,
  deleteLlmModelCatalogEntry,
  getLlmModelCatalog,
  getLlmModelCatalogProviders,
  updateLlmModelCatalogEntry,
} from "@/services/llmModelCatalog";
import type {
  LlmModelCatalogEntry,
  LlmModelCatalogProvider,
} from "@/interfaces/llmModelCatalog.interface";

interface LlmModelCatalogDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ModelForm {
  provider_key: string;
  model_key: string;
  label: string;
  is_active: boolean;
}

const EMPTY_FORM: ModelForm = {
  provider_key: "",
  model_key: "",
  label: "",
  is_active: true,
};

export function LlmModelCatalogDialog({
  open,
  onOpenChange,
}: LlmModelCatalogDialogProps) {
  const [rows, setRows] = useState<LlmModelCatalogEntry[]>([]);
  const [providers, setProviders] = useState<LlmModelCatalogProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<ModelForm | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [rowToDelete, setRowToDelete] = useState<LlmModelCatalogEntry | null>(
    null
  );
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [entries, providerTypes] = await Promise.all([
        getLlmModelCatalog(),
        getLlmModelCatalogProviders(),
      ]);
      setRows(entries);
      setProviders(providerTypes);
    } catch {
      toast.error("Could not load the model catalog.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const providerName = useCallback(
    (key: string) =>
      providers.find((p) => p.provider_key === key)?.name ?? key,
    [providers]
  );

  /** Built-in ids for the provider currently selected in the form. */
  const builtinKeysForForm = useMemo(() => {
    if (!form?.provider_key) return [] as string[];
    return (
      providers.find((p) => p.provider_key === form.provider_key)
        ?.builtin_model_keys ?? []
    );
  }, [form?.provider_key, providers]);

  const collidesWithBuiltin =
    !editingId &&
    !!form?.model_key &&
    builtinKeysForForm.includes(form.model_key.trim());

  const closeForm = () => {
    setForm(null);
    setEditingId(null);
    setFormError(null);
  };

  const openCreateForm = () => {
    setEditingId(null);
    setFormError(null);
    setForm({ ...EMPTY_FORM });
  };

  const openEditForm = (row: LlmModelCatalogEntry) => {
    setEditingId(row.id);
    setFormError(null);
    setForm({
      provider_key: row.provider_key,
      model_key: row.model_key,
      label: row.label,
      is_active: row.is_active === 1,
    });
  };

  const submitForm = async () => {
    if (!form) return;
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        await updateLlmModelCatalogEntry(editingId, {
          label: form.label.trim(),
          is_active: form.is_active ? 1 : 0,
        });
        toast.success("Model updated.");
      } else {
        await createLlmModelCatalogEntry({
          provider_key: form.provider_key,
          model_key: form.model_key.trim(),
          label: form.label.trim(),
          is_active: form.is_active ? 1 : 0,
        });
        toast.success("Model added.");
      }
      closeForm();
      await load();
    } catch (err) {
      setFormError(extractErrorMessage(err, "Could not save this model."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!rowToDelete) return;
    setDeleting(true);
    try {
      await deleteLlmModelCatalogEntry(rowToDelete.id);
      toast.success("Model removed.");
      setDeleteDialogOpen(false);
      setRowToDelete(null);
      await load();
    } catch {
      toast.error("Could not delete this model.");
    } finally {
      setDeleting(false);
    }
  };

  const canSubmit =
    !!form &&
    !!form.label.trim() &&
    (!!editingId || (!!form.provider_key && !!form.model_key.trim()));

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) {
            setDeleteDialogOpen(false);
            setRowToDelete(null);
            closeForm();
          }
          onOpenChange(next);
        }}
      >
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col gap-4 z-50">
          <DialogHeader>
            <DialogTitle>LLM models</DialogTitle>
            <DialogDescription>
              Add models that aren't in the built-in list yet, so they can be
              picked when creating an LLM provider. Built-in models stay
              available and are never changed from here.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={openCreateForm}>
              <Plus className="w-4 h-4 mr-2" />
              Add model
            </Button>
            <Button
              className="ml-auto"
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void load()}
              disabled={loading}
            >
              <RefreshCcw
                className={"w-2 h-2 " + (loading ? "animate-spin" : "")}
              />
              {loading ? "Refreshing..." : "Refresh"}
            </Button>
          </div>

          {form && (
            <div className="rounded-md border p-3 space-y-3 shrink-0">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Provider</span>
                  <Select
                    value={form.provider_key}
                    disabled={!!editingId || saving}
                    onValueChange={(value) =>
                      setForm({ ...form, provider_key: value })
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map((p) => (
                        <SelectItem key={p.provider_key} value={p.provider_key}>
                          {p.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">Model ID</span>
                  <Input
                    value={form.model_key}
                    disabled={!!editingId || saving}
                    placeholder="llama-3.3-70b-versatile"
                    onChange={(e) =>
                      setForm({ ...form, model_key: e.target.value })
                    }
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">
                    Display name
                  </span>
                  <Input
                    value={form.label}
                    disabled={saving}
                    placeholder="Llama 3.3 70B Versatile"
                    onChange={(e) => setForm({ ...form, label: e.target.value })}
                  />
                </label>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  id="catalog-model-active"
                  checked={form.is_active}
                  disabled={saving}
                  onCheckedChange={(checked) =>
                    setForm({ ...form, is_active: checked })
                  }
                />
                <label
                  htmlFor="catalog-model-active"
                  className="text-sm text-muted-foreground"
                >
                  Selectable when creating a provider
                </label>
              </div>

              {collidesWithBuiltin && (
                <p className="text-xs text-amber-600 dark:text-amber-500">
                  This model ID is already built in for{" "}
                  {providerName(form.provider_key)}. The built-in entry is what
                  the provider form will use.
                </p>
              )}
              {editingId && (
                <p className="text-xs text-muted-foreground">
                  Provider and model ID are fixed. Delete and re-add to move an
                  entry, which keeps its cost rate key intact.
                </p>
              )}
              {formError && (
                <p className="text-sm text-destructive">{formError}</p>
              )}

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  disabled={saving || !canSubmit}
                  onClick={() => void submitForm()}
                >
                  {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                  {editingId ? "Save changes" : "Add model"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={saving}
                  onClick={closeForm}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          <div className="flex-1 min-h-0 overflow-auto rounded-md border">
            {loading ? (
              <div className="flex items-center justify-center p-8 text-muted-foreground">
                <Loader2 className="w-6 h-6 animate-spin mr-2" />
                Loading…
              </div>
            ) : rows.length === 0 ? (
              <ListEmptyState
                icon={<Brain className="h-12 w-12 text-muted-foreground" />}
                title="No extra models yet"
                description="The built-in models for every provider type are already available. Add a model here when a new one is released."
                action={
                  !form ? (
                    <Button
                      onClick={openCreateForm}
                      className="rounded-full flex items-center gap-2"
                    >
                      <Plus className="h-4 w-4" />
                      Add model
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model ID</TableHead>
                    <TableHead>Display name</TableHead>
                    <TableHead className="whitespace-nowrap">Status</TableHead>
                    <TableHead className="w-[104px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-sm">
                        {providerName(r.provider_key)}
                      </TableCell>
                      <TableCell
                        className="font-mono text-xs max-w-[240px] truncate"
                        title={r.model_key}
                      >
                        {r.model_key}
                      </TableCell>
                      <TableCell className="text-sm">{r.label}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {r.is_shadowed_by_builtin
                          ? "Built-in"
                          : r.is_active === 1
                          ? "Active"
                          : "Hidden"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                          title="Edit model"
                          onClick={() => openEditForm(r)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                          title="Delete model"
                          onClick={() => {
                            setRowToDelete(r);
                            setDeleteDialogOpen(true);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        isOpen={deleteDialogOpen}
        onOpenChange={(next) => {
          setDeleteDialogOpen(next);
          if (!next) setRowToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        isInProgress={deleting}
        title="Delete model?"
        description={
          rowToDelete
            ? `This removes ${rowToDelete.model_key} from the ${providerName(
                rowToDelete.provider_key
              )} model list. Providers already using it keep working and keep showing it.`
            : undefined
        }
      />
    </>
  );
}
