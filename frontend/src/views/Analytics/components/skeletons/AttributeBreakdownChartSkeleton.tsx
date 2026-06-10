import { Card, CardContent, CardHeader } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";
import { analyticsFadeUpClass } from "../../constants/animations";

/** Chart bars + metrics table placeholder (no card wrapper). */
export function AttributeBreakdownChartBodySkeleton() {
  return (
    <>
      <div className="space-y-4 py-2">
        {[1, 0.75, 0.5].map((scale, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-20 shrink-0" />
            <Skeleton className="h-8 rounded-md" style={{ width: `${scale * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-6 overflow-hidden rounded-lg border border-gray-100">
        <div className="flex gap-4 border-b border-gray-100 bg-gray-50/80 px-4 py-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-3 flex-1" />
          ))}
        </div>
        {Array.from({ length: 3 }, (_, row) => (
          <div
            key={row}
            className="flex gap-4 border-t border-gray-100 px-4 py-3"
          >
            {Array.from({ length: 6 }, (_, col) => (
              <Skeleton key={col} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

export interface AttributeBreakdownChartSkeletonProps {
  className?: string;
}

export function AttributeBreakdownChartSkeleton({
  className,
}: AttributeBreakdownChartSkeletonProps) {
  return (
    <Card className={cn("mt-6 bg-white", analyticsFadeUpClass, className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <div className="space-y-2">
          <Skeleton className="h-5 w-52" />
          <Skeleton className="h-3 w-40" />
        </div>
        <Skeleton className="h-9 w-44 rounded-md" />
      </CardHeader>
      <CardContent>
        <AttributeBreakdownChartBodySkeleton />
      </CardContent>
    </Card>
  );
}
