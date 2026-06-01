import { Card } from "@/components/card";
import { cn } from "@/helpers/utils";
import { analyticsFadeUpClass } from "../../constants/animations";
import { AnalyticsMetricsCardsSkeleton } from "../skeletons";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "../AnalyticsKpiStat";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { AgentStatsSummaryResponse } from "@/interfaces/analyticsReports.interface";
import type { DateRange } from "react-day-picker";

interface SummaryStatsCardsProps {
  summary: AgentStatsSummaryResponse | null;
  previousSummary?: AgentStatsSummaryResponse | null;
  comparedWithLabel?: string | null;
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

export function SummaryStatsCards({ summary, previousSummary, comparedWithLabel, loading, error, containmentRate }: SummaryStatsCardsProps) {
  if (loading) {
    return <AnalyticsMetricsCardsSkeleton count={5} />;
  }

  if (error || !summary) return null;

  const metrics = buildMetrics(summary, containmentRate, previousSummary);

  return (
    <Card className={cn("w-full bg-white px-4 py-4 shadow-sm sm:px-6 sm:py-6", analyticsFadeUpClass)}>
      {previousSummary && comparedWithLabel && (
        <p className="text-xs text-muted-foreground/60 mb-4">{comparedWithLabel}</p>
      )}
      <div className={analyticsKpiGridClass(metrics.length)}>
        {metrics.map((metric) => (
          <AnalyticsKpiStat
            key={metric.label}
            label={metric.label}
            value={metric.value}
            sub={metric.sub}
            description={metric.description}
            valueClassName={metric.color ?? "text-foreground"}
            delta={<DeltaBadge delta={metric.delta} />}
          />
        ))}
      </div>
    </Card>
  );
}
