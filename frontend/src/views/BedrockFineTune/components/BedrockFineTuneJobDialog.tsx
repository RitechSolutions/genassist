import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Info, Loader2, Upload } from "lucide-react";
import { Switch } from "@/components/switch";
import { toast } from "react-hot-toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  createBedrockFineTuneJob,
  getBedrockFineTunableModels,
  uploadBedrockTrainingData,
} from "@/services/bedrockFineTune";
import type { CreateBedrockFineTuneJobRequest } from "@/interfaces/bedrockFineTune.interface";
import type { S3FileRef } from "@/views/BedrockFineTune/types";
import { Tooltip } from "@/components/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";

interface BedrockFineTuneJobDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onJobCreated: () => void;
  onOpenGenerate: (target: "training" | "validation") => void;
  onOpenSelectFile: (target: "training" | "validation") => void;
  onSetData: (target: "training" | "validation", data: S3FileRef | null) => void;
  trainingData: S3FileRef | null;
  validationData: S3FileRef | null;
}

export function BedrockFineTuneJobDialog({
  isOpen,
  onOpenChange,
  onJobCreated,
  onOpenGenerate,
  onOpenSelectFile,
  onSetData,
  trainingData,
  validationData,
}: BedrockFineTuneJobDialogProps) {
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const [model, setModel] = useState<string>("");
  const [suffix, setSuffix] = useState<string>("");
  const [epochCount, setEpochCount] = useState<number | "">("");
  const [learningRate, setLearningRate] = useState<string>("");
  const [warmupSteps, setWarmupSteps] = useState<number | "">("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [uploadingTraining, setUploadingTraining] = useState(false);
  const [uploadingValidation, setUploadingValidation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [isCloseConfirmOpen, setIsCloseConfirmOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchModels();
    }
  }, [isOpen]);

  const fetchModels = async () => {
    try {
      setLoadingModels(true);
      const list = await getBedrockFineTunableModels();
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

      const res = await uploadBedrockTrainingData(file);
      onSetData(type, { s3_uri: res.s3_uri, name: res.filename || file.name });
      toast.success(`${type === "training" ? "Training" : "Validation"} data uploaded`);
    } catch (err) {
      toast.error("File upload failed");
    } finally {
      if (type === "training") setUploadingTraining(false);
      else setUploadingValidation(false);
    }
  };

  const handleUriChange = (type: "training" | "validation", value: string) => {
    const trimmed = value.trim();
    onSetData(type, trimmed ? { s3_uri: trimmed, name: trimmed } : null);
  };

  const resetForm = () => {
    setModel("");
    setSuffix("");
    setEpochCount("");
    setLearningRate("");
    setWarmupSteps("");
    setShowAdvanced(false);
    onSetData("training", null);
    onSetData("validation", null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const missing: string[] = [];
    if (!trainingData?.s3_uri) missing.push("training data");
    if (!model) missing.push("base model");

    if (missing.length > 0) {
      toast.error(`Please provide: ${missing.join(", ")}`);
      return;
    }

    const hyperparameters: Record<string, unknown> = {};
    if (showAdvanced) {
      if (epochCount !== "") hyperparameters.epochCount = Number(epochCount);
      if (learningRate.trim()) hyperparameters.learningRate = learningRate.trim();
      if (warmupSteps !== "") hyperparameters.learningRateWarmupSteps = Number(warmupSteps);
    }

    const payload: CreateBedrockFineTuneJobRequest = {
      training_data_s3_uri: trainingData!.s3_uri,
      base_model_id: model,
      ...(validationData?.s3_uri ? { validation_data_s3_uri: validationData.s3_uri } : {}),
      ...(suffix.trim() ? { suffix: suffix.trim() } : {}),
      ...(Object.keys(hyperparameters).length > 0 ? { hyperparameters } : {}),
    };

    setSubmitting(true);
    try {
      await createBedrockFineTuneJob(payload);
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

  const hasData = Boolean(trainingData || validationData);

  const handleDialogOpenChange = (open: boolean) => {
    if (open) {
      onOpenChange(true);
      return;
    }
    if (hasData) {
      setIsCloseConfirmOpen(true);
      return;
    }
    resetForm();
    onOpenChange(false);
  };

  const handleDiscard = () => {
    resetForm();
    setIsCloseConfirmOpen(false);
    setSubmitting(false);
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
              <DialogTitle className="text-xl">New Bedrock Fine-Tune</DialogTitle>
            </DialogHeader>

            <div className="px-6 pb-6 space-y-6">
              <div className="flex items-start gap-3 rounded-lg border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                <Info className="h-4 w-4 mt-0.5 shrink-0" />
                <p>
                  Amazon Nova fine-tuning runs in us-east-1 and is billed per-token on-demand once
                  deployed.
                </p>
              </div>

              <div className="space-y-2">
                <Label>Base model</Label>
                {loadingModels ? (
                  <div className="flex items-center justify-center p-4">
                    <Loader2 className="w-5 h-5 animate-spin" />
                  </div>
                ) : (
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select base model" />
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
                <Label>Name (suffix)</Label>
                <Input
                  type="text"
                  placeholder="my-custom-model"
                  value={suffix}
                  onChange={(e) => setSuffix(e.target.value)}
                  maxLength={40}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label>Training data</Label>
                  <Tooltip
                    content="The dataset used to teach the model desired behavior. Upload a JSONL file to S3, or paste an existing s3:// URI"
                    contentClassName="w-48"
                    iconClassName="h-4 w-4"
                  />
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
                    <Loader2 className="w-4 h-4 animate-spin" /> Uploading training data...
                  </div>
                )}
                <Input
                  type="text"
                  placeholder="or paste an s3:// URI"
                  value={trainingData?.s3_uri ?? ""}
                  onChange={(e) => handleUriChange("training", e.target.value)}
                />
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 w-fit"
                    onClick={() => onOpenSelectFile("training")}
                  >
                    Select from uploaded files
                  </button>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 w-fit"
                    onClick={() => onOpenGenerate("training")}
                  >
                    Generate from conversations
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label>Validation data (optional)</Label>
                  <Tooltip
                    content="A separate dataset used to evaluate model performance during training. Upload a JSONL file to S3, or paste an existing s3:// URI"
                    contentClassName="w-48"
                    iconClassName="h-4 w-4"
                  />
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
                    <Loader2 className="w-4 h-4 animate-spin" /> Uploading validation data...
                  </div>
                )}
                <Input
                  type="text"
                  placeholder="or paste an s3:// URI"
                  value={validationData?.s3_uri ?? ""}
                  onChange={(e) => handleUriChange("validation", e.target.value)}
                />
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 w-fit"
                    onClick={() => onOpenSelectFile("validation")}
                  >
                    Select from uploaded files
                  </button>
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 w-fit"
                    onClick={() => onOpenGenerate("validation")}
                  >
                    Generate from conversations
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2 border-t pt-4">
                <div className="flex-1" />
                <div className="flex items-center gap-2">
                  <Label htmlFor="show_advanced">Advanced</Label>
                  <Switch id="show_advanced" checked={showAdvanced} onCheckedChange={setShowAdvanced} />
                </div>
              </div>

              {showAdvanced && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Epochs</Label>
                    <Input
                      type="number"
                      min={1}
                      max={5}
                      placeholder="e.g. 2"
                      value={epochCount}
                      onChange={(e) => setEpochCount(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                    <p className="text-xs text-muted-foreground">1–5 (default 2)</p>
                  </div>
                  <div className="space-y-2">
                    <Label>Learning rate</Label>
                    <Input
                      type="text"
                      placeholder="e.g. 0.00001"
                      value={learningRate}
                      onChange={(e) => setLearningRate(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">1e-6 – 1e-4 (default 1e-5)</p>
                  </div>
                  <div className="space-y-2">
                    <Label>Learning rate warmup steps</Label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      placeholder="e.g. 10"
                      value={warmupSteps}
                      onChange={(e) => setWarmupSteps(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                    <p className="text-xs text-muted-foreground">0–100 (default 10)</p>
                  </div>
                </div>
              )}
            </div>

            <DialogFooter className="px-6 py-4 border-t flex items-center justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>
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
        description="You have selected training data. Save to keep your selections or discard to reset the form."
      />
    </>
  );
}
