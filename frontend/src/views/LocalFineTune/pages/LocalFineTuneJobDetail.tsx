import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { getLocalFineTuneJob } from "@/services/localFineTune";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";
import { PageLayout } from "@/components/PageLayout";
import { formatStatusLabel } from "@/views/FineTune/utils/utils";
import { formatDate, formatNumber } from "@/views/FineTune/utils/utils";
import { StatItem, DetailItem } from "@/views/FineTune/components/FineTuneStatItems";
import { inProgressStatuses } from "@/views/FineTune/utils/utils";

export default function LocalFineTuneJobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<LocalFineTuneJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchJob = async () => {
      try {
        setLoading(true);
        const data = await getLocalFineTuneJob(id);
        setJob(data ?? null);
        setError(data ? null : "Job not found");
      } catch {
        setError("Failed to load job");
        setJob(null);
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [id]);

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

  const detailTitle =
    job?.fine_tuned_model?.split("/").pop() ?? job?.model ?? job?.id ?? "Local Fine-Tune Job";

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
            <Button variant="outline" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate("/local-fine-tune")}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <h1 className="text-2xl font-semibold">{detailTitle}</h1>
            </div>
          </div>

          <Card className="rounded-lg border text-card-foreground w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
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
              <StatItem label="Created at" value={formatDate(job.created_at)} />
              <StatItem label="Finished at" value={formatDate(job.finished_at)} />
            </div>

            <div className="border-t border-border mt-4 pt-4" />

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <DetailItem label="Job ID" value={job.id} />
              <DetailItem label="Training file" value={job.training_file ?? "—"} />
              <DetailItem
                label="Validation file"
                value={job.validation_file ?? "—"}
              />
              {job.fine_tuned_model && (
                <div className="sm:col-span-2 lg:col-span-3">
                  <DetailItem label="Fine-tuned model path" value={job.fine_tuned_model} />
                </div>
              )}
              {job.error?.message && (
                <div className="sm:col-span-2 lg:col-span-3">
                  <DetailItem label="Error" value={job.error.message} />
                </div>
              )}
            </div>
          </Card>

          {hyperEntries.length > 0 && (
            <Card className="rounded-lg border text-card-foreground w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
              <h2 className="text-lg font-semibold mb-4">Hyperparameters</h2>
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
            </Card>
          )}
        </div>
      )}
    </PageLayout>
  );
}
