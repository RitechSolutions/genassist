import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileJson,
  Info,
  Loader2,
  MinusCircle,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  importCasesFromFiles,
  listTestCases,
  previewCasesFromFiles,
} from "@/services/testSuites";
import type {
  DatasetFileResult,
  ImportCasesFromFilesResult,
  TestCase,
  TestSuite,
} from "@/interfaces/testSuite.interface";
import { apiErrorDetail } from "../helpers/evalBundle";
import {
  DATASET_SAMPLE_FILE,
  MAX_IMPORT_FILES,
  addFiles,
  describeDroppedFiles,
  describeReadableFile,
  fileKey,
  summarizeFileImportOutcome,
  summarizePreview,
} from "../helpers/datasetFileImport";

const FORMAT_EXAMPLE = `{
  "kind": "genassist.dataset",
  "schema_version": 1,
  "conversations": [
    {
      "turns": [
        {
          "input_data": {
            "message": "Where is my order?",
            "region": "north-america"
          },
          "expected_output": {
            "value": "Let me check. What's your order number?"
          }
        }
      ]
    }
  ]
}`;

const NO_PERMISSION = "You don't have permission to import into this dataset.";

const TEXT_LINK_CLASS =
  "inline-flex items-center gap-1 rounded-sm text-xs hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const FileStatusIcon: React.FC<{
  result?: DatasetFileResult;
  isChecking: boolean;
}> = ({ result, isChecking }) => {
  if (!result) {
    return isChecking ? (
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
    ) : (
      <FileJson className="h-4 w-4 shrink-0 text-muted-foreground" />
    );
  }
  if (result.status !== "ok") {
    return <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />;
  }
  if (result.conversations === 0) {
    return <MinusCircle className="h-4 w-4 shrink-0 text-muted-foreground" />;
  }
  return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />;
};

const FileDetails: React.FC<{
  result: DatasetFileResult;
  /** Where the file sits in `files`, the preview it came from. */
  position: number;
  files: DatasetFileResult[];
}> = ({ result, position, files }) => {
  if (result.status === "evaluation_bundle") {
    return (
      <p className="mt-1 text-xs text-destructive">
        This is an evaluation bundle, not a dataset file. Import it on the{" "}
        <Link to="/tests/evaluations" className="underline underline-offset-2">
          Evaluations page
        </Link>
        .
      </p>
    );
  }
  if (result.status === "failed") {
    return (
      <ul className="mt-1 space-y-0.5 text-xs text-destructive">
        {result.errors.map((error, index) => (
          <li key={`${index}-${error}`}>{error}</li>
        ))}
      </ul>
    );
  }
  return (
    <p className="mt-1 text-xs text-muted-foreground">
      {describeReadableFile(result, position, files)}
    </p>
  );
};

interface ImportFromFilesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The dataset being imported into. Nothing is checked until it is set. */
  suite: TestSuite | null;
  /** Fires after an import with the dataset's refreshed turns. */
  onDatasetChanged?: (suiteId: string, cases: TestCase[]) => void;
}

export const ImportFromFilesDialog: React.FC<ImportFromFilesDialogProps> = ({
  open,
  onOpenChange,
  suite,
  onDatasetChanged,
}) => {
  const [files, setFiles] = useState<File[]>([]);
  // The latest preview, kept with the selection it describes.
  const [checked, setChecked] = useState<{
    files: File[];
    result: ImportCasesFromFilesResult;
  } | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showFormat, setShowFormat] = useState(false);
  // Ticket for the newest preview request, so a slow reply cannot land late.
  const previewRequestRef = useRef(0);
  // Set before the first await, so a close in the same click cannot slip through.
  const isImportingRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const chooseButtonRef = useRef<HTMLButtonElement>(null);
  const removeButtonRefs = useRef(new Map<string, HTMLButtonElement>());

  const suiteId = suite?.id;
  // Only a preview of exactly this selection can unlock Import.
  const preview = checked?.files === files ? checked.result : null;
  // Each file's last known result, shown while a re-check runs so the rows stay put.
  const resultByKey = useMemo(() => {
    const results = new Map<string, { result: DatasetFileResult; position: number }>();
    checked?.files.forEach((file, position) => {
      const result = checked.result.files[position];
      if (result) results.set(fileKey(file), { result, position });
    });
    return results;
  }, [checked]);
  const summary = preview ? summarizePreview(preview) : null;
  const canImport = !!summary?.canImport && !isChecking && !isImporting;
  const isAtCap = files.length >= MAX_IMPORT_FILES;

  // Start empty each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setFiles([]);
    setChecked(null);
    setCheckError("");
    setShowFormat(false);
  }, [open]);

  // Check the selection again whenever it changes.
  useEffect(() => {
    const requestId = ++previewRequestRef.current;
    if (!open || !suiteId || files.length === 0) {
      setIsChecking(false);
      setCheckError("");
      return;
    }
    setIsChecking(true);
    setCheckError("");
    // A short pause, so removing several files in a row sends one check.
    const timer = setTimeout(() => {
      previewCasesFromFiles(suiteId, files)
        .then((result) => {
          if (requestId !== previewRequestRef.current) return;
          if (result) setChecked({ files, result });
          else setCheckError(NO_PERMISSION);
        })
        .catch((error: unknown) => {
          if (requestId !== previewRequestRef.current) return;
          setCheckError(apiErrorDetail(error) ?? "Could not check the files.");
        })
        .finally(() => {
          if (requestId === previewRequestRef.current) setIsChecking(false);
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [open, suiteId, files]);

  const addPicked = (picked: File[]) => {
    if (picked.length === 0 || isImportingRef.current) return;
    const { files: next, dropped } = addFiles(files, picked);
    if (dropped > 0) toast.error(describeDroppedFiles(dropped));
    if (next.length !== files.length) setFiles(next);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files ?? []);
    // Cleared so picking the same file again still fires a change.
    event.target.value = "";
    addPicked(picked);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    addPicked(Array.from(event.dataTransfer.files));
  };

  const removeFile = (index: number) => {
    // Hand focus on first, or it falls back to the dialog itself.
    const neighbour = files[index + 1] ?? files[index - 1];
    const nextFocus = neighbour
      ? removeButtonRefs.current.get(fileKey(neighbour))
      : chooseButtonRef.current;
    nextFocus?.focus();
    setFiles((current) => current.filter((_, position) => position !== index));
  };

  const handleOpenChange = (next: boolean) => {
    // Closing mid-import would hide its outcome.
    if (!next && isImportingRef.current) return;
    onOpenChange(next);
  };

  const handleImport = async () => {
    if (!suiteId || files.length === 0 || isImportingRef.current) return;
    isImportingRef.current = true;
    setIsImporting(true);
    try {
      const result = await importCasesFromFiles(suiteId, files);
      if (!result) {
        toast.error(NO_PERMISSION);
        return;
      }
      const outcome = summarizeFileImportOutcome(result);
      if (outcome.ok) toast.success(outcome.message);
      else toast.error(outcome.message);
      if (result.conversations > 0) {
        const cases = await listTestCases(suiteId).catch(() => null);
        if (cases) onDatasetChanged?.(suiteId, cases);
      }
      isImportingRef.current = false;
      onOpenChange(false);
    } catch (error: unknown) {
      toast.error(apiErrorDetail(error) ?? "Failed to import the files.");
    } finally {
      isImportingRef.current = false;
      setIsImporting(false);
    }
  };

  const footerText =
    files.length === 0
      ? `Choose up to ${MAX_IMPORT_FILES} files.`
      : isChecking
        ? "Checking the files..."
        : checkError || summary?.text || "";
  const footerIsProblem = !isChecking && (!!checkError || !!preview?.error);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-[640px] p-0 overflow-hidden flex flex-col max-h-[80vh]"
        // Focus the picker, not the first link, so Enter opens it straight away.
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          chooseButtonRef.current?.focus();
        }}
      >
        <DialogHeader className="p-6 pb-4 shrink-0">
          <DialogTitle>Import files into "{suite?.name}"</DialogTitle>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-4 space-y-4">
          <div className="space-y-2 text-sm text-muted-foreground">
            <DialogDescription>
              Choose dataset files in JSON. Each file lists conversations, and
              each conversation lists its turns in order. Conversations this
              dataset already holds are skipped.
            </DialogDescription>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <button
                type="button"
                // Darker while open, so the link reads as the guide's toggle.
                className={`${TEXT_LINK_CLASS} ${showFormat ? "text-foreground" : ""}`}
                aria-expanded={showFormat}
                aria-controls="dataset-file-format"
                onClick={() => setShowFormat((shown) => !shown)}
              >
                <Info className="h-3.5 w-3.5" />
                How to format the file
              </button>
              <a
                href={DATASET_SAMPLE_FILE}
                download="dataset_sample.json"
                className={TEXT_LINK_CLASS}
              >
                <Download className="h-3.5 w-3.5" />
                Download sample file
              </a>
            </div>
            {showFormat && (
              <div
                id="dataset-file-format"
                className="space-y-2 rounded-md border bg-muted/40 p-3 text-xs"
              >
                <ul className="list-disc space-y-1 pl-4">
                  <li>
                    <code>input_data</code> is what the agent receives: a{" "}
                    <code>message</code> and any extra fields, such as{" "}
                    <code>region</code>. In a conversation with several turns,
                    every turn needs a <code>message</code>.
                  </li>
                  <li>
                    <code>expected_output</code> is optional, for example{" "}
                    <code>{'{"value": "..."}'}</code>.
                  </li>
                  <li>
                    <code>tags</code> and <code>weight</code> are optional.
                  </li>
                </ul>
                <pre className="overflow-x-auto rounded border bg-background p-2 font-mono text-[11px] leading-relaxed text-foreground">
                  {FORMAT_EXAMPLE}
                </pre>
              </div>
            )}
          </div>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              if (!isImporting) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center gap-2 rounded-lg border border-dashed py-6 transition-colors ${
              isDragging ? "border-primary bg-primary/5" : ""
            }`}
          >
            <FileJson className="h-7 w-7 text-muted-foreground" />
            <Button
              ref={chooseButtonRef}
              variant="outline"
              size="sm"
              icon={<Upload className="h-4 w-4" />}
              disabled={isImporting || isAtCap}
              onClick={() => inputRef.current?.click()}
            >
              Choose files
            </Button>
            <span className="text-xs text-muted-foreground">
              {isAtCap ? `${MAX_IMPORT_FILES} files is the most one import takes.` : "or drop them here"}
            </span>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".json,application/json"
              className="hidden"
              onChange={handleInputChange}
            />
          </div>

          {files.length > 0 && (
            <ul className="space-y-2">
              {files.map((file, index) => {
                const key = fileKey(file);
                const known = resultByKey.get(key);
                const result = known?.result;
                return (
                  <li
                    key={key}
                    className={`rounded-md border px-3 py-2 ${
                      result && result.status !== "ok" ? "border-destructive/40" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <FileStatusIcon result={result} isChecking={isChecking} />
                      <span className="min-w-0 flex-1 truncate text-sm font-medium" title={file.name}>
                        {file.name}
                      </span>
                      <Button
                        ref={(node) => {
                          if (node) removeButtonRefs.current.set(key, node);
                          else removeButtonRefs.current.delete(key);
                        }}
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0 text-muted-foreground"
                        aria-label={`Remove ${file.name}`}
                        title="Remove"
                        disabled={isImporting}
                        onClick={() => removeFile(index)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    {known && (
                      <FileDetails
                        result={known.result}
                        position={known.position}
                        files={checked?.result.files ?? []}
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* sm:justify-between is required: DialogFooter ships sm:justify-end. */}
        <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between gap-3 sm:justify-between">
          <span className={`text-xs ${footerIsProblem ? "text-destructive" : "text-muted-foreground"}`}>
            {footerText}
          </span>
          <Button size="sm" disabled={!canImport} loading={isImporting} onClick={() => void handleImport()}>
            Import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ImportFromFilesDialog;
