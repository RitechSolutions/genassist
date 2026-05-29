import type { ReactNode } from "react";
import { BarChart2, Database, GitBranch, LineChart, Tags } from "lucide-react";
import { ListEmptyState } from "@/components/ListEmptyState";
import { Card } from "@/components/card";
import { analyticsFadeUpClass } from "../constants/animations";
import { cn } from "@/helpers/utils";

function AnalyticsEmptyStateCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card
      className={cn(
        "overflow-hidden rounded-lg border bg-white",
        analyticsFadeUpClass,
        className,
      )}
    >
      {children}
    </Card>
  );
}

/** No rows in summary tables yet (aggregation not run). */
export function AnalyticsAggregatedDataEmptyState() {
  return (
    <AnalyticsEmptyStateCard>
      <ListEmptyState
        icon={<Database className="h-12 w-12 text-gray-400" />}
        title="No analytics data yet"
        description="Run the aggregation task to populate the summary tables. Metrics will appear once your agents have activity in the selected period."
      />
    </AnalyticsEmptyStateCard>
  );
}

/** Node analytics — no rows in summary tables yet. */
export function NodeAnalyticsAggregatedDataEmptyState() {
  return (
    <AnalyticsEmptyStateCard>
      <ListEmptyState
        icon={<GitBranch className="h-12 w-12 text-gray-400" />}
        title="No node data yet"
        description="Run the aggregation task to populate the summary tables. Node execution metrics will appear once workflows have been run in the selected period."
      />
    </AnalyticsEmptyStateCard>
  );
}

/** Table / chart — filters applied but nothing in range. */
export function AnalyticsPeriodEmptyState({
  title = "No data for this period",
  description = "Try expanding the date range or changing your agent filter.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <ListEmptyState
      icon={<BarChart2 className="h-12 w-12 text-gray-400" />}
      title={title}
      description={description}
    />
  );
}

export function AgentPerformanceTableEmptyState() {
  return (
    <AnalyticsPeriodEmptyState
      title="No performance data for this period"
      description="Try a wider date range, pick another agent, or wait until conversations are recorded for this agent."
    />
  );
}

export function NodeAnalyticsTableEmptyState() {
  return (
    <AnalyticsPeriodEmptyState
      title="No node data for this period"
      description="Try a wider date range, another node type, or a different agent filter."
    />
  );
}

export function DailyConversationsChartEmptyState() {
  return (
    <ListEmptyState
      icon={<LineChart className="h-12 w-12 text-gray-400" />}
      title="No conversations in this period"
      description="Adjust the date range or agent filter to see daily conversation trends."
    />
  );
}

export function NodeBreakdownChartEmptyState() {
  return (
    <ListEmptyState
      icon={<GitBranch className="h-12 w-12 text-gray-400" />}
      title="No node executions in this period"
      description="Adjust the date range or filters to see node type breakdown."
    />
  );
}

export function PerformanceTrendChartEmptyState() {
  return (
    <ListEmptyState
      icon={<LineChart className="h-12 w-12 text-gray-400" />}
      title="No insights for this period"
      description="Select a date range with analyzed conversations, or change the agent filter."
    />
  );
}

export function AttributeBreakdownEmptyState() {
  return (
    <ListEmptyState
      icon={<Tags className="h-12 w-12 text-gray-400" />}
      title="No data for this attribute"
      description="This attribute has no values in the selected period. Try another attribute or expand the date range."
    />
  );
}
