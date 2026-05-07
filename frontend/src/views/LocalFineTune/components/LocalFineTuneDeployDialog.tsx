import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/label";
import { Button } from "@/components/button";
import { Switch } from "@/components/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/select";
import { Loader2 } from "lucide-react";
import { toast } from "react-hot-toast";
import { createDeployment, listSystemGpus } from "@/services/localFineTune";
import type { CreateDeploymentRequest, GpuInfo } from "@/interfaces/localFineTune.interface";

interface LocalFineTuneDeployDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
  jobDisplayName: string;
  onDeployed: () => void;
}

function sanitizeDeploymentId(jobId: string): string {
  return `${jobId.replace(/[^a-z0-9-]/gi, "-").toLowerCase().slice(0, 40)}-deploy`;
}

export function LocalFineTuneDeployDialog({
  isOpen,
  onOpenChange,
  jobId,
  jobDisplayName,
  onDeployed,
}: LocalFineTuneDeployDialogProps) {
  const [deploymentId, setDeploymentId] = useState("");
  const [maxModelLen, setMaxModelLen] = useState<number | "">("");
  const [gpuMemUtil, setGpuMemUtil] = useState<number | "">(0.9);
  const [dtype, setDtype] = useState("auto");
  const [gpuId, setGpuId] = useState<number | "">("");
  const [tensorParallelSize, setTensorParallelSize] = useState<number>(1);
  const [availableGpus, setAvailableGpus] = useState<GpuInfo[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const maxParallelism = availableGpus.length || null;
  const parallelismExceedsGpus = maxParallelism !== null && tensorParallelSize > maxParallelism;

  useEffect(() => {
    if (isOpen) {
      setDeploymentId(sanitizeDeploymentId(jobId));
      setMaxModelLen("");
      setGpuMemUtil(0.9);
      setDtype("auto");
      setGpuId("");
      setTensorParallelSize(1);
      setAvailableGpus([]);
      setShowAdvanced(false);
      listSystemGpus().then(setAvailableGpus).catch(() => setAvailableGpus([]));
    }
  }, [isOpen, jobId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deploymentId.trim()) {
      toast.error("Deployment ID is required");
      return;
    }

    const payload: CreateDeploymentRequest = {
      deployment_id: deploymentId.trim(),
      job_id: jobId,
      gpu_memory_utilization: gpuMemUtil !== "" ? Number(gpuMemUtil) : undefined,
      dtype,
      tensor_parallel_size: tensorParallelSize,
      max_model_len: maxModelLen !== "" ? Number(maxModelLen) : null,
      gpu_id: gpuId !== "" ? Number(gpuId) : null,
    };

    setSubmitting(true);
    try {
      await createDeployment(payload);
      toast.success("Deployment created");
      onDeployed();
      onOpenChange(false);
    } catch {
      toast.error("Failed to create deployment");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] p-0 overflow-hidden">
        <form onSubmit={handleSubmit} className="max-h-[90vh] overflow-y-auto overflow-x-hidden">
          <DialogHeader className="p-6">
            <DialogTitle className="text-xl">Deploy Model</DialogTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Launch a vLLM inference server for{" "}
              <span className="font-medium text-foreground">{jobDisplayName}</span>
            </p>
          </DialogHeader>

          <div className="px-6 pb-6 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="deployment-id">Deployment ID</Label>
              <Input
                id="deployment-id"
                value={deploymentId}
                onChange={(e) => setDeploymentId(e.target.value)}
                placeholder="my-deployment"
                className="rounded-lg font-mono text-sm"
                autoComplete="off"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="gpu-mem-util">GPU Memory Utilization</Label>
                <Input
                  id="gpu-mem-util"
                  type="number"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={gpuMemUtil}
                  onChange={(e) =>
                    setGpuMemUtil(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  placeholder="0.9"
                  className="rounded-lg"
                />
              </div>

              <div className="space-y-2">
                <Label>Data Type</Label>
                <Select value={dtype} onValueChange={setDtype}>
                  <SelectTrigger className="rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">auto</SelectItem>
                    <SelectItem value="float16">float16</SelectItem>
                    <SelectItem value="bfloat16">bfloat16</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="tensor-parallel-size">
                Tensor Parallel Size
                {maxParallelism !== null && (
                  <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                    ({maxParallelism} GPU{maxParallelism !== 1 ? "s" : ""} available)
                  </span>
                )}
              </Label>
              <Input
                id="tensor-parallel-size"
                type="number"
                min={1}
                max={maxParallelism ?? undefined}
                step={1}
                value={tensorParallelSize}
                onChange={(e) =>
                  setTensorParallelSize(Math.max(1, Number.parseInt(e.target.value) || 1))
                }
                className={parallelismExceedsGpus ? "rounded-lg border-destructive" : "rounded-lg"}
              />
              {parallelismExceedsGpus ? (
                <p className="text-xs text-destructive">
                  Exceeds the {maxParallelism} GPU{maxParallelism !== 1 ? "s" : ""} available on this system.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Number of GPUs to use. Set to 2+ for large models (e.g. Gemma 9B across 2 GPUs).
                </p>
              )}
            </div>

            <div className="flex items-center gap-2 border-t pt-4">
              <div className="flex-1" />
              <div className="flex items-center gap-2">
                <Label htmlFor="show-advanced-deploy">Advanced</Label>
                <Switch
                  id="show-advanced-deploy"
                  checked={showAdvanced}
                  onCheckedChange={setShowAdvanced}
                />
              </div>
            </div>

            {showAdvanced && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max-model-len">Max Model Length</Label>
                  <Input
                    id="max-model-len"
                    type="number"
                    min={1}
                    value={maxModelLen}
                    onChange={(e) =>
                      setMaxModelLen(e.target.value === "" ? "" : Number(e.target.value))
                    }
                    placeholder="default"
                    className="rounded-lg"
                  />
                </div>
                <div className="space-y-2">
                  <Label>
                    {tensorParallelSize > 1 ? "Pin First GPU" : "GPU"}
                  </Label>
                  <Select
                    value={gpuId === "" ? "auto" : String(gpuId)}
                    onValueChange={(v) => setGpuId(v === "auto" ? "" : Number(v))}
                  >
                    <SelectTrigger className="rounded-lg">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto (by load)</SelectItem>
                      {availableGpus.map((gpu) => (
                        <SelectItem key={gpu.id} value={String(gpu.id)}>
                          GPU {gpu.id} · {gpu.name} ({gpu.free_memory_gb}GB free)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {tensorParallelSize > 1
                      ? `Pins the selected GPU first; ${tensorParallelSize - 1} more auto-selected by load.`
                      : "Auto lets the service pick the GPU with the lowest load."}
                  </p>
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="px-6 py-4 border-t flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || parallelismExceedsGpus}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Deploy
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}