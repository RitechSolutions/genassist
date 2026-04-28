import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { PageLayout } from "@/components/PageLayout";
import { SearchInput } from "@/components/SearchInput";
import { Button, buttonVariants } from "@/components/button";
import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { TagsFieldInput } from "@/components/TagsFieldInput";
import { Progress } from "@/components/progress";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/alert-dialog";
import { usePermissions } from "@/context/PermissionContext";
import {
  deleteFileRecord,
  getFileBase64,
  getFileManagerSettings,
  listFiles,
  uploadFileRecord,
  type FileManagerSettings,
  type FileRecord,
} from "@/services/fileManager";
import { downloadFile, getFileDownloadUrl } from "@/helpers/utils";
import { getApiUrlString } from "@/config/api";
import {
  Download,
  FileText,
  ImageIcon,
  LayoutGrid,
  List,
  Loader2,
  Plus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import toast from "react-hot-toast";
import { cn } from "@/helpers/utils";
import { ToggleGroup, ToggleGroupItem } from "@/components/toggle-group";
import { formatDateTime } from "@/views/ActiveConversations/helpers/format";
import { Clock } from "lucide-react";
import { TooltipButton } from "@/components/tooltip-button";

const PERM_READ = "read:file";
const PERM_CREATE = "create:file";
const PERM_DELETE = "delete:file";

function hasPerm(permissions: string[], p: string): boolean {
  return permissions.includes("*") || permissions.includes(p);
}

function formatBytes(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v < 10 && i > 0 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

function extensionOf(f: FileRecord): string {
  const ext = f.file_extension?.replace(/^\./, "");
  if (ext) return ext.toUpperCase();
  const parts = f.name.split(".");
  return parts.length > 1 ? (parts.pop() || "").toUpperCase() : "FILE";
}

function extensionFromFileName(name: string): string {
  const i = name.lastIndexOf(".");
  if (i <= 0 || i >= name.length - 1) return "FILE";
  return name.slice(i + 1).toUpperCase();
}

function LocalImagePreview({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file.type.startsWith("image/")) {
      setUrl(null);
      return;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  if (!url) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-muted/60">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return (
    <img
      src={url}
      alt=""
      className="h-full w-full object-cover"
    />
  );
}

function FileExtensionPlaceholder({ extension }: { extension: string }) {
  const short = extension.length > 8 ? `${extension.slice(0, 7)}…` : extension;
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-gradient-to-br from-muted/80 to-muted/40 p-3">
      <FileText className="h-10 w-10 text-muted-foreground/70" />
      <span
        className="rounded-md bg-background/90 px-2.5 py-1 font-mono text-xs font-semibold uppercase tracking-wide text-foreground shadow-sm ring-1 ring-border/60"
        title={extension}
      >
        .{short}
      </span>
    </div>
  );
}

function FileThumb({
  fileId,
  mimeType,
  compact = false,
}: {
  fileId: string;
  mimeType?: string | null;
  compact?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!mimeType?.startsWith("image/")) return;
    const el = containerRef.current;
    if (!el) return;

    const obs = new IntersectionObserver(
      (entries) => {
        const [e] = entries;
        if (!e?.isIntersecting) return;
        obs.disconnect();
        setLoading(true);
        getFileBase64(fileId)
          .then((r) => {
            if (r?.content && r.mime_type) {
              setSrc(`data:${r.mime_type};base64,${r.content}`);
            } else {
              setErr(true);
            }
          })
          .catch(() => setErr(true))
          .finally(() => setLoading(false));
      },
      { rootMargin: "120px", threshold: 0.01 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [fileId, mimeType]);

  if (!mimeType?.startsWith("image/")) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg bg-muted/80",
          compact
            ? "h-12 w-12 shrink-0"
            : "h-28 w-full",
        )}
      >
        <FileText
          className={cn(
            "text-muted-foreground/80",
            compact ? "h-6 w-6" : "h-12 w-12",
          )}
        />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-lg bg-muted/50",
        compact ? "h-12 w-12 shrink-0" : "h-28 w-full",
      )}
    >
      {loading && !src && (
        <Loader2
          className={cn(
            "animate-spin text-muted-foreground",
            compact ? "h-5 w-5" : "h-8 w-8",
          )}
        />
      )}
      {err && !src && !loading && (
        <ImageIcon
          className={cn("text-muted-foreground", compact ? "h-5 w-5" : "h-10 w-10")}
        />
      )}
      {src && (
        <img src={src} alt="" className="h-full w-full object-cover" />
      )}
    </div>
  );
}

function FileManagerFileBlock({
  f,
  layout,
  canDelete,
  downloading,
  onDownload,
  onDeleteRequest,
}: {
  f: FileRecord;
  layout: "thumbnails" | "list";
  canDelete: boolean;
  downloading: boolean;
  onDownload: (file: FileRecord) => void;
  onDeleteRequest: (file: FileRecord) => void;
}) {
  const metaBlock =
    f.file_metadata && Object.keys(f.file_metadata).length > 0 ? (
      <details className="text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Metadata ({Object.keys(f.file_metadata).length} keys)
        </summary>
        <pre className="mt-2 max-h-24 overflow-auto rounded-md bg-muted/50 p-2 text-[10px] leading-relaxed">
          {JSON.stringify(f.file_metadata, null, 2)}
        </pre>
      </details>
    ) : null;

  const actions = (
    <div
      className={cn(
        "flex gap-2",
        layout === "thumbnails"
          ? "flex-wrap border-t pt-3"
          : "w-full shrink-0 flex-nowrap sm:w-auto sm:justify-end",
      )}
    >
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="gap-1 shrink-0 rounded-full"
        loading={downloading}
        icon={<Download className="h-3.5 w-3.5" />}
        onClick={() => onDownload(f)}
      >
        Download
      </Button>
      {canDelete && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1 shrink-0 rounded-full text-destructive hover:text-destructive"
          onClick={() => onDeleteRequest(f)}
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete
        </Button>
      )}
    </div>
  );

  const details = (
    <div className="space-y-3">
      <div
        className={cn(
          "flex justify-between gap-2",
          layout === "list" ? "items-center" : "items-start",
        )}
      >
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-sm" title={f.name}>
            {f.name}
          </p>
          {f.path && layout === "list" && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground" title={f.path}>
              {f.path}
            </p>
          )}
          {f.description && (
            <p
              className={cn(
                "mt-1 text-xs text-muted-foreground",
                layout === "list" ? "line-clamp-1" : "line-clamp-2",
              )}
            >
              {f.description}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          {formatBytes(f.size ?? undefined)}
        </span>
        {f.mime_type && (
          <span className="truncate max-w-[180px]" title={f.mime_type}>
            {f.mime_type}
          </span>
        )}
      </div>


      <div className="flex row-span-2 items-center gap-2 text-xs text-muted-foreground justify-between">
        <div className="flex items-center gap-2">
          <TooltipButton
            button={<Clock className="w-3 h-3 text-muted-foreground" />}
            tooltipContent={{ side: 'top', align: 'center', children: <p>Updated at {formatDateTime(f.updated_at)}</p> }}
          />

          <span>{formatDateTime(f.updated_at)}</span>
        </div>

        <Badge variant="secondary" className="shrink-0 font-mono text-[10px]">
          .{extensionOf(f).toLowerCase()}
        </Badge>
      </div>

      {f.tags && f.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {f.tags.slice(0, layout === "list" ? 4 : 6).map((t) => (
            <Badge key={t} variant="outline" className="text-[10px] font-normal">
              {t}
            </Badge>
          ))}
          {f.tags.length > (layout === "list" ? 4 : 6) && (
            <span className="text-[10px] text-muted-foreground">
              +{f.tags.length - (layout === "list" ? 4 : 6)}
            </span>
          )}
        </div>
      )}

      {metaBlock}
      {layout === "thumbnails" && actions}
    </div>
  );

  if (layout === "thumbnails") {
    return (
      <Card className="overflow-hidden border bg-white shadow-sm transition-shadow hover:shadow-md">
        <FileThumb fileId={f.id} mimeType={f.mime_type} />
        <div className="p-4">{details}</div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border bg-white shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
        <FileThumb compact fileId={f.id} mimeType={f.mime_type} />
        <div className="min-w-0 flex-1">{details}</div>
        <div className="flex border-t pt-3 sm:shrink-0 sm:border-t-0 sm:border-l sm:pl-6 sm:pt-0">
          {actions}
        </div>
      </div>
    </Card>
  );
}

export function FileManagerFiles() {
  const permissions = usePermissions();
  const canCreate = hasPerm(permissions, PERM_CREATE);
  const canDelete = hasPerm(permissions, PERM_DELETE);
  const canRead = hasPerm(permissions, PERM_READ);

  const [settings, setSettings] = useState<FileManagerSettings | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FileRecord | null>(null);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fileDragDepthRef = useRef(0);
  const [fileDragActive, setFileDragActive] = useState(false);
  const [pathInput, setPathInput] = useState("uploads");
  const [storagePathInput, setStoragePathInput] = useState("");
  const [descriptionInput, setDescriptionInput] = useState("");
  const [uploadTags, setUploadTags] = useState<string[]>([]);
  const [metadataInput, setMetadataInput] = useState("{}");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [viewMode, setViewMode] = useState<"thumbnails" | "list">("thumbnails");
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(null);

  const fmEnabled =
    settings?.values.file_manager_enabled === true && settings.is_active === 1;

  const loadFiles = useCallback(async () => {
    if (!canRead) return;
    setLoading(true);
    try {
      const data = await listFiles({ limit: 500 });
      setFiles(data ?? []);
      if (data === null) {
        toast.error("You may not have permission to list files.");
      }
    } catch {
      toast.error("Failed to load files.");
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [canRead]);

  useEffect(() => {
    getFileManagerSettings()
      .then((s) => {
        setSettings(s);
        if (s?.values.base_path) {
          setStoragePathInput(s.values.base_path);
        }
      })
      .finally(() => setSettingsLoaded(true));
  }, []);

  useEffect(() => {
    if (!settingsLoaded || !fmEnabled || !canRead) return;
    loadFiles();
  }, [settingsLoaded, fmEnabled, canRead, loadFiles]);

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => {
      const tags = (f.tags ?? []).join(" ").toLowerCase();
      const meta = JSON.stringify(f.file_metadata ?? "").toLowerCase();
      return (
        f.name.toLowerCase().includes(q) ||
        f.path.toLowerCase().includes(q) ||
        tags.includes(q) ||
        meta.includes(q)
      );
    });
  }, [files, searchQuery]);

  const resetUploadForm = () => {
    setUploadFile(null);
    fileDragDepthRef.current = 0;
    setFileDragActive(false);
    setPathInput("uploads");
    setStoragePathInput(settings?.values.base_path ?? "");
    setDescriptionInput("");
    setUploadTags([]);
    setMetadataInput("{}");
    setUploadProgress(0);
  };

  const handleOpenUpload = () => {
    resetUploadForm();
    setUploadOpen(true);
  };

  const clearSelectedFile = () => {
    setUploadFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null;
    setUploadFile(next);
  };

  const handleFileDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    fileDragDepthRef.current = 0;
    setFileDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      setUploadFile(dropped);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleSubmitUpload = async () => {
    if (!uploadFile) {
      toast.error("Choose a file to upload.");
      return;
    }
    const sp = storagePathInput.trim();
    const p = pathInput.trim();
    if (!p) {
      toast.error("Path is required.");
      return;
    }
    if (!sp) {
      toast.error("Storage path is required.");
      return;
    }
    let metaObj: Record<string, unknown> = {};
    try {
      const parsed = JSON.parse(metadataInput.trim() || "{}");
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        metaObj = parsed as Record<string, unknown>;
      } else {
        throw new Error("Metadata must be a JSON object.");
      }
    } catch {
      toast.error("Metadata must be valid JSON object.");
      return;
    }

    const fd = new FormData();
    fd.append("file", uploadFile);
    fd.append("name", uploadFile.name);
    fd.append("path", p);
    fd.append("storage_path", sp);
    fd.append(
      "storage_provider",
      settings?.values.file_manager_provider || "local"
    );
    if (descriptionInput.trim()) {
      fd.append("description", descriptionInput.trim());
    }
    if (uploadTags.length) {
      fd.append("tags", JSON.stringify(uploadTags));
    }
    if (Object.keys(metaObj).length) {
      fd.append("file_metadata", JSON.stringify(metaObj));
    }

    setUploading(true);
    setUploadProgress(0);
    try {
      await uploadFileRecord(fd, {
        onProgress: (pct) => setUploadProgress(pct),
      });
      toast.success("File uploaded.");
      setUploadOpen(false);
      resetUploadForm();
      await loadFiles();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteFileRecord(deleteTarget.id);
      toast.success("File deleted.");
      setDeleteTarget(null);
      await loadFiles();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed.");
    }
  };

  const handleDownload = async (f: FileRecord) => {
    setDownloadingFileId(f.id);
    try {
      const tenantId = localStorage.getItem("tenant_id");
      const fileUrl = getFileDownloadUrl(f.id, getApiUrlString, tenantId || "");
      await downloadFile(fileUrl, f.name);
    } catch {
      toast.error("Failed to download file");
    } finally {
      setDownloadingFileId(null);
    }
  };

  if (!settingsLoaded) {
    return (
      <PageLayout>
        <div className="flex justify-center py-24">
          <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
        </div>
      </PageLayout>
    );
  }

  if (!fmEnabled) {
    return (
      <PageLayout>
        <Card className="p-8">
          <h1 className="text-xl font-semibold mb-2">Manage Files</h1>
          <p className="text-sm text-muted-foreground">
            File manager is not enabled or is disabled. Please contact your
            administrator to enable it.
          </p>
        </Card>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:flex-wrap">
        <div className="min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold mb-1">Manage Files</h1>
          <p className="text-sm md:text-base text-muted-foreground">
            Browse uploads, preview images, and manage metadata
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
          <ToggleGroup
            type="single"
            value={viewMode}
            onValueChange={(v) => {
              if (v === "thumbnails" || v === "list") setViewMode(v);
            }}
            variant="outline"
            size="sm"
            className="shrink-0 justify-start rounded-full border border-input bg-background p-0.5"
            aria-label="File layout"
          >
            <ToggleGroupItem
              value="thumbnails"
              className="rounded-full px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
              aria-label="Thumbnails"
            >
              <LayoutGrid className="h-4 w-4" />
            </ToggleGroupItem>
            <ToggleGroupItem
              value="list"
              className="rounded-full px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
              aria-label="List"
            >
              <List className="h-4 w-4" />
            </ToggleGroupItem>
          </ToggleGroup>
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search by name, path, tags…"
            className="sm:w-[280px]"
          />
          {canCreate && (
            <Button
              type="button"
              className="rounded-full gap-2"
              onClick={handleOpenUpload}
            >
              <Plus className="w-4 h-4" />
              Upload file
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
        </div>
      ) : viewMode === "thumbnails" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((f) => (
            <FileManagerFileBlock
              key={f.id}
              f={f}
              layout="thumbnails"
              canDelete={canDelete}
              downloading={downloadingFileId === f.id}
              onDownload={handleDownload}
              onDeleteRequest={setDeleteTarget}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((f) => (
            <FileManagerFileBlock
              key={f.id}
              f={f}
              layout="list"
              canDelete={canDelete}
              downloading={downloadingFileId === f.id}
              onDownload={handleDownload}
              onDeleteRequest={setDeleteTarget}
            />
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <p className="py-12 text-center text-sm text-muted-foreground">
          {searchQuery.trim()
            ? "No files match your search."
            : "No files yet."}
        </p>
      )}

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent
          className={cn(
            "flex h-[90vh] max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-4xl flex-col gap-0 overflow-hidden p-0 sm:w-full",
          )}
        >
          <DialogHeader className="shrink-0 space-y-0 border-b border-gray-100 px-6 pb-4 pt-6 pr-14">
            <DialogTitle>Upload file</DialogTitle>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-4">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="fm-file">File</Label>
              <input
                ref={fileInputRef}
                id="fm-file"
                type="file"
                className="sr-only"
                onChange={handleFileInputChange}
              />
              <div
                role={uploadFile ? "group" : "button"}
                tabIndex={uploading || uploadFile ? -1 : 0}
                aria-label={
                  uploadFile
                    ? `Selected file ${uploadFile.name}. Click to replace.`
                    : "Choose file to upload or drop a file here"
                }
                onClick={() => !uploading && fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                onDragEnter={(e) => {
                  e.preventDefault();
                  if (uploading) return;
                  fileDragDepthRef.current += 1;
                  setFileDragActive(true);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!uploading) e.dataTransfer.dropEffect = "copy";
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  if (uploading) return;
                  fileDragDepthRef.current = Math.max(0, fileDragDepthRef.current - 1);
                  if (fileDragDepthRef.current === 0) setFileDragActive(false);
                }}
                onDrop={uploading ? undefined : handleFileDrop}
                className={cn(
                  "group relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-200",
                  uploading && "pointer-events-none opacity-60",
                  fileDragActive
                    ? "border-primary bg-primary/[0.06] ring-2 ring-primary/25"
                    : "border-border/80 bg-muted/20 hover:border-primary/40 hover:bg-muted/35",
                )}
              >
                {!uploadFile ? (
                  <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-background shadow-sm ring-1 ring-border/60 transition-transform duration-200 group-hover:scale-105">
                      <Upload className="h-7 w-7 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        Drop a file here or click to browse
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Any file type — preview for images, details for others
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-stretch">
                    <div
                      className={cn(
                        "relative mx-auto h-36 w-full max-w-[200px] shrink-0 overflow-hidden rounded-xl bg-muted/50 ring-1 ring-border/50 sm:mx-0 sm:h-40 sm:w-40",
                      )}
                    >
                      {uploadFile.type.startsWith("image/") ? (
                        <LocalImagePreview file={uploadFile} />
                      ) : (
                        <FileExtensionPlaceholder
                          extension={extensionFromFileName(uploadFile.name)}
                        />
                      )}
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p
                            className="truncate text-sm font-semibold text-foreground"
                            title={uploadFile.name}
                          >
                            {uploadFile.name}
                          </p>
                          <p className="mt-1 text-sm tabular-nums text-muted-foreground">
                            {formatBytes(uploadFile.size)}
                          </p>
                          {uploadFile.type && (
                            <p className="mt-0.5 truncate text-xs text-muted-foreground/90">
                              {uploadFile.type}
                            </p>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:text-foreground"
                          onClick={(e) => {
                            e.stopPropagation();
                            clearSelectedFile();
                          }}
                          aria-label="Remove file"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Click the card to replace, or remove to choose another file.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fm-path">Logical path</Label>
              <input
                id="fm-path"
                value={pathInput}
                onChange={(e) => setPathInput(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="uploads"
              />
              <p className="text-xs text-muted-foreground">
                Folder segment used when building the stored path (required).
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fm-sp">Storage path</Label>
              <input
                id="fm-sp"
                value={storagePathInput}
                onChange={(e) => setStoragePathInput(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder={settings?.values.base_path || "Base path from settings"}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fm-desc">Description (optional)</Label>
              <input
                id="fm-desc"
                value={descriptionInput}
                onChange={(e) => setDescriptionInput(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fm-tags">Tags (optional)</Label>
              <TagsFieldInput
                id="fm-tags"
                value={uploadTags}
                placeholder="Type and press Enter or comma…"
                onChange={setUploadTags}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fm-meta">Metadata JSON (optional)</Label>
              <Textarea
                id="fm-meta"
                value={metadataInput}
                onChange={(e) => setMetadataInput(e.target.value)}
                className="min-h-[88px] font-mono text-xs"
                placeholder='{"key": "value"}'
              />
            </div>
          </div>
          </div>
          <DialogFooter className="shrink-0 flex-col items-stretch gap-3 border-t border-gray-100 px-6 py-4 sm:flex-col">
            {uploading && (
              <div className="w-full space-y-1.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Uploading…</span>
                  <span className="tabular-nums font-medium text-foreground">
                    {uploadProgress}%
                  </span>
                </div>
                <Progress value={uploadProgress} className="h-2" />
              </div>
            )}
            <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setUploadOpen(false)}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button type="button" loading={uploading} onClick={handleSubmitUpload}>
                Upload
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete file?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove{" "}
              <span className="font-medium text-foreground">
                {deleteTarget?.name}
              </span>{" "}
              from storage. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className={cn(buttonVariants({ variant: "destructive" }))}
              onClick={() => void handleDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageLayout>
  );
}
