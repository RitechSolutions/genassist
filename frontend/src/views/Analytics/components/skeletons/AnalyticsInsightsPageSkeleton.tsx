import { AnalyticsChartCardSkeleton } from "./AnalyticsChartCardSkeleton";
import { AnalyticsMetricsCardsSkeleton } from "./AnalyticsMetricsCardsSkeleton";
import { AttributeBreakdownChartSkeleton } from "./AttributeBreakdownChartSkeleton";

/** AI Insights page body while primary metrics are loading. */
export function AnalyticsInsightsPageSkeleton() {
  return (
    <div className="space-y-6 sm:space-y-8">
      <AnalyticsMetricsCardsSkeleton showContextLine />
      <AnalyticsChartCardSkeleton variant="area" />
      <AttributeBreakdownChartSkeleton />
    </div>
  );
}
