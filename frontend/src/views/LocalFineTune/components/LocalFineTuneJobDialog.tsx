import { useEffect, useState } from "react";
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
import { Loader2, ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
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
  const [trainingFilePage, setTrainingFilePage] = useState(0);
  const [managerFiles, setManagerFiles] = useState<FileManagerFileRecord[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedTrainingFile, setSelectedTrainingFile] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isCloseConfirmOpen, setIsCloseConfirmOpen] = useState(false);

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
    if (!isOpen) return;
    let cancelled = false;
    (async () => {
      setFilesLoading(true);
      try {
        const list = await listFileManagerFiles({
          limit: TRAINING_FILES_PAGE_SIZE,
          offset: trainingFilePage * TRAINING_FILES_PAGE_SIZE,
        });
        if (cancelled) return;
        setManagerFiles(list);
      } catch {
        if (!cancelled) {
          setManagerFiles([]);
          toast.error("Could not load files from File Manager");
        }
      } finally {
        if (!cancelled) setFilesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen, trainingFilePage]);

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
    setTrainingFilePage(0);
    setShowAdvanced(false);
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

    const payload: CreateLocalFineTuneJobRequest = {
      training_file: selectedTrainingFile.id,
      file_token: token,
      model_id: selectedModelId.trim(),
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

  const hasTrainingFileChoice = Boolean(selectedTrainingFile);

  const handleDialogOpenChange = (open: boolean) => {
    if (open) {
      onOpenChange(true);
      return;
    }
    if (hasTrainingFileChoice) {
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

              <div className="space-y-2">
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
                {filesLoading ? (
                  <div className="text-sm text-muted-foreground flex items-center gap-2 h-10">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading files…
                  </div>
                ) : trainingFileSelectItems.length === 0 ? (
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    No files in File Manager for this page. Upload files under Knowledge Base / File
                    Manager or change page.
                  </p>
                ) : (
                  <Select
                    value={selectedTrainingFile?.id}
                    onValueChange={(id) => {
                      const f = trainingFileSelectItems.find((row) => row.id === id);
                      setSelectedTrainingFile(
                        f
                          ? { id: f.id, name: fileManagerDisplayName(f) }
                          : null
                      );
                    }}
                  >
                    <SelectTrigger className="rounded-lg">
                      <SelectValue placeholder="Select a training file" />
                    </SelectTrigger>
                    <SelectContent>
                      {trainingFileSelectItems.map((f) => (
                        <SelectItem key={f.id} value={f.id}>
                          <span className="truncate">
                            {fileManagerDisplayName(f)}
                            {f.file_extension ? (
                              <span className="text-muted-foreground"> ({f.file_extension})</span>
                            ) : null}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <div className="flex items-center justify-between gap-2 pt-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={filesLoading || trainingFilePage === 0}
                    onClick={() => setTrainingFilePage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    Page {trainingFilePage + 1}
                    {managerFiles.length === TRAINING_FILES_PAGE_SIZE ? " · more may exist" : ""}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={
                      filesLoading || managerFiles.length < TRAINING_FILES_PAGE_SIZE
                    }
                    onClick={() => setTrainingFilePage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
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
        description="You have selected a training file. Save to keep your selection or discard to reset the form."
      />
    </>
  );
}
