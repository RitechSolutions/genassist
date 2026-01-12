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
import { Loader2, Upload, ChevronDown, ChevronUp, Download } from "lucide-react";
import { toast } from "react-hot-toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  createFineTuneJob,
  getFineTunableModels,
  uploadFineTuneFile,
} from "@/services/openaiFineTune";
import type { CreateFineTuneJobRequest } from "@/interfaces/fineTune.interface";
import { Tooltip } from "@/components/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

interface FineTuneJobDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onJobCreated: () => void;
}

export function FineTuneJobDialog({
  isOpen,
  onOpenChange,
  onJobCreated,
}: FineTuneJobDialogProps) {
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const [model, setModel] = useState<string>("");
  const [suffix, setSuffix] = useState<string>("");
  const [nEpochs, setNEpochs] = useState<number>(1);
  const [batchSize, setBatchSize] = useState<number>(4);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [modelTouched, setModelTouched] = useState(false);

  const [trainingFile, setTrainingFile] = useState<{ id: string; name: string } | null>(null);
  const [validationFile, setValidationFile] = useState<{ id: string; name: string } | null>(null);
  const [uploadingTraining, setUploadingTraining] = useState(false);
  const [uploadingValidation, setUploadingValidation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isCloseConfirmOpen, setIsCloseConfirmOpen] = useState(false);
  const toggleAdvanced = () => setShowAdvanced((v) => !v);
  const handleAdvancedKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleAdvanced();
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchModels();
    }
  }, [isOpen]);

  const fetchModels = async () => {
    try {
      setLoadingModels(true);
      const list = await getFineTunableModels();
      setModels(list);
    } catch (err) {
      toast.error("Failed to load models");
    } finally {
      setLoadingModels(false);
    }
  };

  const handleUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
    type: "training" | "validation"
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      if (type === "training") setUploadingTraining(true);
      else setUploadingValidation(true);

      const res = await uploadFineTuneFile(file, "fine-tune");
      const info = { id: res.id, name: res.filename || file.name };
      if (type === "training") setTrainingFile(info);
      else setValidationFile(info);
      toast.success(`${type === "training" ? "Training" : "Validation"} file uploaded`);
    } catch (err) {
      toast.error("File upload failed");
    } finally {
      if (type === "training") setUploadingTraining(false);
      else setUploadingValidation(false);
    }
  };

  const resetForm = () => {
    setModel("");
    setSuffix("");
    setNEpochs(1);
    setBatchSize(4);
    setShowAdvanced(false);
    setModelTouched(false);
    setTrainingFile(null);
    setValidationFile(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const missing: string[] = [];
    if (!trainingFile?.id) missing.push("training file");
    if (!validationFile?.id) missing.push("validation file");
    if (!model) missing.push("model");
    if (!suffix) missing.push("suffix");

    if (missing.length > 0) {
      toast.error(`Please provide: ${missing.join(", ")}`);
      return;
    }

    const payload: CreateFineTuneJobRequest = {
      training_file: trainingFile!.id,
      model,
      validation_file: validationFile!.id,
      suffix,
      hyperparameters: {
        n_epochs: Number(nEpochs) || 1,
        batch_size: Number(batchSize) || 4,
      },
    };

    setSubmitting(true);
    try {
      await createFineTuneJob(payload);
      toast.success("Fine-tune job created");
      onJobCreated();
      onOpenChange(false);
      resetForm();
    } catch (err) {
      toast.error("Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  const suffixPlaceholder = "my-custom-model";
  const derivedNamePreview = `${model || "gpt-3.5-turbo-1106"}-${suffix || suffixPlaceholder}`;
  const hasUploads = Boolean(trainingFile || validationFile);

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

  const handleSaveAndClose = () => {
    setIsCloseConfirmOpen(false);
    onOpenChange(false);
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
        <DialogContent className="sm:max-w-[620px] p-0 overflow-hidden">
          <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden">
            <DialogHeader className="p-6">
              <DialogTitle className="text-xl">New Fine-Tune</DialogTitle>
            </DialogHeader>

          <div className="px-6 pb-6 space-y-6">
            <div className="space-y-2">
              <Label>Model</Label>
              {loadingModels ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              ) : (
                <Select
                  value={model}
                  onValueChange={(v) => {
                    setModel(v);
                    setModelTouched(true);
                  }}
                >
                  <SelectTrigger
                    className="w-full"
                    onFocus={() => setModelTouched(true)}
                    onClick={() => setModelTouched(true)}
                  >
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {models.map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                type="text"
                placeholder={suffixPlaceholder}
                value={suffix}
                onChange={(e) => setSuffix(e.target.value)}
              />
              {modelTouched && model && (
                <div className="text-sm text-muted-foreground">{derivedNamePreview}</div>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Training file</Label>
                  <Tooltip
                    content="The dataset used to teach the model desired behavior. Must be properly formatted (JSONL) and representative of real usage"
                    contentClassName="w-48"
                    iconClassName="h-4 w-4"
                  />
                </div>
                <a
                  href="/sample-files/traning_sample.jsonl"
                  download="training_sample.jsonl"
                  className="flex items-center gap-1 text-xs hover:text-foreground"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download Sample File</span>
                </a>
              </div>
              <label className="border border-dashed border-muted-foreground/40 rounded-lg p-4 flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-muted-foreground/70 transition">
                <Upload className="w-5 h-5 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Select file to upload</span>
                <Input
                  type="file"
                  accept=".json,.jsonl,application/json"
                  className="hidden"
                  onChange={(e) => handleUpload(e, "training")}
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
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Validation file</Label>
                  <Tooltip
                    content="A separate dataset used to evaluate model performance during training and detect overfitting"
                    contentClassName="w-48"
                    iconClassName="h-4 w-4"
                  />
                </div>
                <a
                  href="/sample-files/validation_sample.jsonl"
                  download="validation_sample.jsonl"
                  className="flex items-center gap-1 text-xs hover:text-foreground"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download Sample File</span>
                </a>
              </div>
              <label className="border border-dashed border-muted-foreground/40 rounded-lg p-4 flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-muted-foreground/70 transition">
                <Upload className="w-5 h-5 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Select file to upload</span>
                <Input
                  type="file"
                  accept=".json,.jsonl,application/json"
                  className="hidden"
                  onChange={(e) => handleUpload(e, "validation")}
                />
              </label>
              {uploadingValidation && (
                <div className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Uploading validation file...
                </div>
              )}
              {validationFile && (
                <div className="text-sm text-green-700">Uploaded: {validationFile.name}</div>
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
                <span className="text-sm font-semibold">Advanced</span>
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
                    <Label>n_epochs</Label>
                    <Input
                      type="number"
                      min={1}
                      value={nEpochs}
                      onChange={(e) => setNEpochs(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Batch Size</Label>
                    <Input
                      type="number"
                      min={1}
                      value={batchSize}
                      onChange={(e) => setBatchSize(Number(e.target.value))}
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
        onConfirm={async () => {
          handleSaveAndClose();
        }}
        onCancel={handleDiscard}
        isInProgress={false}
        primaryButtonText="Save"
        secondaryButtonText="Discard"
        title="Save changes before closing?"
        description="You have uploaded files. Save to keep your selections or discard to reset the form."
      />
    </>
  );
}