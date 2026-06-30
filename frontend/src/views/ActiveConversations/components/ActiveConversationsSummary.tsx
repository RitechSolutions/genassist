import { Skeleton } from "@/components/skeleton";
import { cn } from "@/helpers/utils";

interface SummaryProps {
  total: number;
  counts: { bad: number; neutral: number; good: number };
  loading?: boolean;
}

export function ActiveConversationsSummary({ total, counts, loading }: SummaryProps) {
  const sentiments = [
    { label: "Bad", count: counts.bad, color: "bg-red-500" },
    { label: "Neutral", count: counts.neutral, color: "bg-blue-500" },
    { label: "Good", count: counts.good, color: "bg-green-500" },
  ];

  return (
    <div className="flex flex-col items-center gap-6 rounded-2xl bg-muted px-2 pb-2 pt-6 sm:gap-8 sm:pt-8">
      {loading ? (
        <div className="w-full space-y-3">
          <Skeleton className="mx-auto h-10 w-20 sm:h-12 sm:w-24" />
          <div className="flex gap-1">
            <Skeleton className="h-24 flex-1 rounded-lg" />
            <Skeleton className="h-24 flex-1 rounded-lg" />
            <Skeleton className="h-24 flex-1 rounded-lg" />
          </div>
        </div>
      ) : (
        <>
          <div className="text-4xl font-bold leading-none text-foreground sm:text-5xl">
            {total}
          </div>

          <div className="flex gap-1 w-full">
            {sentiments.map((sentiment, index) => (
              <div
                key={index}
                className="flex flex-1 flex-col items-center justify-center gap-1 rounded-lg bg-white px-2 py-3 shadow-sm sm:gap-2 sm:py-4"
              >
                <div className="flex items-center justify-center shrink-0">
                  <div className={cn("w-4 h-[4px] rounded-xl", sentiment.color)} />
                </div>
                <p className="text-sm text-muted-foreground shrink-0">{sentiment.count}</p>
                <p className="text-sm text-accent-foreground shrink-0">{sentiment.label}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default ActiveConversationsSummary;
