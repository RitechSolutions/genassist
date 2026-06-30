import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { Card } from "@/components/card";
import { AnalyticsMetricsCardsSkeleton } from "./skeletons";
import {
  SmileIcon,
  Award,
  CheckCircle,
  Zap,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  type LucideIcon,
} from "lucide-react";
import { format } from "date-fns";
import type { FetchedMetricsData, MetricsDeltas } from "@/services/metrics";
import type { DateRange } from "react-day-picker";
import { cn } from "@/helpers/utils";
import { analyticsFadeUpClass, analyticsRefreshingClassName } from "../constants/animations";
import { AnalyticsKpiStat, analyticsKpiGridClass } from "./AnalyticsKpiStat";

interface MetricItem {
  title: string;
  value: string;
  numericValue: number;
  icon: LucideIcon;
  color: string;
  description?: string;
  sub?: string;
  deltaKey?: string;
}

interface AnalyticsMetricsSectionProps {
  dateRange?: DateRange;
  agentId?: string;
  groupId?: string;
  metrics: FetchedMetricsData | null;
  deltas: MetricsDeltas | null;
  loading: boolean;
  refreshing?: boolean;
  error: Error | null;
  compareDateRange?: DateRange;
}

/** Return a Tailwind text color class based on score percentage. */
function getScoreColor(value: number, hasData: boolean): string {
  if (!hasData) return "text-zinc-900";
  if (value >= 70) return "text-emerald-600";
  if (value >= 40) return "text-amber-600";
  return "text-rose-600";
}

function parsePercent(str: string): number {
  const n = parseFloat(str);
  return isNaN(n) ? 0 : n;
}

function DeltaBadge({ delta }: { delta: number | undefined | null }) {
  if (delta === undefined || delta === null || delta === 0) return null;
  const isPositive = delta > 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-emerald-600" : "text-rose-500";
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${color}`}>
      <Icon className="w-3 h-3" />
      {isPositive ? "+" : ""}{delta}%
    </span>
  );
}

export const AnalyticsMetricsSection = ({
  dateRange,
  agentId,
  groupId,
  metrics,
  deltas,
  loading,
  refreshing,
  error,
  compareDateRange,
}: AnalyticsMetricsSectionProps) => {
  const defaultMetrics: FetchedMetricsData = {
    "Customer Satisfaction": "0%",
    "Resolution Rate": "0%",
    "Positive Sentiment": "0%",
    "Negative Sentiment": "0%",
    "Efficiency": "0%",
    "Response Time": "0%",
    "Quality of Service": "0%",
    "total_analyzed_audios": 0,
  };

  const d = metrics || defaultMetrics;
  const analyzedCount = d["total_analyzed_audios"];

  const positivePct = parsePercent(d["Positive Sentiment"]);
  const negativePct = parsePercent(d["Negative Sentiment"]);
  const neutralPct = Math.max(0, 100 - positivePct - negativePct);

  const metricCards: MetricItem[] = [
    {
      title: "Customer Satisfaction",
      value: d["Customer Satisfaction"],
      numericValue: parsePercent(d["Customer Satisfaction"]),
      icon: SmileIcon,
      description:
        "AI-evaluated score of how satisfied the customer appeared during the conversation.",
      color: "#10b981",
      deltaKey: "Customer Satisfaction",
    },
    {
      title: "Quality of Service",
      value: d["Quality of Service"],
      numericValue: parsePercent(d["Quality of Service"]),
      icon: Award,
      description:
        "AI-evaluated score of overall service quality, including accuracy, tone, and completeness.",
      color: "#8b5cf6",
      deltaKey: "Quality of Service",
    },
    {
      title: "Resolution Rate",
      value: d["Resolution Rate"],
      numericValue: parsePercent(d["Resolution Rate"]),
      icon: CheckCircle,
      description:
        "AI-evaluated score of how well customer issues were resolved.",
      color: "#f59e0b",
      deltaKey: "Resolution Rate",
    },
    {
      title: "Efficiency",
      value: d["Efficiency"],
      numericValue: parsePercent(d["Efficiency"]),
      icon: Zap,
      description:
        "AI-evaluated score of how efficiently the agent handled the conversation.",
      color: "#06b6d4",
      deltaKey: "Efficiency",
    },
    {
      title: "Sentiment",
      value: analyzedCount > 0 ? `${positivePct.toFixed(0)}%` : "No feedback yet",
      numericValue: positivePct,
      icon: MessageSquare,
      description:
        "Overall sentiment distribution detected across analyzed conversations.",
      color: "#22c55e",
      sub:
        analyzedCount > 0
          ? `Positive · ${negativePct.toFixed(0)}% negative · ${neutralPct.toFixed(0)}% neutral`
          : undefined,
      deltaKey: "Positive Sentiment",
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <AnalyticsMetricsCardsSkeleton showContextLine />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-red-500">
        Error loading analytics data
      </div>
    );
  }

  return (
    <div className={cn("space-y-6 sm:space-y-8", analyticsRefreshingClassName(refreshing))}>
      <Card className={cn("mb-0 w-full bg-white px-4 py-4 shadow-sm sm:px-6 sm:py-6", analyticsFadeUpClass)}>
        {/* Context line */}
        {(analyzedCount > 0 || deltas) && (
          <p className="text-xs text-muted-foreground mb-4">
            {analyzedCount > 0 && (
              <>Based on {analyzedCount.toLocaleString()} analyzed conversation{analyzedCount !== 1 ? "s" : ""}</>
            )}
            {deltas && compareDateRange?.from && compareDateRange?.to && (
              <span className="text-muted-foreground/60">
                {analyzedCount > 0 ? " · " : ""}
                vs {format(compareDateRange.from, "MMM d")} – {format(compareDateRange.to, "MMM d")}
              </span>
            )}
          </p>
        )}

        <div className={analyticsKpiGridClass(metricCards.length)}>
          {metricCards.map((metric) => {
            const Icon = metric.icon;
            const delta = metric.deltaKey && deltas ? deltas[metric.deltaKey] : undefined;
            return (
              <AnalyticsKpiStat
                key={metric.title}
                label={metric.title}
                value={metric.value}
                sub={metric.sub}
                description={metric.description}
                valueClassName={getScoreColor(metric.numericValue, analyzedCount > 0)}
                icon={Icon}
                iconColor={metric.color}
                delta={<DeltaBadge delta={delta} />}
              />
            );
          })}
        </div>
      </Card>

      <PerformanceChart dateRange={dateRange} agentId={agentId} groupId={groupId} />
    </div>
  );
};
