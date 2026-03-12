import { useState } from "react";
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
import { Loader2, Upload, ChevronDown, ChevronUp, Download } from "lucide-react";
import { toast } from "react-hot-toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createLocalFineTuneJob } from "@/services/localFineTune";
import { uploadFiles } from "@/services/api";
import { getAccessToken } from "@/services/auth";
import type {
  CreateLocalFineTuneJobRequest,
  LocalFineTuneHyperparameters,
} from "@/interfaces/localFineTune.interface";

const DEFAULT_MODEL = "unsloth/Meta-Llama-3.1-8B";
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
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [trainingFile, setTrainingFile] = useState<{ id: string; name: string } | null>(null);
  const [uploadingTraining, setUploadingTraining] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isCloseConfirmOpen, setIsCloseConfirmOpen] = useState(false);

  const [hyperparams, setHyperparams] = useState<LocalFineTuneHyperparameters>({
    ...DEFAULT_HYPERPARAMETERS,
  });

  const toggleAdvanced = () => setShowAdvanced((v) => !v);
  const handleAdvancedKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleAdvanced();
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setUploadingTraining(true);
      const results = await uploadFiles([file]);
      const first = results?.[0];
      const rawFilename = (first as { filename?: string })?.filename ?? first?.filename;
      const fileId = rawFilename ? String(rawFilename).replace(/\.jsonl$/i, "") : null;
      if (!fileId) {
        toast.error("Upload succeeded but no file ID returned");
        return;
      }
      setTrainingFile({
        id: fileId,
        name: (first as { original_filename?: string })?.original_filename ?? first?.filename ?? file.name,
      });
      toast.success("Training file uploaded");
    } catch (err) {
      toast.error("File upload failed");
    } finally {
      setUploadingTraining(false);
    }
  };

  const resetForm = () => {
    setModel(DEFAULT_MODEL);
    setTrainingFile(null);
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
    if (!trainingFile?.id) {
      toast.error("Please upload a training file");
      return;
    }
    if (!model?.trim()) {
      toast.error("Please enter a model");
      return;
    }

    const payload: CreateLocalFineTuneJobRequest = {
      training_file: trainingFile.id,
      file_token: token,
      model: model.trim(),
      tool_training_mode: "assistant_and_tools",
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

  const hasUploads = Boolean(trainingFile);

  const handleDialogOpenChange = (open: boolean) => {
    if (open) {
      onOpenChange(true);
      return;
    }
    if (hasUploads) {
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
                <Input
                  type="text"
                  placeholder={DEFAULT_MODEL}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Training file</Label>
                  <a
                    href="/sample-files/traning_sample.jsonl"
                    download="training_sample.jsonl"
                    className="flex items-center gap-1 text-xs hover:text-foreground"
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>Download Sample File</span>
                  </a>
                </div>
                <p className="text-xs text-muted-foreground">
                  File is uploaded to the same storage used for Knowledge Base. JSONL format.
                </p>
                <label className="border border-dashed border-muted-foreground/40 rounded-lg p-4 flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-muted-foreground/70 transition">
                  <Upload className="w-5 h-5 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Select file to upload</span>
                  <Input
                    type="file"
                    accept=".json,.jsonl,application/json"
                    className="hidden"
                    onChange={handleUpload}
                  />
                </label>
                {uploadingTraining && (
                  <div className="text-sm text-muted-foreground flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Uploading training file...
                  </div>
                )}
                {trainingFile && (
                  <div className="text-sm text-green-700">Uploaded: {trainingFile.name}</div>
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
        description="You have uploaded a file. Save to keep your selection or discard to reset the form."
      />
    </>
  );
}
