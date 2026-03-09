import { useState, type ComponentType } from "react";
import { Download, FileText, Sheet, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { api, getApiUrl } from "@/config/api";

const EXPORT_FORMATS: Array<{
  fmt: "csv" | "xlsx" | "pdf";
  label: string;
  Icon: ComponentType<{ className?: string }>;
  iconClass: string;
}> = [
  { fmt: "csv",  label: "Download CSV",   Icon: Sheet,           iconClass: "text-green-600" },
  { fmt: "xlsx", label: "Download Excel", Icon: FileSpreadsheet, iconClass: "text-emerald-600" },
  { fmt: "pdf",  label: "Download PDF",   Icon: FileText,        iconClass: "text-red-500" },
];

interface ExportButtonProps {
  endpoint: string;                              // e.g. "/analytics/agents/export"
  params: Record<string, string | undefined>;    // e.g. { agent_id, from_date, to_date }
  filename: string;                              // base name without extension
  disabled?: boolean;
}

async function downloadBlob(
  endpoint: string,
  params: Record<string, string | undefined>,
  format: "csv" | "xlsx" | "pdf",
  filename: string,
): Promise<void> {
  const baseUrl = await getApiUrl();
  const qs = new URLSearchParams({ format });
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") qs.set(k, v);
  });

  const url = `${baseUrl}${endpoint.replace(/^\//, "")}?${qs.toString()}`;
  const response = await api.get(url, { responseType: "blob" });

  const blob = new Blob([response.data], { type: response.headers["content-type"] });
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = `${filename}.${format}`;
  a.click();
  URL.revokeObjectURL(objectUrl);
}

export function ExportButton({ endpoint, params, filename, disabled }: ExportButtonProps) {
  const [exporting, setExporting] = useState<"csv" | "xlsx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const handle = (fmt: "csv" | "xlsx" | "pdf") => async () => {
    setExporting(fmt);
    setExportError(null);
    try {
      await downloadBlob(endpoint, params, fmt, filename);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Export failed. Check the server logs.";
      setExportError(msg);
      console.error("Export failed:", err);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      {exportError && (
        <p className="text-xs text-red-500 max-w-[240px] text-right">{exportError}</p>
      )}
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || exporting !== null}
          className="gap-1.5"
        >
          <Download className="w-3.5 h-3.5" />
          {exporting ? "Exporting…" : "Export"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {EXPORT_FORMATS.map(({ fmt, label, Icon, iconClass }) => (
          <DropdownMenuItem key={fmt} onClick={handle(fmt)} className="gap-2 cursor-pointer">
            <Icon className={`w-4 h-4 ${iconClass}`} />
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
    </div>
  );
}
