import { PerformanceChart } from "@/components/analytics/PerformanceChart";
import { Card } from "@/components/card";
import { Tooltip } from "@/components/tooltip";
import {
  Timer,
  SmileIcon,
  Award,
  CheckCircle,
  Zap,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import type { FetchedMetricsData } from "@/services/metrics";
import type { DateRange } from "react-day-picker";

interface MetricItem {
  title: string;
  value: string;
  icon: LucideIcon;
  color: string;
  description?: string;
}

interface AnalyticsMetricsSectionProps {
  dateRange?: DateRange;
  agentId?: string;
  metrics: FetchedMetricsData | null;
  loading: boolean;
  refreshing?: boolean;
  error: Error | null;
}

const PLACEHOLDER_COUNT = 8;

export const AnalyticsMetricsSection = ({ dateRange, agentId, metrics, loading, refreshing, error }: AnalyticsMetricsSectionProps) => {
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

  const formattedData = metrics || defaultMetrics;

  const metricCards: MetricItem[] = [
    {
      title: "Responsiveness",
      value: formattedData["Response Time"],
      icon: Timer,
      description: "AI-evaluated score of how promptly the operator responded during takeover conversations. Higher is better.",
      color: "#3b82f6",
    },
    {
      title: "Customer Satisfaction",
      value: formattedData["Customer Satisfaction"],
      icon: SmileIcon,
      description: "AI-evaluated score of how satisfied the customer appeared during the conversation.",
      color: "#10b981",
    },
    {
      title: "Quality of Service",
      value: formattedData["Quality of Service"],
      icon: Award,
      description: "AI-evaluated score of overall service quality, including accuracy, tone, and completeness.",
      color: "#8b5cf6",
    },
    {
      title: "Resolution Rate",
      value: formattedData["Resolution Rate"],
      icon: CheckCircle,
      description: "AI-evaluated score of how well customer issues were resolved, based on conversation analysis.",
      color: "#f59e0b",
    },
    {
      title: "Efficiency",
      value: formattedData["Efficiency"],
      icon: Zap,
      description: "AI-evaluated score of how efficiently the agent handled the conversation.",
      color: "#06b6d4",
    },
    {
      title: "Positive Sentiment",
      value: formattedData["Positive Sentiment"],
      icon: ThumbsUp,
      description: "Average positive sentiment detected across analyzed conversations.",
      color: "#22c55e",
    },
    {
      title: "Negative Sentiment",
      value: formattedData["Negative Sentiment"],
      icon: ThumbsDown,
      description: "Average negative sentiment detected across analyzed conversations.",
      color: "#ef4444",
    },
    {
      title: "Analyzed",
      value: formattedData["total_analyzed_audios"].toLocaleString(),
      icon: MessageSquare,
      description: "Total number of conversations analyzed in the selected period.",
      color: "#6b7280",
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
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
    return <div className="text-center py-8 text-red-500">Error loading analytics data</div>;
  }

  return (
    <div className={refreshing ? "opacity-70 transition-opacity duration-200" : "transition-opacity duration-200"}>
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up mb-6 sm:mb-8">
        {[metricCards.slice(0, 4), metricCards.slice(4)].map((row, rowIndex) => (
          <div key={rowIndex}>
            {rowIndex > 0 && <div className="border-t border-zinc-200 my-4 sm:my-5" />}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
              {row.map((metric, index) => {
                const Icon = metric.icon;
                const isLastInRow = index === row.length - 1;
                return (
                  <div key={metric.title} className="relative">
                    <div className="flex flex-col gap-1 py-2 sm:py-0">
                      <div className="text-xl sm:text-2xl font-bold text-foreground leading-tight">
                        {metric.value}
                      </div>
                      <div className="flex items-center gap-1 text-sm font-medium text-muted-foreground">
                        <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: metric.color }} />
                        <span className="truncate">{metric.title}</span>
                        {metric.description && (
                          <Tooltip
                            content={<span className="whitespace-normal max-w-[200px] block">{metric.description}</span>}
                            iconClassName="w-3 h-3"
                            contentClassName="w-48 text-center"
                          />
                        )}
                      </div>
                    </div>
                    {!isLastInRow && (
                      <>
                        <div className="hidden sm:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                        <div className="sm:hidden border-b border-zinc-100 mt-3" />
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </Card>

      <PerformanceChart dateRange={dateRange} agentId={agentId} />
    </div>
  );
};
