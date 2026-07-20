import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, ArrowLeft, Check, Copy, Info, Loader2, PowerOff, RefreshCw, Rocket } from "lucide-react";
import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { toast } from "react-hot-toast";
import {
  deployBedrockCustomModel,
  getBedrockFineTuneJob,
  undeployBedrockCustomModel,
} from "@/services/bedrockFineTune";
import type { BedrockFineTuneJob } from "@/interfaces/bedrockFineTune.interface";
import { PageLayout } from "@/components/PageLayout";
import { formatDate, formatNumber } from "@/views/FineTune/utils/utils";
import { JobSummaryStatsCard } from "@/views/FineTune/components/JobSummaryStatsCard";
import { JobProfileCard } from "@/views/FineTune/components/JobProfileCard";
import {
  bedrockActiveDeploymentStatuses,
  bedrockInProgressStatuses,
  formatBedrockStatusLabel,
} from "@/views/BedrockFineTune/utils/utils";

export default function BedrockFineTuneJobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<BedrockFineTuneJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [undeploying, setUndeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = async (showSpinner = true) => {
    if (!id) return;
    try {
      if (showSpinner) setLoading(true);
      const data = await getBedrockFineTuneJob(id, true);
      setJob(data);
      setError(null);
    } catch (err) {
      setError("Failed to load job");
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    void fetchJob(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetchJob(false);
      toast.success("Job synced");
    } catch {
      toast.error("Failed to sync job");
    } finally {
      setSyncing(false);
    }
  };

  const handleDeploy = async () => {
    if (!id) return;
    setDeploying(true);
    try {
      const updated = await deployBedrockCustomModel(id);
      if (updated) setJob(updated);
      toast.success("Deployment started");
    } catch {
      toast.error("Failed to deploy model");
    } finally {
      setDeploying(false);
    }
  };

  const handleUndeploy = async () => {
    if (!id) return;
    setUndeploying(true);
    try {
      const updated = await undeployBedrockCustomModel(id);
      if (updated) setJob(updated);
      toast.success("Deployment removed");
    } catch {
      toast.error("Failed to undeploy model");
    } finally {
      setUndeploying(false);
    }
  };

  const normalizedStatus = String(job?.status || "").toLowerCase();
  const isInProgress = bedrockInProgressStatuses.has(normalizedStatus);
  const isCompleted = normalizedStatus === "completed";
  const isFailed = normalizedStatus === "failed";

  const deploymentStatus = String(job?.deployment_status || "NotDeployed");
  const normalizedDeployment = deploymentStatus.toLowerCase();
  const hasDeployment = bedrockActiveDeploymentStatuses.has(normalizedDeployment);
  const canDeploy = isCompleted && !hasDeployment;

  const detailTitle = String(
    job?.suffix ??
    job?.custom_model_name ??
    job?.id ??
    "Bedrock Fine-Tune Job"
  );

  const statusLabel = formatBedrockStatusLabel(String(job?.status || ""));

  const hyper = (job?.hyperparameters as Record<string, unknown> | null | undefined) || {};
  const hyperEntries = Object.entries(hyper);

  return (
    <PageLayout>
      {loading ? (
        <div className="p-6 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : error || !job ? (
        <div className="p-6 flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground">{error || "Job not found"}</p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate(-1)}>
              Go back
            </Button>
            {id && <Button onClick={() => window.location.reload()}>Retry</Button>}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Header */}
          <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold mb-1 animate-fade-down">
                  {detailTitle}
                </h1>
                <p className="text-sm text-muted-foreground animate-fade-up">
                  Amazon Nova fine-tuning run details
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleSync} disabled={syncing}>
                {syncing ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Sync
              </Button>
              {canDeploy && (
                <Button size="sm" onClick={handleDeploy} disabled={deploying}>
                  {deploying ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Rocket className="h-4 w-4 mr-2" />
                  )}
                  Deploy
                </Button>
              )}
            </div>
          </header>

          {/* Failure reason banner */}
          {isFailed && job.error_message && (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <p className="font-medium">{String(job.error_message)}</p>
            </div>
          )}

          {/* Summary stats card */}
          <JobSummaryStatsCard
            loading={loading}
            items={[
              { label: "Base model", value: job.base_model_id || "—" },
              {
                label: "Status",
                value: (
                  <div className="flex items-center gap-2">
                    {isInProgress && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                    <span>{statusLabel}</span>
                  </div>
                ),
              },
              {
                label: "Deployment",
                value:
                  normalizedDeployment === "creating" ? (
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 text-primary animate-spin" />
                      <span>Creating</span>
                    </div>
                  ) : (
                    formatBedrockStatusLabel(deploymentStatus)
                  ),
              },
              { label: "# of trained tokens", value: formatNumber(job.trained_tokens) },
            ]}
          />

          {/* Profile + hyperparameters row */}
          <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-4">
            <JobProfileCard
              rows={[
                { label: "Created at", value: formatDate(job.created_at) },
                { label: "Completed at", value: formatDate(job.finished_at) },
                { label: "Last synced at", value: formatDate(job.last_synced_at) },
                { label: "Region", value: job.region || "—" },
              ]}
            />

            <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up rounded-lg border text-card-foreground h-full">
              <p className="text-sm font-semibold mb-4">Deployment</p>
              {hasDeployment && job.deployment_arn ? (
                <div className="space-y-3">
                  <CopyableValue label="Deployment ARN" value={String(job.deployment_arn)} />
                  <div className="flex items-start gap-2 rounded-lg border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                    <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                    <p>
                      Paste this deployment ARN into the Model field of a Bedrock LLM provider to use
                      this fine-tuned model.
                    </p>
                  </div>
                  {normalizedDeployment === "active" && (
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleUndeploy}
                        disabled={undeploying}
                      >
                        {undeploying ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <PowerOff className="h-4 w-4 mr-2" />
                        )}
                        Undeploy
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        Removes the AWS deployment to stop ongoing charges.
                      </span>
                    </div>
                  )}
                </div>
              ) : canDeploy ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    This job is complete. Deploy an on-demand Nova serving endpoint to use the
                    fine-tuned model.
                  </p>
                  <Button size="sm" onClick={handleDeploy} disabled={deploying}>
                    {deploying ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Rocket className="h-4 w-4 mr-2" />
                    )}
                    Deploy
                  </Button>
                </div>
              ) : normalizedDeployment === "failed" ? (
                <div className="space-y-3">
                  <p className="text-sm text-destructive">Deployment failed. You can try again.</p>
                  {isCompleted && (
                    <Button size="sm" onClick={handleDeploy} disabled={deploying}>
                      {deploying ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Rocket className="h-4 w-4 mr-2" />
                      )}
                      Retry deploy
                    </Button>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Deployment becomes available once the job is completed.
                </p>
              )}

              {hyperEntries.length > 0 && (
                <div className="mt-6 pt-4 border-t border-zinc-200">
                  <p className="text-sm font-semibold mb-3">Hyperparameters</p>
                  <div className="grid grid-cols-2 gap-3">
                    {hyperEntries.map(([key, value]) => (
                      <div key={key} className="flex flex-col gap-1">
                        <span className="text-xs text-muted-foreground">{key}</span>
                        <span className="text-sm font-medium text-foreground">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>

          {/* Training / Validation S3 URIs */}
          {(job.training_data_s3_uri || job.validation_data_s3_uri) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {job.training_data_s3_uri && (
                <div className="rounded-lg border px-4 py-3">
                  <CopyableValue label="Training data" value={String(job.training_data_s3_uri)} />
                </div>
              )}
              {job.validation_data_s3_uri && (
                <div className="rounded-lg border px-4 py-3">
                  <CopyableValue label="Validation data" value={String(job.validation_data_s3_uri)} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </PageLayout>
  );
}

function CopyableValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 text-xs bg-muted rounded px-2 py-1 truncate">{value}</code>
        <button
          type="button"
          onClick={copy}
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          title="Copy"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}
