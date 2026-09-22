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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import {
  getLlmCostRates,
  importLlmCostRatesCsv,
  deleteLlmCostRate,
  exportLlmCostRatesCsv,
  createLlmCostRate,
  updateLlmCostRate,
} from "@/services/llmCostRates";
import type { LlmCostRate } from "@/interfaces/llmCostRate.interface";
import toast from "react-hot-toast";
import {
  Coins,
  Copy,
  Download,
  FileText,
  Loader2,
  Pencil,
  Plus,
  RefreshCcw,
  Trash2,
  Upload,
} from "lucide-react";
import { formatTimeAgo } from "@/helpers/formatters";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ListEmptyState } from "@/components/ListEmptyState";
import {
  changedCacheRates,
  serializeCacheRate,
  validateLlmCostRateForm,
  type LlmCostRateFieldErrors,
  type LlmCostRateFormValues,
} from "@/views/LlmProviders/helpers/llmCostRateValidation";

/** Header the import API requires (UTF-8). */
const CSV_TEMPLATE =
  "provider,model,input_per_1k,output_per_1k,cache_read_per_1k,cache_creation_per_1k";

/** Display-only placeholder keys prevent pasted data from overwriting rates. */
const CSV_EXAMPLE = `${CSV_TEMPLATE}
example-provider,example-model,0.00025,0.001,,
example-provider,example-model-cached,0.00025,0.001,0.000025,0
example-provider,_default,0.00025,0.001,,`;

interface LlmCostRatesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type RateForm = LlmCostRateFormValues;

const EMPTY_FORM: RateForm = {
  provider: "",
  model: "",
  input_per_1k: "",
  output_per_1k: "",
  cache_read_per_1k: "",
  cache_creation_per_1k: "",
};

function backendErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data as
    | { error?: string; detail?: unknown }
    | undefined;
  if (typeof data?.error === "string" && data.error) return data.error;
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) =>
        typeof d === "object" && d && "msg" in d
          ? String((d as { msg: string }).msg)
          : ""
      )
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return err instanceof Error ? err.message : fallback;
}

export function LlmCostRatesDialog({
  open,
  onOpenChange,
}: LlmCostRatesDialogProps) {
  const [rows, setRows] = useState<LlmCostRate[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [csvFormatOpen, setCsvFormatOpen] = useState(false);
  const [rowToDelete, setRowToDelete] = useState<LlmCostRate | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [form, setForm] = useState<RateForm | null>(null);
  const [editPrefill, setEditPrefill] = useState<RateForm | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<LlmCostRateFieldErrors>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLlmCostRates();
      setRows(data);
    } catch {
      toast.error("Could not load LLM cost rates.");
    } finally {
      await new Promise((resolve) => setTimeout(resolve, 200));
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      void load();
    }
  }, [open, load]);

  useEffect(() => {
    setPage(1);
  }, [open]);

  const totalRows = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const pagedRows = useMemo(() => {
    const start = (page - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [rows, page, pageSize]);

  const fromRow = totalRows === 0 ? 0 : (page - 1) * pageSize + 1;
  const toRow = totalRows === 0 ? 0 : Math.min(totalRows, page * pageSize);

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast.error("Please choose a .csv file.");
      return;
    }
    setUploading(true);
    try {
      const result = await importLlmCostRatesCsv(file);
      toast.success(
        `Imported: ${result.inserted} new, ${result.updated} updated.`
      );
      if (result.errors.length) {
        result.errors.slice(0, 5).forEach((msg) => toast.error(msg));
        if (result.errors.length > 5) {
          toast.error(`${result.errors.length - 5} more row errors…`);
        }
      }
      await load();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Upload failed."
      );
    } finally {
      setUploading(false);
    }
  };

  const copyCsvTemplate = () => {
    void navigator.clipboard.writeText(`${CSV_TEMPLATE}\n`);
    toast.success("CSV header copied to clipboard.");
  };

  const closeForm = () => {
    setForm(null);
    setEditPrefill(null);
    setEditingId(null);
    setFormError(null);
    setFieldErrors({});
  };

  const openCreateForm = () => {
    setEditingId(null);
    setFormError(null);
    setFieldErrors({});
    setEditPrefill(null);
    setForm({ ...EMPTY_FORM });
  };

  const openEditForm = (row: LlmCostRate) => {
    // Frozen so changedCacheRates can omit cache fields the user never touched
    const prefill: RateForm = {
      provider: row.provider_key,
      model: row.model_key,
      input_per_1k: row.input_per_1k,
      output_per_1k: row.output_per_1k,
      cache_read_per_1k: row.cache_read_per_1k ?? "",
      cache_creation_per_1k: row.cache_creation_per_1k ?? "",
    };
    setEditingId(row.id);
    setFormError(null);
    setFieldErrors({});
    setEditPrefill(prefill);
    setForm({ ...prefill });
  };

  const updateField = (field: keyof RateForm, value: string) => {
    setForm((prev) => (prev ? { ...prev, [field]: value } : prev));
    setFieldErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const submitForm = async () => {
    if (!form) return;
    const errors = validateLlmCostRateForm(form);
    setFieldErrors(errors);
    setFormError(null);
    if (Object.keys(errors).length > 0) return;
    setSaving(true);
    try {
      if (editingId) {
        await updateLlmCostRate(editingId, {
          input_per_1k: form.input_per_1k.trim(),
          output_per_1k: form.output_per_1k.trim(),
          ...(editPrefill ? changedCacheRates(form, editPrefill) : {}),
        });
        toast.success("Cost rate updated.");
      } else {
        await createLlmCostRate({
          provider: form.provider.trim(),
          model: form.model.trim(),
          input_per_1k: form.input_per_1k.trim(),
          output_per_1k: form.output_per_1k.trim(),
          cache_read_per_1k: serializeCacheRate(form.cache_read_per_1k),
          cache_creation_per_1k: serializeCacheRate(
            form.cache_creation_per_1k
          ),
        });
        toast.success("Cost rate added.");
      }
      closeForm();
      await load();
    } catch (err) {
      setFormError(backendErrorMessage(err, "Could not save this cost rate."));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClick = (row: LlmCostRate) => {
    setRowToDelete(row);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!rowToDelete) return;
    setDeleting(true);
    try {
      await deleteLlmCostRate(rowToDelete.id);
      toast.success("Cost rate removed.");
      setDeleteDialogOpen(false);
      setRowToDelete(null);
      await load();
    } catch {
      toast.error("Could not delete this cost rate.");
    } finally {
      setDeleting(false);
    }
  };

  const downloadCsvTemplate = () => {
    const blob = new Blob([`${CSV_TEMPLATE}\n`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "llm-cost-rates-template.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV header downloaded.");
  };

  const downloadCurrentRatesCsv = async () => {
    try {
      const blob = await exportLlmCostRatesCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "llm-cost-rates.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Current rates downloaded.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Export failed.");
    }
  };

  return (
    <>
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setCsvFormatOpen(false);
          setDeleteDialogOpen(false);
          setRowToDelete(null);
          closeForm();
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col gap-4 z-50">
        <DialogHeader>
          <DialogTitle>LLM cost rates</DialogTitle>
          <DialogDescription>
            USD per 1K tokens. Open{" "} <strong>CSV template</strong> for the exact column layout.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={openCreateForm}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add rate
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setCsvFormatOpen(true)}
          >
            <FileText className="w-4 h-4 mr-2" />
            CSV template
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void downloadCurrentRatesCsv()}
          >
            <Download className="w-4 h-4 mr-2" />
            Download current CSV
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={uploading}
            className="relative"
            onClick={() => document.getElementById("csv-input")?.click()}
          >
            {uploading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Upload className="w-4 h-4 mr-2" />
            )}
            Upload CSV
            <Input
              id="csv-input"
              type="file"
              accept=".csv,text/csv"
              className="absolute inset-0 cursor-pointer opacity-0 w-full h-full"
              disabled={uploading}
              onChange={(ev) => void onFile(ev)}
            />
          </Button>
          <Button
            className="ml-auto"
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
          >
            <RefreshCcw className={"w-2 h-2 " + (loading ? "animate-spin" : "")} />
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>

        {form && (
          <div className="rounded-md border p-3 space-y-3 shrink-0">
            <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Provider</span>
                <Input
                  value={form.provider}
                  disabled={!!editingId || saving}
                  placeholder="openai"
                  onChange={(e) => updateField("provider", e.target.value)}
                />
                {fieldErrors.provider && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.provider}
                  </span>
                )}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Model</span>
                <Input
                  value={form.model}
                  disabled={!!editingId || saving}
                  placeholder="gpt-4o"
                  onChange={(e) => updateField("model", e.target.value)}
                />
                {fieldErrors.model && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.model}
                  </span>
                )}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Input / 1K</span>
                <Input
                  value={form.input_per_1k}
                  disabled={saving}
                  inputMode="decimal"
                  placeholder="0.00015"
                  onChange={(e) => updateField("input_per_1k", e.target.value)}
                />
                {fieldErrors.input_per_1k && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.input_per_1k}
                  </span>
                )}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">
                  Output / 1K
                </span>
                <Input
                  value={form.output_per_1k}
                  disabled={saving}
                  inputMode="decimal"
                  placeholder="0.0006"
                  onChange={(e) => updateField("output_per_1k", e.target.value)}
                />
                {fieldErrors.output_per_1k && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.output_per_1k}
                  </span>
                )}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">
                  Cache read / 1K
                </span>
                <Input
                  value={form.cache_read_per_1k}
                  disabled={saving}
                  inputMode="decimal"
                  placeholder="optional"
                  onChange={(e) =>
                    updateField("cache_read_per_1k", e.target.value)
                  }
                />
                {fieldErrors.cache_read_per_1k && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.cache_read_per_1k}
                  </span>
                )}
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">
                  Cache write / 1K
                </span>
                <Input
                  value={form.cache_creation_per_1k}
                  disabled={saving}
                  inputMode="decimal"
                  placeholder="optional"
                  onChange={(e) =>
                    updateField("cache_creation_per_1k", e.target.value)
                  }
                />
                {fieldErrors.cache_creation_per_1k && (
                  <span className="block text-xs text-destructive">
                    {fieldErrors.cache_creation_per_1k}
                  </span>
                )}
              </label>
            </div>

            <p className="text-xs text-muted-foreground">
              Leave a cache rate blank to leave it unset; enter <code>0</code> to
              price that bucket as free.
            </p>
            {editingId && (
              <p className="text-xs text-muted-foreground">
                Provider and model are fixed. Delete and re-add to move a rate.
              </p>
            )}
            {formError && (
              <p className="text-sm text-destructive">{formError}</p>
            )}

            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                disabled={saving}
                onClick={() => void submitForm()}
              >
                {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                {editingId ? "Save changes" : "Add rate"}
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
              icon={<Coins className="h-12 w-12 text-muted-foreground" />}
              title="No cost rates yet"
              description="Add a rate to price token usage per provider and model, or upload a CSV to set several at once."
              action={
                !form ? (
                  <Button
                    onClick={openCreateForm}
                    className="rounded-full flex items-center gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    Add rate
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Input / 1K</TableHead>
                  <TableHead className="text-right">Output / 1K</TableHead>
                  <TableHead className="text-right whitespace-nowrap">
                    Cache read / 1K
                  </TableHead>
                  <TableHead className="text-right whitespace-nowrap">
                    Cache write / 1K
                  </TableHead>
                  <TableHead className="whitespace-nowrap">Updated</TableHead>
                  <TableHead className="w-[104px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">
                      {r.provider_key}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[200px] truncate" title={r.model_key}>
                      {r.model_key}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.input_per_1k}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.output_per_1k}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.cache_read_per_1k ?? "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.cache_creation_per_1k ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground"
                      title={r.updated_at}
                    >
                      {formatTimeAgo(r.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                        title="Edit rate"
                        onClick={() => openEditForm(r)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                        title="Delete row"
                        onClick={() => handleDeleteClick(r)}
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

        {!loading && rows.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="tabular-nums">
              {fromRow}–{toRow} of {totalRows}
            </span>

            <div className="flex items-center gap-2 ml-auto">
              <label className="flex items-center gap-2">
                <span className="text-xs">Rows</span>
                <select
                  className="h-8 rounded-md border bg-background px-2 text-sm text-foreground"
                  value={pageSize}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    setPageSize(next);
                    setPage(1);
                  }}
                >
                  {[10, 25, 50, 100].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>

              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </Button>
              <span className="tabular-nums">
                Page {page} / {totalPages}
              </span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        )}
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
        title="Delete cost rate?"
        description={
          rowToDelete
            ? `This removes the pricing row for ${rowToDelete.provider_key}/${rowToDelete.model_key}. You can add it again later with a CSV import. This action cannot be undone from the UI.`
            : undefined
        }
      />

      <Dialog open={csvFormatOpen} onOpenChange={setCsvFormatOpen}>
        <DialogContent className="max-w-lg max-h-[min(80vh,560px)] flex flex-col gap-3">
          <DialogHeader>
            <DialogTitle>CSV file format</DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>
                  Required header (column names are case-insensitive):{" "}
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    provider
                  </code>
                  ,{" "}
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    model
                  </code>
                  ,{" "}
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    input_per_1k
                  </code>
                  ,{" "}
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    output_per_1k
                  </code>
                  . Values are USD per 1K tokens.
                </p>
                <p>
                  Optional:{" "}
                  <code className="text-xs bg-muted px-1 rounded">
                    cache_read_per_1k
                  </code>{" "}
                  and{" "}
                  <code className="text-xs bg-muted px-1 rounded">
                    cache_creation_per_1k
                  </code>
                  . Files without them still import. Enter{" "}
                  <code className="text-xs bg-muted px-1 rounded">0</code> where
                  the model charges nothing. Left blank the bucket is unset, and
                  the cost falls back to a family estimate where one exists,
                  otherwise to ordinary input pricing, or stays unpriced on
                  providers that report cache tokens outside their input count.
                </p>
                <p>
                  The rows below only illustrate the layout, the keys and rates
                  are placeholders. Copy the real per-1K figures from your
                  provider's price list.
                </p>
                <p>
                  Use{" "}
                  <code className="text-xs bg-muted px-1 rounded">_default</code>{" "}
                  as <code className="text-xs bg-muted px-1 rounded">model</code>{" "}
                  for a provider-wide default when no specific model matches.
                </p>
              </div>
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap gap-2 shrink-0">
            <Button type="button" variant="outline" size="sm" onClick={copyCsvTemplate}>
              <Copy className="w-4 h-4 mr-2" />
              Copy header
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={downloadCsvTemplate}
            >
              <Download className="w-4 h-4 mr-2" />
              Download header .csv
            </Button>
          </div>

          <pre className="text-xs font-mono bg-muted/80 rounded-md p-3 overflow-auto flex-1 min-h-[140px] border">
            {CSV_EXAMPLE}
          </pre>
        </DialogContent>
      </Dialog>
    </>
  );
}
