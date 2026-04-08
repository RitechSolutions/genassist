import { format } from "date-fns";
import { Card } from "@/components/card";
import { Tooltip } from "@/components/tooltip";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { AgentStatsSummaryResponse } from "@/interfaces/analyticsReports.interface";
import type { DateRange } from "react-day-picker";

interface SummaryStatsCardsProps {
  summary: AgentStatsSummaryResponse | null;
  previousSummary?: AgentStatsSummaryResponse | null;
  compareDateRange?: DateRange;
  loading: boolean;
  error: string | null;
  containmentRate?: number | null;
}

interface StatMetric {
  label: string;
  value: string;
  sub?: string;
  description?: string;
  color?: string;
  delta?: number | null;
}

function DeltaBadge({ delta }: { delta: number | undefined | null }) {
  if (delta === undefined || delta === null || delta === 0) return null;
  const isPositive = delta > 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-emerald-600" : "text-rose-500";
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${color}`}>
      <Icon className="w-3 h-3" />
      {isPositive ? "+" : ""}{delta.toFixed(1)}%
    </span>
  );
}

/** Percentage change: ((current - previous) / previous) * 100 */
function pctChange(current: number, previous: number): number | null {
  if (previous === 0) return current > 0 ? 100 : null;
  return Math.round(((current - previous) / previous) * 100 * 10) / 10;
}

/** Percentage-point difference */
function ppDiff(currentRate: number, previousRate: number): number | null {
  const diff = Math.round((currentRate - previousRate) * 10) / 10;
  return diff === 0 ? null : diff;
}

function getComparisonLabel(compareDateRange?: DateRange): string | null {
  if (!compareDateRange?.from || !compareDateRange?.to) return null;
  return `vs ${format(compareDateRange.from, "MMM d")} – ${format(compareDateRange.to, "MMM d")}`;
}

function getResponseTimeColor(ms: number): string {
  if (ms < 3000) return "text-emerald-600";
  if (ms < 10000) return "text-amber-600";
  return "text-rose-600";
}

function buildMetrics(
  summary: AgentStatsSummaryResponse,
  containmentRate?: number | null,
  previous?: AgentStatsSummaryResponse | null,
): StatMetric[] {
  const successRate =
    summary.total_executions > 0
      ? ((summary.total_success / summary.total_executions) * 100).toFixed(1)
      : "0.0";
  const prevSuccessRate =
    previous && previous.total_executions > 0
      ? (previous.total_success / previous.total_executions) * 100
      : null;

  const totalFeedback = summary.total_thumbs_up + summary.total_thumbs_down;
  const satisfactionRate =
    totalFeedback > 0
      ? ((summary.total_thumbs_up / totalFeedback) * 100).toFixed(0)
      : null;
  const prevTotalFeedback = previous
    ? previous.total_thumbs_up + previous.total_thumbs_down
    : 0;
  const prevSatisfactionRate =
    previous && prevTotalFeedback > 0
      ? (previous.total_thumbs_up / prevTotalFeedback) * 100
      : null;

  const responseMs = summary.avg_response_ms;

  const metrics: StatMetric[] = [
    {
      label: "Conversations",
      value: summary.total_unique_conversations.toLocaleString(),
      sub:
        summary.total_finalized_conversations + summary.total_in_progress_conversations > 0
          ? `${summary.total_finalized_conversations} completed · ${summary.total_in_progress_conversations} in progress`
          : undefined,
      description: "Unique chat sessions in the selected period.",
      delta: previous
        ? pctChange(summary.total_unique_conversations, previous.total_unique_conversations)
        : null,
    },
    {
      label: "Success Rate",
      value: `${successRate}%`,
      sub: `${summary.total_success.toLocaleString()} of ${summary.total_executions.toLocaleString()} executions`,
      description: "Percentage of workflow executions that completed without errors.",
      delta: prevSuccessRate != null ? ppDiff(parseFloat(successRate), prevSuccessRate) : null,
    },
    {
      label: "Avg Response Time",
      value: responseMs != null ? (responseMs < 1000 ? `${Math.round(responseMs)} ms` : `${(responseMs / 1000).toFixed(1)}s`) : "—",
      description: "Average time from request to response. Green < 3s, amber 3-10s, red > 10s.",
      color: responseMs != null ? getResponseTimeColor(responseMs) : undefined,
      delta:
        responseMs != null && previous?.avg_response_ms != null
          ? (() => {
              const d = pctChange(responseMs, previous.avg_response_ms!);
              return d != null ? -d : null; // invert: faster = positive
            })()
          : null,
    },
  ];

  if (containmentRate != null) {
    metrics.push({
      label: "Containment Rate",
      value: `${(containmentRate * 100).toFixed(1)}%`,
      description: "Conversations resolved by the agent without escalation.",
    });
  }

  metrics.push({
    label: "Satisfaction",
    value: satisfactionRate != null ? `${satisfactionRate}%` : "—",
    sub:
      totalFeedback > 0
        ? `${summary.total_thumbs_up} positive · ${summary.total_thumbs_down} negative`
        : "No feedback yet",
    description: "Percentage of positive feedback out of all user ratings.",
    delta:
      satisfactionRate != null && prevSatisfactionRate != null
        ? ppDiff(parseFloat(satisfactionRate), prevSatisfactionRate)
        : null,
  });

  return metrics;
}

const PLACEHOLDER_COUNT = 5;

export function SummaryStatsCards({ summary, previousSummary, compareDateRange, loading, error, containmentRate }: SummaryStatsCardsProps) {
  if (loading) {
    return (
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-6 lg:gap-8">
          {Array.from({ length: PLACEHOLDER_COUNT }).map((_, i) => (
            <div key={i} className="relative flex flex-col gap-3 py-2 sm:py-0">
              <div className="h-7 w-16 bg-zinc-100 rounded animate-pulse" />
              <div className="h-4 w-24 bg-zinc-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  if (error || !summary) return null;

  const metrics = buildMetrics(summary, containmentRate, previousSummary);
  const colClass =
    metrics.length === 5
      ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5"
      : "grid-cols-2 sm:grid-cols-2 lg:grid-cols-4";

  return (
    <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
      {previousSummary && getComparisonLabel(compareDateRange) && (
        <p className="text-xs text-muted-foreground/60 mb-4">
          {getComparisonLabel(compareDateRange)}
        </p>
      )}
      <div className={`grid ${colClass} gap-4 sm:gap-6 lg:gap-8`}>
        {metrics.map((metric, index) => (
          <div key={metric.label} className="relative">
            <div className="flex flex-col gap-1 py-2 sm:py-0">
              <div className="flex items-baseline gap-2">
                <span className={`text-xl sm:text-2xl font-bold leading-tight ${metric.color ?? "text-foreground"}`}>
                  {metric.value}
                </span>
                <DeltaBadge delta={metric.delta} />
              </div>
              <div className="flex items-center gap-1 text-sm font-medium text-muted-foreground">
                {metric.label}
                {metric.description && (
                  <Tooltip
                    content={<span className="whitespace-normal max-w-[200px] block">{metric.description}</span>}
                    iconClassName="w-3 h-3"
                    contentClassName="w-48 text-center"
                  />
                )}
              </div>
              {metric.sub && (
                <div className="text-xs text-muted-foreground/70 leading-tight">
                  {metric.sub}
                </div>
              )}
            </div>
            {index < metrics.length - 1 && (
              <>
                <div className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                <div className="lg:hidden border-b border-zinc-100 mt-3" />
              </>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
