import { useMemo } from "react";
import type { LucideIcon } from "lucide-react";
import { Activity, CheckCircle2, Layers, XCircle } from "lucide-react";
import { Card } from "@/components/card";
import { Tooltip } from "@/components/tooltip";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";
import { inProgressStatuses } from "@/views/FineTune/utils/utils";

interface LocalFineTuneListSummaryProps {
  jobs: LocalFineTuneJob[];
  loading: boolean;
}

interface SummaryMetric {
  title: string;
  value: string;
  valueClassName: string;
  sub?: string;
  icon: LucideIcon;
  iconColor: string;
  description: string;
}

const PLACEHOLDER_COUNT = 4;

export function LocalFineTuneListSummary({
  jobs,
  loading,
}: LocalFineTuneListSummaryProps) {
  const counts = useMemo(() => {
    let active = 0;
    let succeeded = 0;
    let failed = 0;
    for (const j of jobs) {
      const s = String(j.status ?? "").toLowerCase();
      if (s === "succeeded") succeeded += 1;
      else if (s === "failed") failed += 1;
      else if (inProgressStatuses.has(s)) active += 1;
    }
    return { total: jobs.length, active, succeeded, failed };
  }, [jobs]);

  const metrics: SummaryMetric[] = useMemo(
    () => [
      {
        title: "Total jobs",
        value: counts.total.toLocaleString(),
        valueClassName: "text-foreground",
        sub: "All local runs on this API",
        icon: Layers,
        iconColor: "#71717a",
        description: "Every fine-tuning job returned by the local trainer.",
      },
      {
        title: "In progress",
        value: counts.active.toLocaleString(),
        valueClassName:
          counts.active > 0 ? "text-blue-600" : "text-muted-foreground",
        sub: "Queued, running, or saving output",
        icon: Activity,
        iconColor: "#2563eb",
        description:
          "Jobs still running on the local worker (includes validating files, queue, training, and saving the model).",
      },
      {
        title: "Completed",
        value: counts.succeeded.toLocaleString(),
        valueClassName:
          counts.succeeded > 0 ? "text-emerald-600" : "text-muted-foreground",
        sub: "Successful runs",
        icon: CheckCircle2,
        iconColor: "#059669",
        description: "Jobs that finished with status succeeded.",
      },
      {
        title: "Failed",
        value: counts.failed.toLocaleString(),
        valueClassName:
          counts.failed > 0 ? "text-rose-600" : "text-muted-foreground",
        sub: "Needs attention",
        icon: XCircle,
        iconColor: "#e11d48",
        description:
          "Jobs that failed during training or setup. Open a job for the error message.",
      },
    ],
    [counts]
  );

  if (loading) {
    return (
      <Card className="rounded-lg border text-card-foreground w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
        <div className="h-3 w-48 bg-zinc-100 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
          {Array.from({ length: PLACEHOLDER_COUNT }).map((_, i) => (
            <div key={i} className="flex flex-col gap-3 py-2 sm:py-0">
              <div className="h-7 w-16 bg-zinc-100 rounded animate-pulse" />
              <div className="h-4 w-24 bg-zinc-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  const total = counts.total;

  return (
    <Card className="rounded-lg border text-card-foreground w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
      <p className="text-xs text-muted-foreground mb-4">
        {total > 0 ? (
          <>
            Based on {total.toLocaleString()} local fine-tuning job
            {total !== 1 ? "s" : ""}
          </>
        ) : (
          <>No jobs yet — stats will appear after your first run</>
        )}
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
        {metrics.map((metric, index) => {
          const Icon = metric.icon;
          const isLast = index === metrics.length - 1;
          return (
            <div key={metric.title} className="relative">
              <div className="flex flex-col gap-1 py-2 sm:py-0">
                <div className="flex items-baseline gap-2">
                  <span
                    className={`text-xl sm:text-2xl font-bold leading-tight tabular-nums ${metric.valueClassName}`}
                  >
                    {metric.value}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-sm font-medium text-muted-foreground min-w-0">
                  <Icon
                    className="w-3.5 h-3.5 flex-shrink-0"
                    style={{ color: metric.iconColor }}
                  />
                  <span className="truncate">{metric.title}</span>
                  <Tooltip
                    content={
                      <span className="whitespace-normal max-w-[220px] block">
                        {metric.description}
                      </span>
                    }
                    iconClassName="w-3 h-3"
                    contentClassName="w-52 text-center"
                  />
                </div>
                {metric.sub && (
                  <div className="text-xs text-muted-foreground/70 leading-tight">
                    {metric.sub}
                  </div>
                )}
              </div>
              {!isLast && (
                <>
                  <div className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                  <div className="lg:hidden border-b border-zinc-100 mt-3" />
                </>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
