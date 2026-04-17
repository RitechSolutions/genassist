import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { ScrollArea } from "@/components/scroll-area";
import { Loader2, ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
import { cn } from "@/helpers/utils";
import { toast } from "react-hot-toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  createLocalFineTuneJob,
  listLocalFineTuneSupportedModels,
} from "@/services/localFineTune";
import { getAccessToken } from "@/services/auth";
import { listFileManagerFiles } from "@/services/fileManager";
import type {
  CreateLocalFineTuneJobRequest,
  LocalFineTuneHyperparameters,
  LocalFineTuneSupportedModel,
} from "@/interfaces/localFineTune.interface";
import type { FileManagerFileRecord } from "@/interfaces/file-manager.interface";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

const SUPPORTED_MODELS_PAGE_SIZE = 10;
const TRAINING_FILES_PAGE_SIZE = 10;
const FINE_TUNE_FILE_TAG = "fine-tune";

function fileManagerDisplayName(file: {
  original_filename?: string | null;
  name: string;
}): string {
  return file.original_filename?.trim() || file.name;
}
const DEFAULT_HYPERPARAMETERS: LocalFineTuneHyperparameters = {
  num_train_epochs: 1,
  per_device_train_batch_size: 2,
  gradient_accumulation_steps: 4,
  learning_rate: 2e-4,
  lora_r: 16,
  lora_alpha: 16,
  max_seq_length: 2048,
  logging_steps: 1,
  save_steps: 1,
  eval_steps: 1,
  warmup_steps: 10,
};

interface LocalFineTuneJobDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onJobCreated: () => void;
}

export function LocalFineTuneJobDialog({
  isOpen,
  onOpenChange,
  onJobCreated,
}: LocalFineTuneJobDialogProps) {
  const [supportedModels, setSupportedModels] = useState<LocalFineTuneSupportedModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [managerFiles, setManagerFiles] = useState<FileManagerFileRecord[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesLoadingMore, setFilesLoadingMore] = useState(false);
  const [hasMoreFiles, setHasMoreFiles] = useState(true);
  const [trainingFilePickerOpen, setTrainingFilePickerOpen] = useState(false);
  const [trainingMenuWidth, setTrainingMenuWidth] = useState<number | null>(null);
  const trainingFilesBlockRef = useRef<HTMLDivElement>(null);
  const fetchMoreLock = useRef(false);
  const [selectedTrainingFile, setSelectedTrainingFile] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isCloseConfirmOpen, setIsCloseConfirmOpen] = useState(false);
  const [suffix, setSuffix] = useState("");

  const [hyperparams, setHyperparams] = useState<LocalFineTuneHyperparameters>({
    ...DEFAULT_HYPERPARAMETERS,
  });

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    (async () => {
      setModelsLoading(true);
      try {
        const list = await listLocalFineTuneSupportedModels(0, SUPPORTED_MODELS_PAGE_SIZE);
        if (cancelled) return;
        setSupportedModels(list);
        setSelectedModelId((prev) => {
          if (prev && list.some((m) => m.id === prev)) return prev;
          return list[0]?.id ?? "";
        });
      } catch {
        if (!cancelled) {
          setSupportedModels([]);
          setSelectedModelId("");
          toast.error("Could not load supported models");
        }
      } finally {
        if (!cancelled) setModelsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setManagerFiles([]);
      setHasMoreFiles(true);
      setTrainingFilePickerOpen(false);
      fetchMoreLock.current = false;
      return;
    }
    let cancelled = false;
    (async () => {
      setFilesLoading(true);
      try {
        const list = await listFileManagerFiles({
          limit: TRAINING_FILES_PAGE_SIZE,
          offset: 0,
          tag: FINE_TUNE_FILE_TAG,
        });
        if (cancelled) return;
        setManagerFiles(list);
        setHasMoreFiles(list.length === TRAINING_FILES_PAGE_SIZE);
      } catch {
        if (!cancelled) {
          setManagerFiles([]);
          setHasMoreFiles(false);
          toast.error("Could not load files from File Manager");
        }
      } finally {
        if (!cancelled) setFilesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const loadMoreTrainingFiles = useCallback(async () => {
    if (!hasMoreFiles || filesLoading || fetchMoreLock.current) return;
    fetchMoreLock.current = true;
    setFilesLoadingMore(true);
    try {
      const offset = managerFiles.length;
      const list = await listFileManagerFiles({
        limit: TRAINING_FILES_PAGE_SIZE,
        offset,
        tag: FINE_TUNE_FILE_TAG,
      });
      setManagerFiles((prev) => {
        const seen = new Set(prev.map((f) => f.id));
        const next = [...prev];
        for (const f of list) {
          if (!seen.has(f.id)) {
            seen.add(f.id);
            next.push(f);
          }
        }
        return next;
      });
      setHasMoreFiles(list.length === TRAINING_FILES_PAGE_SIZE);
    } catch {
      toast.error("Could not load more files");
    } finally {
      fetchMoreLock.current = false;
      setFilesLoadingMore(false);
    }
  }, [hasMoreFiles, filesLoading, managerFiles.length]);

  useLayoutEffect(() => {
    if (trainingFilePickerOpen && trainingFilesBlockRef.current) {
      setTrainingMenuWidth(trainingFilesBlockRef.current.offsetWidth);
    }
  }, [trainingFilePickerOpen]);

  const onTrainingFilesScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    if (el.scrollHeight - el.scrollTop - el.clientHeight > 48) return;
    void loadMoreTrainingFiles();
  };

  const toggleAdvanced = () => setShowAdvanced((v) => !v);
  const handleAdvancedKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleAdvanced();
    }
  };

  const trainingFileSelectItems = (() => {
    const rows = [...managerFiles];
    if (
      selectedTrainingFile &&
      !rows.some((f) => f.id === selectedTrainingFile.id)
    ) {
      rows.unshift({
        id: selectedTrainingFile.id,
        name: selectedTrainingFile.name,
        original_filename: selectedTrainingFile.name,
        path: "",
        storage_path: "",
        storage_provider: "local",
        created_at: "",
        updated_at: "",
        is_deleted: 0,
      });
    }
    return rows;
  })();

  const resetForm = () => {
    setSelectedModelId(supportedModels[0]?.id ?? "");
    setSelectedTrainingFile(null);
    setTrainingFilePickerOpen(false);
    setShowAdvanced(false);
    setSuffix("");
    setHyperparams({ ...DEFAULT_HYPERPARAMETERS });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) {
      toast.error("You must be logged in to create a job");
      return;
    }
    if (!selectedTrainingFile?.id) {
      toast.error("Please select a training file");
      return;
    }
    if (!selectedModelId?.trim()) {
      toast.error("Please select a model");
      return;
    }

    const trimmedSuffix = suffix.trim();

    const payload: CreateLocalFineTuneJobRequest = {
      training_file: selectedTrainingFile.id,
      file_token: token,
      model_id: selectedModelId.trim(),
      suffix: trimmedSuffix || null,
      tool_training_mode: "assistant_and_tools",
      remote_files: true,
      cleanup_files: false,
      hyperparameters: {
        num_train_epochs: hyperparams.num_train_epochs ?? 1,
        per_device_train_batch_size: hyperparams.per_device_train_batch_size ?? 2,
        gradient_accumulation_steps: hyperparams.gradient_accumulation_steps ?? 4,
        learning_rate: hyperparams.learning_rate ?? 2e-4,
        lora_r: hyperparams.lora_r ?? 16,
        lora_alpha: hyperparams.lora_alpha ?? 16,
        max_seq_length: hyperparams.max_seq_length ?? 2048,
        logging_steps: hyperparams.logging_steps ?? 1,
        save_steps: hyperparams.save_steps ?? 1,
        eval_steps: hyperparams.eval_steps ?? 1,
        warmup_steps: hyperparams.warmup_steps ?? 10,
      },
    };

    setSubmitting(true);
    try {
      await createLocalFineTuneJob(payload);
      toast.success("Local fine-tune job created");
      onJobCreated();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      toast.error("Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  const hasFormContent =
    Boolean(selectedTrainingFile) || Boolean(suffix.trim());

  const handleDialogOpenChange = (open: boolean) => {
    if (open) {
      onOpenChange(true);
      return;
    }
    if (hasFormContent) {
      setIsCloseConfirmOpen(true);
      return;
    }
    resetForm();
    onOpenChange(false);
  };

  const handleDiscard = () => {
    resetForm();
    setIsCloseConfirmOpen(false);
    onOpenChange(false);
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="sm:max-w-[620px] p-0 overflow-hidden">
          <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden">
            <DialogHeader className="p-6">
              <DialogTitle className="text-xl">New Local Fine-Tune</DialogTitle>
            </DialogHeader>

            <div className="px-6 pb-6 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="local-ft-suffix">Job name</Label>
                <Input
                  id="local-ft-suffix"
                  placeholder="Job name"
                  value={suffix}
                  onChange={(e) => setSuffix(e.target.value)}
                  className="rounded-lg"
                  autoComplete="off"
                />
              </div>

              <div className="space-y-2">
                <Label>Model</Label>
                {modelsLoading ? (
                  <div className="text-sm text-muted-foreground flex items-center gap-2 h-10">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading models…
                  </div>
                ) : supportedModels.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No models available. Check the local fine-tune service and try again.
                  </p>
                ) : (
                  <Select
                    value={selectedModelId}
                    onValueChange={setSelectedModelId}
                  >
                    <SelectTrigger className="rounded-lg">
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {supportedModels.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div ref={trainingFilesBlockRef} className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>Training file</Label>
                  <a
                    href="/sample-files/traning_sample.jsonl"
                    download="training_sample.jsonl"
                    className="flex items-center gap-1 text-xs hover:text-foreground shrink-0"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Download Sample File</span>
                  </a>
                </div>
                <p className="text-xs text-muted-foreground">
                  Only files tagged{" "}
                  <span className="font-mono">{FINE_TUNE_FILE_TAG}</span> in File Manager appear here.
                </p>
                {filesLoading ? (
                  <div className="text-sm text-muted-foreground flex items-center gap-2 h-10">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading files…
                  </div>
                ) : trainingFileSelectItems.length === 0 ? (
                  <div className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/25 py-8 px-4">
                    <FileText className="w-4 h-4 text-muted-foreground/70 shrink-0" />
                    <p className="text-sm text-muted-foreground">No files</p>
                  </div>
                ) : (
                  <Popover
                    open={trainingFilePickerOpen}
                    onOpenChange={setTrainingFilePickerOpen}
                  >
                    <PopoverTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        role="combobox"
                        aria-expanded={trainingFilePickerOpen}
                        className={cn(
                          "h-10 w-full justify-between rounded-lg border-input bg-background px-3 py-2 text-sm font-normal shadow-sm hover:bg-accent/50"
                        )}
                      >
                        <span className="truncate text-left">
                          {selectedTrainingFile
                            ? selectedTrainingFile.name
                            : "Select a training file"}
                        </span>
                        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent
                      align="start"
                      sideOffset={4}
                      className="z-[1400] w-auto max-w-[calc(100vw-2rem)] p-0"
                      style={
                        trainingMenuWidth != null
                          ? { width: trainingMenuWidth }
                          : undefined
                      }
                      onOpenAutoFocus={(ev) => ev.preventDefault()}
                      onWheel={(e) => e.stopPropagation()}
                    >
                      <ScrollArea
                        className="h-[min(320px,50vh)] w-full"
                        viewportProps={{
                          onScroll: onTrainingFilesScroll,
                          onWheel: (e) => e.stopPropagation(),
                          className: "touch-pan-y overscroll-contain max-h-[min(320px,50vh)]",
                        }}
                      >
                        <div className="p-1">
                          {trainingFileSelectItems.map((f) => (
                            <button
                              key={f.id}
                              type="button"
                              className={cn(
                                "relative flex w-full cursor-pointer select-none items-center rounded-sm py-2 px-3 text-left text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground",
                                selectedTrainingFile?.id === f.id &&
                                  "bg-accent/70 text-accent-foreground"
                              )}
                              onClick={() => {
                                setSelectedTrainingFile({
                                  id: f.id,
                                  name: fileManagerDisplayName(f),
                                });
                                setTrainingFilePickerOpen(false);
                              }}
                            >
                              <span className="truncate">
                                {fileManagerDisplayName(f)}
                                {f.file_extension ? (
                                  <span className="text-muted-foreground">
                                    {" "}
                                    ({f.file_extension})
                                  </span>
                                ) : null}
                              </span>
                            </button>
                          ))}
                          {filesLoadingMore ? (
                            <div className="flex justify-center py-3 text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin" />
                            </div>
                          ) : null}
                        </div>
                      </ScrollArea>
                    </PopoverContent>
                  </Popover>
                )}
                {selectedTrainingFile && (
                  <div className="text-sm text-green-700">
                    Selected: {selectedTrainingFile.name}{" "}
                    <span className="text-muted-foreground font-mono text-xs">
                      ({selectedTrainingFile.id})
                    </span>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div
                  className="flex items-center justify-between cursor-pointer select-none"
                  onClick={toggleAdvanced}
                  role="button"
                  tabIndex={0}
                  onKeyDown={handleAdvancedKeyDown}
                >
                  <span className="text-sm font-semibold">Advanced (hyperparameters)</span>
                  <span className="h-8 w-8 flex items-center justify-center text-muted-foreground">
                    {showAdvanced ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronUp className="h-4 w-4" />
                    )}
                  </span>
                </div>
                {showAdvanced && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>num_train_epochs</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.num_train_epochs ?? 1}
                        onChange={(e) =>
                          setHyperparams((p) => ({ ...p, num_train_epochs: Number(e.target.value) }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>per_device_train_batch_size</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.per_device_train_batch_size ?? 2}
                        onChange={(e) =>
                          setHyperparams((p) => ({
                            ...p,
                            per_device_train_batch_size: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>gradient_accumulation_steps</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.gradient_accumulation_steps ?? 4}
                        onChange={(e) =>
                          setHyperparams((p) => ({
                            ...p,
                            gradient_accumulation_steps: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>learning_rate</Label>
                      <Input
                        type="number"
                        step="any"
                        value={hyperparams.learning_rate ?? 2e-4}
                        onChange={(e) =>
                          setHyperparams((p) => ({
                            ...p,
                            learning_rate: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>lora_r</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.lora_r ?? 16}
                        onChange={(e) =>
                          setHyperparams((p) => ({ ...p, lora_r: Number(e.target.value) }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>lora_alpha</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.lora_alpha ?? 16}
                        onChange={(e) =>
                          setHyperparams((p) => ({ ...p, lora_alpha: Number(e.target.value) }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>max_seq_length</Label>
                      <Input
                        type="number"
                        min={1}
                        value={hyperparams.max_seq_length ?? 2048}
                        onChange={(e) =>
                          setHyperparams((p) => ({
                            ...p,
                            max_seq_length: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>warmup_steps</Label>
                      <Input
                        type="number"
                        min={0}
                        value={hyperparams.warmup_steps ?? 10}
                        onChange={(e) =>
                          setHyperparams((p) => ({
                            ...p,
                            warmup_steps: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <DialogFooter className="px-6 py-4 border-t flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleDialogOpenChange(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        isOpen={isCloseConfirmOpen}
        onOpenChange={setIsCloseConfirmOpen}
        onConfirm={() => {
          setIsCloseConfirmOpen(false);
          onOpenChange(false);
        }}
        onCancel={handleDiscard}
        isInProgress={false}
        primaryButtonText="Save"
        secondaryButtonText="Discard"
        title="Save changes before closing?"
        description="You have entered a job name and/or selected a training file. Save to keep your work or discard to reset the form."
      />
    </>
  );
}
