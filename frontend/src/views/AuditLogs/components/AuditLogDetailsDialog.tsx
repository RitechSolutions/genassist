import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Check, Clipboard, Copy, Download, Lock } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { Skeleton } from "@/components/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs";
import { ListErrorState } from "@/components/ListErrorState";
import { cn, formatDate, getTimeFromDatetime } from "@/helpers/utils";
import { AuditLog, AuditLogDetailsDialogProps } from "@/interfaces/audit-log.interface";
import { fetchAuditLogDetails } from "@/services/auditLogs";
import JsonViewer, { type JsonValue } from "@/components/JsonViewer";

type ChangeRow = { field: string; before: unknown; after: unknown };
type ValueRow = { field: string; value: unknown };

/** The shapes the backend writes into `json_changes` (see backend/app/db/models/audit_log.py). */
type ParsedChanges =
  | { kind: "update"; rows: ChangeRow[] }
  | { kind: "snapshot"; rows: ValueRow[] }
  | { kind: "generic"; rows: ValueRow[] };

const REDACTED = "[REDACTED]";

const ACTION_BADGE_CLASS: Record<string, string> = {
  Insert: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  Update: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  Delete: "bg-red-500/15 text-red-700 dark:text-red-400",
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** json_changes is stored as text, and some values inside it are JSON-encoded again. */
function deepParse(value: unknown): unknown {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        return deepParse(JSON.parse(trimmed));
      } catch {
        return value;
      }
    }
    return value;
  }
  if (Array.isArray(value)) return value.map(deepParse);
  if (isRecord(value)) {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, deepParse(v)]));
  }
  return value;
}

function toParsedChanges(data: unknown): ParsedChanges {
  if (!isRecord(data)) return { kind: "generic", rows: [{ field: "value", value: data }] };

  const entries = Object.entries(data);
  if (entries.length > 0 && entries.every(([, v]) => isRecord(v) && "old" in v && "new" in v)) {
    return {
      kind: "update",
      rows: entries.map(([field, v]) => {
        const change = v as { old: unknown; new: unknown };
        return { field, before: change.old, after: change.new };
      }),
    };
  }

  if (isRecord(data.values)) {
    return {
      kind: "snapshot",
      rows: Object.entries(data.values).map(([field, value]) => ({ field, value })),
    };
  }

  return { kind: "generic", rows: entries.map(([field, value]) => ({ field, value })) };
}

/** Renders one audit value: nulls, redactions and the backend's list/dict summaries get their own treatment. */
function AuditValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <span className="italic text-muted-foreground">{value === "" ? "empty" : "null"}</span>;
  }
  if (value === REDACTED) {
    return (
      <span className="inline-flex items-center gap-1 italic text-muted-foreground">
        <Lock className="h-3 w-3" />
        Redacted
      </span>
    );
  }
  if (isRecord(value) && value.type === "list" && typeof value.len === "number") {
    return <span className="text-muted-foreground">List · {value.len} {value.len === 1 ? "item" : "items"}</span>;
  }
  if (isRecord(value) && value.type === "dict" && typeof value.keys === "number") {
    return <span className="text-muted-foreground">Object · {value.keys} {value.keys === 1 ? "key" : "keys"}</span>;
  }
  if (typeof value === "object") {
    return (
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted/50 p-2 font-mono text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span className="break-all font-mono text-xs">{String(value)}</span>;
}

function CopyableId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
  }, []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
      timeoutRef.current = window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable — nothing to do
    }
  };

  return (
    <span className="flex min-w-0 items-center gap-1">
      <span className="truncate font-mono text-xs" title={value}>
        {value}
      </span>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy"
        title="Copy"
        className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </span>
  );
}

/** A boolean that flips back to false `ms` after each `trigger()` — for "Copied"-style feedback. */
function useFlash(ms = 2000) {
  const [on, setOn] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
  }, []);

  const trigger = () => {
    setOn(true);
    if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => setOn(false), ms);
  };

  return [on, trigger] as const;
}

function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-0.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="min-w-0 text-sm font-medium">{children}</div>
    </div>
  );
}

function UpdateTable({ rows }: { rows: ChangeRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className="grid grid-cols-[minmax(7rem,0.8fr)_1fr_auto_1fr] items-center gap-3 border-b bg-muted/40 px-4 py-2 text-xs font-medium text-muted-foreground">
        <span>Field</span>
        <span>Before</span>
        <span className="w-4" />
        <span>After</span>
      </div>
      <div className="divide-y">
        {rows.map((row) => (
          <div
            key={row.field}
            className="grid grid-cols-[minmax(7rem,0.8fr)_1fr_auto_1fr] items-start gap-3 px-4 py-2.5"
          >
            <span className="break-all pt-0.5 font-mono text-xs font-semibold">{row.field}</span>
            <div className="min-w-0 rounded-md bg-red-500/5 px-2 py-1 text-red-700 dark:text-red-300">
              <AuditValue value={row.before} />
            </div>
            <ArrowRight className="mt-1.5 h-4 w-4 text-muted-foreground" />
            <div className="min-w-0 rounded-md bg-emerald-500/5 px-2 py-1 text-emerald-700 dark:text-emerald-300">
              <AuditValue value={row.after} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ValueTable({ rows }: { rows: ValueRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className="grid grid-cols-[minmax(7rem,0.6fr)_1.4fr] gap-3 border-b bg-muted/40 px-4 py-2 text-xs font-medium text-muted-foreground">
        <span>Field</span>
        <span>Value</span>
      </div>
      <div className="divide-y">
        {rows.map((row) => (
          <div key={row.field} className="grid grid-cols-[minmax(7rem,0.6fr)_1.4fr] items-start gap-3 px-4 py-2.5">
            <span className="break-all pt-0.5 font-mono text-xs font-semibold">{row.field}</span>
            <div className="min-w-0 pt-0.5">
              <AuditValue value={row.value} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetailsSkeleton() {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid grid-cols-2 gap-4 rounded-lg border p-4 sm:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="space-y-1.5">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-28" />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    </div>
  );
}

export function AuditLogDetailsDialog({
  isOpen,
  onOpenChange,
  auditLogId,
  users,
}: AuditLogDetailsDialogProps) {
  const [log, setLog] = useState<AuditLog | null>(null);
  const [rawChanges, setRawChanges] = useState<unknown>(null);
  const [changes, setChanges] = useState<ParsedChanges | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState("changes");
  const [copied, flashCopied] = useFlash();
  const [downloaded, flashDownloaded] = useFlash();

  // Each log opens on the readable view.
  useEffect(() => {
    if (isOpen) setTab("changes");
  }, [isOpen, auditLogId]);

  const rawJsonText = () => JSON.stringify(rawChanges, null, 2);

  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(rawJsonText());
      flashCopied();
    } catch {
      // clipboard unavailable — nothing to do
    }
  };

  const handleDownloadJson = () => {
    if (!log) return;
    const url = URL.createObjectURL(new Blob([rawJsonText()], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-log-${log.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    flashDownloaded();
  };

  useEffect(() => {
    if (!isOpen || !auditLogId) return;
    let cancelled = false;

    setLoading(true);
    setError(null);
    fetchAuditLogDetails(auditLogId)
      .then((data) => {
        if (cancelled) return;
        const parsed = deepParse(data.json_changes);
        setLog(data);
        setRawChanges(parsed);
        setChanges(toParsedChanges(parsed));
      })
      .catch(() => {
        if (cancelled) return;
        setLog(null);
        setChanges(null);
        setError("We couldn't load this audit log.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, auditLogId, reloadKey]);

  const username = log
    ? users.find((user) => user.id === log.modified_by)?.username || "Unknown User"
    : "";

  const changesLabel =
    changes?.kind === "update" ? "Changes" : changes?.kind === "snapshot" ? "Record" : "Details";

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl">
        {loading ? (
          <DetailsSkeleton />
        ) : error || !log || !changes ? (
          <>
            <DialogHeader>
              <DialogTitle>Audit log details</DialogTitle>
            </DialogHeader>
            <ListErrorState
              message={error ?? "No details are available for this audit log."}
              onRetry={() => setReloadKey((k) => k + 1)}
            />
          </>
        ) : (
          <>
            <DialogHeader className="space-y-1.5 pr-6">
              <div className="flex flex-wrap items-center gap-2">
                <DialogTitle className="font-mono text-lg">{log.table_name}</DialogTitle>
                <Badge
                  variant="outline"
                  className={cn("border-transparent", ACTION_BADGE_CLASS[log.action_name] ?? "bg-muted text-foreground")}
                >
                  {log.action_name}
                </Badge>
              </div>
              <DialogDescription>
                {changes.kind === "update"
                  ? `${changes.rows.length} ${changes.rows.length === 1 ? "field" : "fields"} changed`
                  : changes.kind === "snapshot"
                    ? `Record ${log.action_name === "Delete" ? "deleted" : "created"} with ${changes.rows.length} fields`
                    : "Audit event details"}{" "}
                by {username} on {formatDate(log.modified_at)} at {getTimeFromDatetime(log.modified_at)}
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-1 gap-4 rounded-lg border bg-muted/20 p-4 sm:grid-cols-3">
              <MetaItem label="User">{username}</MetaItem>
              <MetaItem label="Date">
                {formatDate(log.modified_at)} {getTimeFromDatetime(log.modified_at)}
              </MetaItem>
              <MetaItem label="Table">
                <span className="font-mono text-xs">{log.table_name}</span>
              </MetaItem>
              <MetaItem label="Record ID">
                {log.record_id ? <CopyableId value={log.record_id} /> : <span className="text-muted-foreground">—</span>}
              </MetaItem>
              <MetaItem label="Log ID">
                <CopyableId value={String(log.id)} />
              </MetaItem>
            </div>

            <Tabs value={tab} onValueChange={setTab} className="mt-6 min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <TabsList>
                  <TabsTrigger value="changes">
                    {changesLabel}
                    <span className="ml-1.5 rounded-full bg-muted-foreground/15 px-1.5 text-[10px]">
                      {changes.rows.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="raw">Raw JSON</TabsTrigger>
                </TabsList>
                {tab === "raw" && (
                  <Button size="sm" variant="outline" onClick={handleDownloadJson} className="gap-2">
                    {downloaded ? <Check className="h-4 w-4 text-emerald-500" /> : <Download className="h-4 w-4" />}
                    {downloaded ? "Downloaded" : "Download JSON"}
                  </Button>
                )}
              </div>
              <TabsContent value="changes" className="mt-3 max-h-[45vh] overflow-y-auto">
                {changes.rows.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">No changes were recorded.</p>
                ) : changes.kind === "update" ? (
                  <UpdateTable rows={changes.rows} />
                ) : (
                  <ValueTable rows={changes.rows} />
                )}
              </TabsContent>
              <TabsContent value="raw" className="mt-3 max-h-[45vh] overflow-y-auto text-xs">
                <JsonViewer data={rawChanges as JsonValue} />
              </TabsContent>
            </Tabs>

            <DialogFooter className="mt-6">
              <Button variant="outline" onClick={handleCopyJson} className="gap-2">
                {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Clipboard className="h-4 w-4" />}
                {copied ? "Copied" : "Copy JSON"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
