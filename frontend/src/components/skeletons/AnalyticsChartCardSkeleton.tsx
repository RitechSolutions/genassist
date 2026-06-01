import { Card, CardContent, CardHeader } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";
import { analyticsFadeUpClass } from "@/views/Analytics/constants/animations";

export type AnalyticsChartCardSkeletonVariant = "area" | "bar-horizontal";

export interface AnalyticsChartCardSkeletonProps {
  variant?: AnalyticsChartCardSkeletonVariant;
  className?: string;
}

export function AnalyticsChartCardSkeleton({
  variant = "area",
  className,
}: AnalyticsChartCardSkeletonProps) {
  return (
    <Card className={cn("bg-white shadow-sm", analyticsFadeUpClass, className)}>
      <CardHeader className="pb-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Skeleton className="h-4 w-40" />
          <div className="flex items-center gap-4">
            <Skeleton className="h-3 w-24" />
            {variant === "bar-horizontal" && <Skeleton className="h-3 w-20" />}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {variant === "area" ? (
          <Skeleton className="h-[240px] w-full rounded-lg sm:h-[280px]" />
        ) : (
          <div className="space-y-3 py-1">
            {[1, 0.85, 0.7, 0.55, 0.45, 0.35].map((scale, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-28 shrink-0" />
                <Skeleton className="h-7 rounded-md" style={{ width: `${scale * 100}%` }} />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
