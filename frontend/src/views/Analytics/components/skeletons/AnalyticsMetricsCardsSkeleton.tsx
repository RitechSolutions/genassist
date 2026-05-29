import { Card } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";
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
  const colClass =
    count >= 5
      ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5"
      : count === 4
        ? "grid-cols-2 sm:grid-cols-2 lg:grid-cols-4"
        : "grid-cols-2 sm:grid-cols-3";

  return (
    <Card
      className={cn(
        "w-full bg-white px-4 py-4 shadow-sm sm:px-6 sm:py-6",
        analyticsFadeUpClass,
        className,
      )}
    >
      {showContextLine && <Skeleton className="mb-4 h-3 w-56" />}
      <div className={cn("grid gap-4 sm:gap-6 lg:gap-8", colClass)}>
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="flex flex-col gap-2 py-2 sm:py-0">
            <Skeleton className="h-7 w-16" />
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-36" />
          </div>
        ))}
      </div>
    </Card>
  );
}
