import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, ArrowLeft, Check, Copy, Download, Info, Loader2 } from "lucide-react";
import { Button } from "@/components/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { downloadOpenAIFile, getFineTuneJob } from "@/services/openaiFineTune";
import { getUser } from "@/services/users";
import type { FineTuneJob } from "@/interfaces/fineTune.interface";
import { PageLayout } from "@/components/PageLayout";
import {
  formatStatusLabel,
  normalizePercent,
  normalizeNumber,
  getAccuracyFromMetrics,
  getAccuracyColor,
  buildAccuracySeries,
  formatNumber,
  formatDate,
  inProgressStatuses,
} from "@/views/FineTune/utils/utils";
import { AccuracyOverStepsChart } from "@/views/FineTune/components/AccuracyOverStepsChart";
import { JobSummaryStatsCard } from "@/views/FineTune/components/JobSummaryStatsCard";
import { JobProfileCard } from "@/views/FineTune/components/JobProfileCard";
import type { JobProgress, UsageMetrics } from "@/views/FineTune/types";

export default function FineTuneJobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<FineTuneJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createdByName, setCreatedByName] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchJob = async () => {
      try {
        setLoading(true);
        const data = await getFineTuneJob(id, true);
        setJob(data);
        setError(null);
      } catch (err) {
        setError("Failed to load job");
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [id]);

  const progress = (job as Record<string, unknown> | null)?.progress as JobProgress | undefined;
  const normalizedStatus = String(job?.status || progress?.status || "").toLowerCase();
  const isInProgress =
    !["succeeded", "failed", "cancelled"].includes(normalizedStatus) &&
    (inProgressStatuses.has(normalizedStatus) || progress?.is_running);
  const percent =
    normalizePercent((job as Record<string, unknown> | null)?.progress_percentage) ??
    normalizePercent(progress?.progress_percentage);
  const usageMetrics = (job as Record<string, unknown> | null)?.usage_metrics as UsageMetrics | undefined;
  const interactions =
    normalizeNumber((job as Record<string, unknown> | null)?.trained_tokens) ??
    normalizeNumber(usageMetrics?.total_interactions) ??
    normalizeNumber(usageMetrics?.total_tokens) ??
    null;
  const events = (job as Record<string, unknown> | null)?.events as
    | Array<{ metrics?: Record<string, unknown>; created_at?: string }>
    | undefined;

  const detailTitle = String(
    job?.user_provided_suffix ??
    job?.suffix ??
    job?.fine_tuned_model ??
    job?.id ??
    "Fine-Tune Job"
  );

  const statusLabel = (() => {
    if (["succeeded", "failed", "cancelled"].includes(normalizedStatus)) {
      if (normalizedStatus === "succeeded") return "Completed";
      return formatStatusLabel(normalizedStatus);
    }
    return percent !== null ? `${percent} %` : formatStatusLabel(normalizedStatus);
  })();

  const latestMetricsAccuracy = getAccuracyFromMetrics(progress?.latest_metrics, isInProgress);
  const accuracy =
    normalizePercent((job as Record<string, unknown> | null)?.accuracy) ??
    normalizePercent((job as Record<string, unknown> | null)?.validation_accuracy) ??
    normalizePercent((job as Record<string, unknown> | null)?.full_valid_mean_token_accuracy) ??
    normalizePercent(progress?.accuracy) ??
    latestMetricsAccuracy;

  const hyper = (job?.hyperparameters as { n_epochs?: unknown; batch_size?: unknown } | undefined) || {};
  const nEpochsValue: string | number = normalizeNumber(hyper.n_epochs) ?? "—";
  const batchSizeValue: string | number = normalizeNumber(hyper.batch_size) ?? "—";

  type FileInfo = { id: string; openai_file_id: string; filename: string; bytes: number };
  const trainingFileInfo = (job as Record<string, unknown> | null)?.training_file_info as FileInfo | undefined;
  const validationFileInfo = (job as Record<string, unknown> | null)?.validation_file_info as FileInfo | undefined;

  const createdByValue: string =
    createdByName ??
    (typeof job?.created_by === "string" ? job.created_by : "—");

  const stepData = useMemo(() => buildAccuracySeries(events), [events]);

  useEffect(() => {
    const creatorId = (job as Record<string, unknown> | null)?.created_by as string | undefined;
    if (!creatorId) {
      setCreatedByName(null);
      return;
    }
    let active = true;
    const fetchUser = async () => {
      try {
        const user = await getUser(creatorId);
        if (!active) return;
        if (user) {
          type UserNameFields = {
            first_name?: string;
            last_name?: string;
            firstName?: string;
            lastName?: string;
            email?: string;
            username?: string;
          };
          const names = user as unknown as UserNameFields;
          const first = names.first_name || names.firstName;
          const last = names.last_name || names.lastName;
          const full = [first, last].filter(Boolean).join(" ").trim();
          const display = full || names.username || names.email || creatorId;
          setCreatedByName(display);
        } else {
          setCreatedByName(creatorId);
        }
      } catch (_err) {
        if (active) setCreatedByName(creatorId);
      }
    };
    fetchUser();
    return () => {
      active = false;
    };
  }, [job]);

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
            {id && (
              <Button onClick={() => window.location.reload()}>
                Retry
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Header — match Agent Performance */}
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
                  Training run details and metrics
                </p>
              </div>
            </div>
          </header>

          {/* Failure reason banner */}
          {normalizedStatus === "failed" && (job.error_message as string | undefined) && (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div className="space-y-0.5">
                <p className="font-medium">{job.error_message as string}</p>
                {(job.error_code as string | undefined) && (
                  <p className="text-xs text-destructive/70">{job.error_code as string}</p>
                )}
              </div>
            </div>
          )}

          {/* Summary stats card — same style as Agent Performance SummaryStatsCards */}
          <JobSummaryStatsCard
            loading={loading}
            model={job.model || "—"}
            status={
              <div className="flex items-center gap-2">
                {isInProgress && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                <span>{statusLabel}</span>
              </div>
            }
            accuracy={
              accuracy === null ? (
                isInProgress ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 text-primary animate-spin" />
                    <span className="text-muted-foreground">Calculating...</span>
                  </div>
                ) : (
                  "—"
                )
              ) : (
                <div className="flex items-center gap-2">
                  {isInProgress && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                  <span className={getAccuracyColor(accuracy)}>{accuracy}%</span>
                </div>
              )
            }
            trainedTokens={
              interactions === null && isInProgress ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 text-primary animate-spin" />
                  <span className="text-muted-foreground">Calculating...</span>
                </div>
              ) : (
                formatNumber(interactions)
              )
            }
          />

          {/* Profile + Chart row — profile left, Accuracy over steps card right */}
          <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-4">
            <JobProfileCard
              rows={[
                { label: "Created at", value: formatDate(job.created_at) },
                { label: "Completed at", value: formatDate(job.finished_at) },
                { label: "Created by", value: createdByValue },
              ]}
              pairRows={[
                { label: "n_epochs", value: nEpochsValue },
                { label: "Batch size", value: batchSizeValue },
              ]}
            />
            <AccuracyOverStepsChart
              data={stepData}
              loading={loading}
              title="Accuracy over steps"
              valueLabel="Accuracy"
            />
          </div>

          {/* Training / Validation files */}
          {(trainingFileInfo || validationFileInfo) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { label: "Training file", info: trainingFileInfo },
                { label: "Validation file", info: validationFileInfo },
              ].map(({ label, info }) =>
                info ? (
                  <div
                    key={info.openai_file_id}
                    className="flex items-center justify-between rounded-lg border px-4 py-3 gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
                      <p className="text-sm font-medium truncate">{info.filename}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {(info.bytes / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <FileIdsPopover id={info.id} openaiFileId={info.openai_file_id} />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void downloadOpenAIFile(info.openai_file_id, info.filename)}
                      >
                        <Download className="h-3.5 w-3.5 mr-1.5" />
                        Download
                      </Button>
                    </div>
                  </div>
                ) : null
              )}
            </div>
          )}
        </div>
      )}
    </PageLayout>
  );
}

function FileIdsPopover({ id, openaiFileId }: { id: string; openaiFileId: string }) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copy = (value: string, key: string) => {
    void navigator.clipboard.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="text-muted-foreground hover:text-foreground transition-colors">
          <Info className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3 space-y-3" align="end">
        {[
          { label: "Local DB", value: id, key: "db" },
          { label: "OpenAI", value: openaiFileId, key: "openai" },
        ].map(({ label, value, key }) => (
          <div key={key}>
            <p className="text-xs text-muted-foreground mb-1">{label}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs bg-muted rounded px-2 py-1 truncate">{value}</code>
              <button
                onClick={() => copy(value, key)}
                className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
              >
                {copiedKey === key ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}