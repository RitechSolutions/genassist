import { TableSkeleton } from "@/components/skeletons";
import { analyticsFadeUpClass } from "../../constants/animations";
import { AnalyticsChartCardSkeleton } from "./AnalyticsChartCardSkeleton";
import { AnalyticsMetricsCardsSkeleton } from "./AnalyticsMetricsCardsSkeleton";

export interface AgentPerformancePageSkeletonProps {
  /** Table column count (6 with agent column, 6 with date column) */
  tableColumns?: number;
}

/** Agent Performance page body while data is loading. */
export function AgentPerformancePageSkeleton({
  tableColumns = 6,
}: AgentPerformancePageSkeletonProps) {
  return (
    <div className="space-y-6 sm:space-y-8">
      <AnalyticsMetricsCardsSkeleton />
      <AnalyticsChartCardSkeleton variant="area" />
      <TableSkeleton columns={tableColumns} rows={6} className={analyticsFadeUpClass} />
    </div>
  );
}
