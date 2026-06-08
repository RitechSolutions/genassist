import { TableSkeleton } from "@/components/skeletons";
import { analyticsFadeUpClass } from "../../constants/animations";
import { AnalyticsChartCardSkeleton } from "./AnalyticsChartCardSkeleton";

/** Node Analytics page body while data is loading. */
export function NodeAnalyticsPageSkeleton() {
  return (
    <div className="space-y-6 sm:space-y-8">
      <AnalyticsChartCardSkeleton variant="bar-horizontal" />
      <TableSkeleton columns={6} rows={6} className={analyticsFadeUpClass} />
    </div>
  );
}
