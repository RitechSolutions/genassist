import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getLlmCostRates,
  importLlmCostRatesCsv,
  deleteLlmCostRate,
} from "@/services/llmCostRates";
import type { LlmCostRate } from "@/interfaces/llmCostRate.interface";
import toast from "react-hot-toast";
import {
  Copy,
  Download,
  FileText,
  Loader2,
  RefreshCcw,
  Trash2,
  Upload,
} from "lucide-react";
import { formatTimeAgo } from "@/helpers/formatters";
import { ConfirmDialog } from "@/components/ConfirmDialog";

/** Example CSV matching the import API (UTF-8, header row required). */
const CSV_MODEL = `provider,model,input_per_1k,output_per_1k
openai,gpt-4o,0.0025,0.01
openai,gpt-4o-mini,0.00015,0.0006
anthropic,claude-3-5-sonnet,0.003,0.015
openrouter,_default,0.001,0.002
vllm,_default,0,0`;

interface LlmCostRatesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
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

  const copyCsvModel = () => {
    void navigator.clipboard.writeText(`${CSV_MODEL.trim()}\n`);
    toast.success("Example CSV copied to clipboard.");
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

  const downloadCsvModel = () => {
    const blob = new Blob([`${CSV_MODEL.trim()}\n`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "llm-cost-rates-template.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Template downloaded.");
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
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col gap-4 z-50">
        <DialogHeader>
          <DialogTitle>LLM cost rates</DialogTitle>
          <DialogDescription>
            USD per 1K tokens. Open <strong>CSV template</strong> for the exact
            column layout and a ready-to-edit example.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
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

        <div className="flex-1 min-h-0 overflow-auto rounded-md border">
          {loading ? (
            <div className="flex items-center justify-center p-8 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin mr-2" />
              Loading…
            </div>
          ) : rows.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              No rates in the database yet. Run migrations or upload a CSV.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Input / 1K</TableHead>
                  <TableHead className="text-right">Output / 1K</TableHead>
                  <TableHead className="whitespace-nowrap">Updated</TableHead>
                  <TableHead className="w-[72px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">
                      {r.provider_key}
                    </TableCell>
                    <TableCell className="font-mono text-xs max-w-[240px] truncate" title={r.model_key}>
                      {r.model_key}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.input_per_1k}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.output_per_1k}
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
                  Use{" "}
                  <code className="text-xs bg-muted px-1 rounded">_default</code>{" "}
                  as <code className="text-xs bg-muted px-1 rounded">model</code>{" "}
                  for a provider-wide default when no specific model matches.
                </p>
              </div>
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap gap-2 shrink-0">
            <Button type="button" variant="outline" size="sm" onClick={copyCsvModel}>
              <Copy className="w-4 h-4 mr-2" />
              Copy example
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={downloadCsvModel}
            >
              <Download className="w-4 h-4 mr-2" />
              Download .csv
            </Button>
          </div>

          <pre className="text-xs font-mono bg-muted/80 rounded-md p-3 overflow-auto flex-1 min-h-[140px] border">
            {CSV_MODEL.trim()}
          </pre>
        </DialogContent>
      </Dialog>
    </>
  );
}
