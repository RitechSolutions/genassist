import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { Card } from "@/components/card";
import { Tooltip } from "@/components/tooltip";
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

const PLACEHOLDER_COUNT = 5;

export const AnalyticsMetricsSection = ({
  dateRange,
  agentId,
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
      value: analyzedCount > 0 ? `${positivePct.toFixed(0)}% positive` : "No feedback yet",
      numericValue: positivePct,
      icon: MessageSquare,
      description:
        "Overall sentiment distribution detected across analyzed conversations.",
      color: "#22c55e",
      sub: analyzedCount > 0 ? `${negativePct.toFixed(0)}% negative · ${neutralPct.toFixed(0)}% neutral` : undefined,
      deltaKey: "Positive Sentiment",
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-6 lg:gap-8">
            {Array.from({ length: PLACEHOLDER_COUNT }).map((_, i) => (
              <div key={i} className="flex flex-col gap-3 py-2 sm:py-0">
                <div className="h-7 w-16 bg-zinc-100 rounded animate-pulse" />
                <div className="h-4 w-20 bg-zinc-100 rounded animate-pulse" />
              </div>
            ))}
          </div>
        </Card>
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
    <div
      className={
        refreshing
          ? "opacity-70 transition-opacity duration-200"
          : "transition-opacity duration-200"
      }
    >
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up mb-6 sm:mb-8">
        {/* Context line */}
        {(analyzedCount > 0 || deltas) && (
          <p className="text-xs text-muted-foreground mb-4">
            {analyzedCount > 0 && (
              <>Based on {analyzedCount.toLocaleString()} analyzed conversation{analyzedCount !== 1 ? "s" : ""}</>
            )}
            {deltas && compareDateRange?.from && compareDateRange?.to && (
              <span className="text-muted-foreground/60">
                {analyzedCount > 0 ? " · " : ""}vs {format(compareDateRange.from, "MMM d")} – {format(compareDateRange.to, "MMM d")}
              </span>
            )}
          </p>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 sm:gap-6 lg:gap-8">
          {metricCards.map((metric, index) => {
            const Icon = metric.icon;
            const isLast = index === metricCards.length - 1;
            const delta = metric.deltaKey && deltas ? deltas[metric.deltaKey] : undefined;
            return (
              <div key={metric.title} className="relative">
                <div className="flex flex-col gap-1 py-2 sm:py-0">
                  <div className="flex items-baseline gap-2">
                    <span
                      className={`text-xl sm:text-2xl font-bold leading-tight ${getScoreColor(metric.numericValue, analyzedCount > 0)}`}
                    >
                      {metric.value}
                    </span>
                    <DeltaBadge delta={delta} />
                  </div>
                  <div className="flex items-center gap-1 text-sm font-medium text-muted-foreground">
                    <Icon
                      className="w-3.5 h-3.5 flex-shrink-0"
                      style={{ color: metric.color }}
                    />
                    <span className="truncate">{metric.title}</span>
                    {metric.description && (
                      <Tooltip
                        content={
                          <span className="whitespace-normal max-w-[200px] block">
                            {metric.description}
                          </span>
                        }
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

      <PerformanceChart dateRange={dateRange} agentId={agentId} />
    </div>
  );
};
