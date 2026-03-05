import { Card } from "@/components/card";
import { Tooltip } from "@/components/tooltip";
import type { AgentStatsSummaryResponse } from "@/interfaces/analyticsReports.interface";

interface SummaryStatsCardsProps {
  summary: AgentStatsSummaryResponse | null;
  loading: boolean;
  error: string | null;
}

interface StatMetric {
  label: string;
  value: string;
  sub?: string;
  description?: string;
}

function buildMetrics(summary: AgentStatsSummaryResponse): StatMetric[] {
  const successRate =
    summary.total_executions > 0
      ? ((summary.total_success / summary.total_executions) * 100).toFixed(1)
      : "0.0";

  return [
    {
      label: "Conversations",
      value: summary.total_unique_conversations.toLocaleString(),
      sub: (summary.total_finalized_conversations + summary.total_in_progress_conversations) > 0
        ? `${summary.total_finalized_conversations} finalized · ${summary.total_in_progress_conversations} in progress`
        : undefined,
      description: "Unique chat sessions started with any agent in the selected period.",
    },
    {
      label: "Total Executions",
      value: summary.total_executions.toLocaleString(),
      description: "Number of times a workflow was triggered and run end-to-end.",
    },
    {
      label: "Success Rate",
      value: `${successRate}%`,
      description: "Percentage of executions that completed without errors.",
    },
    {
      label: "Avg Response Time",
      value: summary.avg_response_ms != null ? `${Math.round(summary.avg_response_ms)} ms` : "—",
      description: "Weighted average time from workflow start to final response, across all executions.",
    },
    {
      label: "Thumbs Up",
      value: summary.total_thumbs_up.toLocaleString(),
      description: "Positive feedback submitted by users on agent responses.",
    },
    {
      label: "Thumbs Down",
      value: summary.total_thumbs_down.toLocaleString(),
      description: "Negative feedback submitted by users on agent responses.",
    },
  ];
}

const PLACEHOLDER_COUNT = 6;

export function SummaryStatsCards({ summary, loading, error }: SummaryStatsCardsProps) {
  if (loading) {
    return (
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6 lg:gap-8">
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

  const metrics = buildMetrics(summary);

  return (
    <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6 lg:gap-8">
        {metrics.map((metric, index) => (
          <div key={metric.label} className="relative">
            <div className="flex flex-col gap-1 py-2 sm:py-0">
              <div className="text-xl sm:text-2xl font-bold text-foreground leading-tight">
                {metric.value}
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
