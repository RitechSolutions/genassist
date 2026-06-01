import { Card } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";
import { analyticsKpiGridClass } from "../AnalyticsKpiStat";
import { analyticsFadeUpClass } from "../../constants/animations";

export interface AnalyticsMetricsCardsSkeletonProps {
  /** Number of metric columns to mimic */
  count?: number;
  /** Show a context-line placeholder above the grid */
  showContextLine?: boolean;
  className?: string;
}

export function AnalyticsMetricsCardsSkeleton({
  count = 5,
  showContextLine = false,
  className,
}: AnalyticsMetricsCardsSkeletonProps) {
  return (
    <Card
      className={cn(
        "w-full bg-white px-4 py-4 shadow-sm sm:px-6 sm:py-6",
        analyticsFadeUpClass,
        className,
      )}
    >
      {showContextLine && <Skeleton className="mb-4 h-3 w-56 max-w-full" />}
      <div className={analyticsKpiGridClass(count)}>
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="flex min-w-0 flex-col gap-2 py-1">
            <Skeleton className="h-7 w-16 max-w-full" />
            <Skeleton className="h-4 w-full max-w-[7rem]" />
            <Skeleton className="h-3 w-full max-w-[9rem]" />
          </div>
        ))}
      </div>
    </Card>
  );
}
