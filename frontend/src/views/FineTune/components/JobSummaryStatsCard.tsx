import { ReactNode } from "react";
import { Card } from "@/components/card";

interface JobSummaryStatsCardProps {
  loading?: boolean;
  model: string;
  status: ReactNode;
  accuracy: ReactNode;
  trainedTokens: ReactNode;
}

export function JobSummaryStatsCard({
  loading = false,
  model,
  status,
  accuracy,
  trainedTokens,
}: JobSummaryStatsCardProps) {
  if (loading) {
    return (
      <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up rounded-lg border text-card-foreground">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="relative flex flex-col gap-3 py-2 sm:py-0">
              <div className="h-7 w-20 bg-zinc-100 rounded animate-pulse" />
              <div className="h-4 w-24 bg-zinc-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  const metrics = [
    { label: "Model", value: model },
    { label: "Status", value: status },
    { label: "Accuracy", value: accuracy },
    { label: "# of trained tokens", value: trainedTokens },
  ];

  return (
    <Card className="w-full px-4 py-4 sm:px-6 sm:py-6 shadow-sm bg-white animate-fade-up rounded-lg border text-card-foreground">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-6 lg:gap-8">
        {metrics.map((metric, index) => (
          <div key={metric.label} className="relative">
            <div className="flex flex-col gap-1 py-2 sm:py-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-xl sm:text-2xl font-bold leading-tight text-foreground [&_.animate-spin]:inline-block">
                  {metric.value}
                </span>
              </div>
              <div className="text-sm font-medium text-muted-foreground">
                {metric.label}
              </div>
            </div>
            {index < metrics.length - 1 && (
              <>
                <div className="hidden xl:block absolute right-0 top-1/2 -translate-y-1/2 h-16 w-0 border-l border-zinc-200" />
                <div className="xl:hidden border-b border-zinc-100 mt-3" />
              </>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
