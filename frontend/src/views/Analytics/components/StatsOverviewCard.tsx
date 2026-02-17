import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { Card } from "@/components/card";
import { getChangeBadgeColor, getChangeIconColor, getChangeTextColor } from "../helpers/badgeColors";

interface StatMetric {
  label: string;
  value: string;
  change: number;
  changeType: "increase" | "decrease" | "neutral";
}

interface StatsOverviewCardProps {
  metrics: StatMetric[];
  loading?: boolean;
}

export const StatsOverviewCard = ({ metrics, loading = false }: StatsOverviewCardProps) => {
  const getChangeIcon = (changeType: "increase" | "decrease" | "neutral") => {
    switch (changeType) {
      case "increase":
        return ArrowUp;
      case "decrease":
        return ArrowDown;
      case "neutral":
        return Minus;
    }
  };

  if (loading) {
    return (
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-8">
          {[1, 2, 3].map((index) => (
            <div key={index} className="relative">
              <div className="flex flex-col gap-3 sm:gap-4 py-2 sm:py-0">
                <div className="h-8 w-20 bg-gray-200 rounded animate-pulse" />
                <div className="h-5 w-28 bg-gray-200 rounded animate-pulse" />
              </div>
              {index < 3 && (
                <>
                  <div className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                  <div className="sm:hidden border-b border-zinc-200 mt-4" />
                </>
              )}
            </div>
          ))}
        </div>
      </Card>
    );
  }

  const gridColsClass =
    metrics.length === 4
      ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
      : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";

  return (
    <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up">
      <div className={`grid ${gridColsClass} gap-4 sm:gap-6 lg:gap-8`}>
        {metrics.map((metric, index) => {
          const ChangeIcon = getChangeIcon(metric.changeType);

          return (
            <div key={index} className="relative">
              <div className="flex flex-col gap-3 sm:gap-4 py-2 sm:py-0">
                <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
                  <div className="text-xl sm:text-2xl font-bold text-foreground leading-tight">
                    {metric.value}
                  </div>
                  {/* TODO */}
                  {/* <div className="flex items-center gap-2">
                    <div className={`${getChangeBadgeColor(metric.changeType)} flex items-center p-1 rounded-full`}>
                      <ChangeIcon className={`w-4 h-4 sm:w-5 sm:h-5 ${getChangeIconColor(metric.changeType)}`} />
                    </div>
                    <div className={`text-sm sm:text-base font-medium ${getChangeTextColor(metric.changeType)}`}>
                      {metric.change === 0 ? "No Change" : `${Math.abs(metric.change)}%`}
                    </div>
                  </div> */}
                </div>
                <div className="text-sm sm:text-base font-medium text-foreground">
                  {metric.label}
                </div>
              </div>

              {/* Vertical divider - hidden on mobile, shown on larger screens between items */}
              {index < metrics.length - 1 && (
                <>
                  <div className="hidden lg:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                  <div className="sm:hidden border-b border-zinc-200 mt-4" />
                </>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
