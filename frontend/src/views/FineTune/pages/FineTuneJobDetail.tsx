import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { getFineTuneJob } from "@/services/openaiFineTune";
import { getUser } from "@/services/users";
import type { FineTuneJob } from "@/interfaces/fineTune.interface";
import { PageLayout } from "@/components/PageLayout";
import {
  formatStatusLabel,
  normalizePercent,
  normalizeNumber,
  getAccuracyFromMetrics,
  buildAccuracySeries,
  formatNumber,
  formatDate,
  inProgressStatuses,
} from "@/views/FineTune/utils/utils";
import { FineTuneAccuracyChart } from "@/views/FineTune/components/FineTuneAccuracyChart";
import { StatItem, DetailItem } from "@/views/FineTune/components/FineTuneStatItems";
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

  const createdByValue: string =
    createdByName ??
    (typeof job?.created_by === "string" ? job.created_by : "—");

  const accuracyData = useMemo(() => buildAccuracySeries(events), [events]);

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
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <h1 className="text-2xl font-semibold">{detailTitle}</h1>
            </div>
          </div>

          <Card className="p-5 space-y-5 bg-white">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
              <StatItem label="Model" value={job.model || "—"} />
              <StatItem
                label="Status"
                value={
                  <div className="flex items-center gap-2">
                    {isInProgress && <Loader2 className="h-4 w-4 text-primary animate-spin" />}
                    <span>{statusLabel}</span>
                  </div>
                }
              />
              <StatItem
                label="Accuracy"
                value={
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
                      <span>{`${accuracy} %`}</span>
                    </div>
                  )
                }
              />
              <StatItem
                label="# of trained tokens"
                value={
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
            </div>

            <div className="border-t border-border" />

            <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-4">
              <div className="grid gap-3">
                <DetailItem label="Created at" value={formatDate(job.created_at)} />
                <DetailItem label="Completed at" value={formatDate(job.finished_at)} />
                <DetailItem label="Created by" value={createdByValue} />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <DetailItem label="n_epochs" value={nEpochsValue} />
                  <DetailItem label="Batch size" value={batchSizeValue} />
                </div>
              </div>

              <FineTuneAccuracyChart data={accuracyData} />
            </div>
          </Card>
        </div>
      )}
    </PageLayout>
  );
}