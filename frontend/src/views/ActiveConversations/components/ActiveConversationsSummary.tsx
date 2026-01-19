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
    <div className="bg-muted rounded-2xl flex flex-col gap-12 items-center pt-12 pb-1 px-1 max-h-[240px]">
      {loading ? (
        <div className="space-y-4">
          <div className="h-12 w-24 bg-gray-200 rounded animate-pulse" />
          <div className="flex gap-1">
            <div className="h-24 flex-1 bg-gray-200 rounded animate-pulse" />
            <div className="h-24 flex-1 bg-gray-200 rounded animate-pulse" />
            <div className="h-24 flex-1 bg-gray-200 rounded animate-pulse" />
          </div>
        </div>
      ) : (
        <>
          <div className="text-5xl font-bold text-foreground leading-[48px]">
            {total}
          </div>
          
          <div className="flex gap-1 w-full">
            {sentiments.map((sentiment, index) => (
              <div
                key={index}
                className="flex-1 bg-white rounded-lg shadow-sm px-2 py-4 flex flex-col gap-2 items-center justify-center"
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