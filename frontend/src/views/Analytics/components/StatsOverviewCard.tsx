import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { Card } from "@/components/card";

interface StatMetric {
  label: string;
  value: string;
  change: number;
  changeType: "increase" | "decrease" | "neutral";
}

interface StatsOverviewCardProps {
  metrics: StatMetric[];
}

export const StatsOverviewCard = ({ metrics }: StatsOverviewCardProps) => {
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

  const getChangeBadgeColor = (changeType: "increase" | "decrease" | "neutral") => {
    switch (changeType) {
      case "increase":
        return "bg-green-200";
      case "decrease":
        return "bg-red-200";
      case "neutral":
        return "bg-zinc-200";
    }
  };

  const getChangeTextColor = (changeType: "increase" | "decrease" | "neutral") => {
    switch (changeType) {
      case "increase":
        return "text-green-600";
      case "decrease":
        return "text-red-600";
      case "neutral":
        return "text-zinc-600";
    }
  };

  const getChangeIconColor = (changeType: "increase" | "decrease" | "neutral") => {
    switch (changeType) {
      case "increase":
        return "text-green-700";
      case "decrease":
        return "text-red-700";
      case "neutral":
        return "text-zinc-600";
    }
  };

  return (
    <Card className="w-full px-6 py-6 shadow-sm bg-white">
      <div className="flex items-center gap-8">
        {metrics.map((metric, index) => {
          const ChangeIcon = getChangeIcon(metric.changeType);
          
          return (
            <div key={index} className="flex items-center gap-8 flex-1">
              <div className="flex flex-col gap-4 py-0 flex-1">
                <div className="flex items-center gap-4">
                  <div className="text-2xl font-bold text-foreground leading-8">
                    {metric.value}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`${getChangeBadgeColor(metric.changeType)} flex items-center p-1 rounded-full`}>
                      <ChangeIcon className={`w-5 h-5 ${getChangeIconColor(metric.changeType)}`} />
                    </div>
                    <div className={`text-base font-medium ${getChangeTextColor(metric.changeType)}`}>
                      {metric.change === 0 ? "No Change" : `${Math.abs(metric.change)}%`}
                    </div>
                  </div>
                </div>
                <div className="text-base font-medium text-foreground">
                  {metric.label}
                </div>
              </div>
              
              {index < metrics.length - 1 && (
                <div className="h-16 w-0 border-l border-zinc-200" />
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
