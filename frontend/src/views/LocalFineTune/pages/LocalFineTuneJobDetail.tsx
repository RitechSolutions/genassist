import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Info,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import { ScrollArea } from "@/components/scroll-area";
import {
  getLocalFineTuneJob,
  listLocalFineTuneJobEvents,
} from "@/services/localFineTune";
import type {
  LocalFineTuneJob,
  LocalFineTuneJobEvent,
} from "@/interfaces/localFineTune.interface";
import { PageLayout } from "@/components/PageLayout";
import {
  formatStatusLabel,
  formatDate,
  formatNumber,
  inProgressStatuses,
} from "@/views/FineTune/utils/utils";
import { DetailItem } from "@/views/FineTune/components/FineTuneStatItems";
import { JobSummaryStatsCard } from "@/views/FineTune/components/JobSummaryStatsCard";
import { JobProfileCard } from "@/views/FineTune/components/JobProfileCard";
import { AccuracyOverStepsChart } from "@/views/FineTune/components/AccuracyOverStepsChart";
import {
  buildLossSeriesFromEvents,
  parseFinalTrainLoss,
  parseTrainSampleCount,
} from "@/views/LocalFineTune/utils/trainingEvents";
import { getLocalFineTuneJobDisplayName } from "@/views/LocalFineTune/utils/jobDisplayName";

function formatLearningRate(value: unknown): string {
  if (value === undefined || value === null) return "—";
  const n = Number(value);
  if (!isFinite(n)) return "—";
  if (n === 0) return "0";
  if (Math.abs(n) < 0.001) return n.toExponential(2);
  return String(n);
}

function levelBadgeVariant(
  level: string
): "default" | "secondary" | "destructive" | "outline" {
  const l = level.toLowerCase();
  if (l === "error" || l === "critical") return "destructive";
  if (l === "warn" || l === "warning") return "secondary";
  return "outline";
}

export default function LocalFineTuneJobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<LocalFineTuneJob | null>(null);
  const [events, setEvents] = useState<LocalFineTuneJobEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        const [jobData, eventList] = await Promise.all([
          getLocalFineTuneJob(id),
          listLocalFineTuneJobEvents(id),
        ]);
        if (cancelled) return;
        setJob(jobData ?? null);
        setEvents(eventList);
        setError(jobData ? null : "Job not found");
      } catch {
        if (!cancelled) {
          setError("Failed to load job");
          setJob(null);
          setEvents([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const lossSeries = useMemo(() => buildLossSeriesFromEvents(events), [events]);
  const trainSamples = useMemo(() => parseTrainSampleCount(events), [events]);
  const finalLoss = useMemo(() => parseFinalTrainLoss(events), [events]);

  const normalizedStatus = String(job?.status ?? "").toLowerCase();
  const isInProgress = inProgressStatuses.has(normalizedStatus);
  const statusLabel =
    normalizedStatus === "succeeded"
      ? "Completed"
      : formatStatusLabel(normalizedStatus);

  const hyper = (job?.hyperparameters ?? {}) as Record<string, unknown>;
  const hyperEntries = Object.entries(hyper).filter(
    ([_, v]) => v !== undefined && v !== null && v !== ""
  );

  const detailTitle = job ? getLocalFineTuneJobDisplayName(job) : "Local Fine-Tune Job";

  const summaryItems = job
    ? [
        {
          label: "Model",
          value: (
            <span className="break-all text-base sm:text-lg">{job.model || "—"}</span>
          ),
        },
        {
          label: "Status",
          value: (
            <div className="flex items-center gap-2">
              {isInProgress && (
                <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
              )}
              <span>{statusLabel}</span>
            </div>
          ),
        },
        {
          label: "Learning rate",
          value: formatLearningRate(hyper.learning_rate),
        },
        {
          label: "Train samples",
          value:
            trainSamples != null ? (
              formatNumber(trainSamples)
            ) : (
              <span className="text-muted-foreground">—</span>
            ),
        },
      ]
    : [];

  return (
    <PageLayout>
      {loading ? (
        <div className="p-6 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : error || !job ? (
        <div className="p-6 flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground">{error || "Job not found"}</p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate(-1)}>
              Go back
            </Button>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0"
                onClick={() => navigate("/local-fine-tune")}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <div className="min-w-0">
                <h1 className="text-2xl sm:text-3xl font-bold mb-1 animate-fade-down truncate">
                  {detailTitle}
                </h1>
                <p className="text-sm text-muted-foreground animate-fade-up">
                  Local training run · job{" "}
                  <span className="font-mono text-xs">{job.id}</span>
                </p>
              </div>
            </div>
          </header>

          {normalizedStatus === "failed" && job.error?.message && (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div className="space-y-0.5 min-w-0">
                <p className="font-medium break-words">{job.error.message}</p>
                {job.error.code && (
                  <p className="text-xs text-destructive/70 font-mono">{job.error.code}</p>
                )}
              </div>
            </div>
          )}

          <JobSummaryStatsCard loading={false} items={summaryItems} />

          <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-4">
            <JobProfileCard
              pairRows={[
                {
                  label: "Epochs",
                  value:
                    hyper.num_train_epochs != null
                      ? formatNumber(hyper.num_train_epochs)
                      : "—",
                },
                {
                  label: "Batch size",
                  value:
                    hyper.per_device_train_batch_size != null
                      ? formatNumber(hyper.per_device_train_batch_size)
                      : "—",
                },
              ]}
              rows={[
                {
                  label: "Job name (suffix)",
                  value: job.suffix?.trim() || (
                    <span className="text-muted-foreground">—</span>
                  ),
                },
                { label: "Created at", value: formatDate(job.created_at) },
                { label: "Finished at", value: formatDate(job.finished_at) },
                {
                  label: "Final train loss",
                  value:
                    finalLoss != null ? (
                      <span className="font-mono text-sm">{finalLoss.toFixed(4)}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    ),
                },
                {
                  label: "Training file ID",
                  value: (
                    <span className="font-mono text-xs break-all">
                      {job.training_file ?? "—"}
                    </span>
                  ),
                },
                {
                  label: "Validation file ID",
                  value: (
                    <span className="font-mono text-xs break-all">
                      {job.validation_file ?? "—"}
                    </span>
                  ),
                },
                ...(job.fine_tuned_model
                  ? [
                      {
                        label: "Fine-tuned model path",
                        value: (
                          <span className="font-mono text-xs break-all">
                            {job.fine_tuned_model}
                          </span>
                        ),
                      } as const,
                    ]
                  : []),
              ]}
            />
            <AccuracyOverStepsChart
              data={lossSeries}
              loading={false}
              title="Training loss (logged steps)"
              valueLabel="Loss"
              valueMode="number"
            />
          </div>

          <Card className="rounded-lg border bg-white shadow-sm overflow-hidden animate-fade-up">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-zinc-700">
                Job events
              </CardTitle>
              <p className="text-xs text-muted-foreground font-normal">
                Live log from the local trainer ({events.length}{" "}
                {events.length === 1 ? "entry" : "entries"})
              </p>
            </CardHeader>
            <CardContent className="pt-0">
              {events.length === 0 ? (
                <div className="flex items-start gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-4 py-4 text-sm text-muted-foreground">
                  <Info className="h-4 w-4 shrink-0 mt-0.5" />
                  <p>
                    No event stream returned for this job. If your API exposes{" "}
                    <code className="text-xs bg-muted px-1 rounded">
                      GET …/fine-tuning/jobs/{`{id}`}/events
                    </code>
                    , events will appear here automatically.
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[min(420px,50vh)] pr-3">
                  <ul className="space-y-3 pr-2 pb-2">
                    {events.map((ev, i) => (
                      <li
                        key={`${ev.timestamp}-${i}`}
                        className="rounded-lg border border-border bg-zinc-50/80 px-3 py-2.5 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2 gap-y-1 mb-1">
                          <Badge
                            variant={levelBadgeVariant(ev.level)}
                            className="text-[10px] uppercase tracking-wide"
                          >
                            {ev.level}
                          </Badge>
                          <time
                            className="text-xs text-muted-foreground tabular-nums"
                            dateTime={ev.timestamp}
                          >
                            {formatDate(ev.timestamp)}
                          </time>
                        </div>
                        <p className="text-foreground leading-snug">{ev.message}</p>
                        {ev.data && Object.keys(ev.data).length > 0 ? (
                          <pre className="mt-2 max-h-36 overflow-auto rounded-md bg-white border border-border p-2 text-[11px] leading-relaxed font-mono text-zinc-700">
                            {JSON.stringify(ev.data, null, 2)}
                          </pre>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          {hyperEntries.length > 0 && (
            <Card className="rounded-lg border text-card-foreground w-full shadow-sm bg-white animate-fade-up">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-zinc-700">
                  Hyperparameters
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {hyperEntries.map(([key]) => (
                    <DetailItem
                      key={key}
                      label={key.replace(/_/g, " ")}
                      value={
                        typeof hyper[key] === "number"
                          ? formatNumber(hyper[key])
                          : String(hyper[key] ?? "—")
                      }
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </PageLayout>
  );
}
