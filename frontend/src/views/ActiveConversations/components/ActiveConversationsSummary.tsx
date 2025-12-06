import { Card } from "@/components/card";

interface SummaryProps {
  total: number;
  counts: { bad: number; neutral: number; good: number };
  loading?: boolean;
}

export function ActiveConversationsSummary({ total, counts, loading }: SummaryProps) {
  return (
    <Card className="p-4 bg-muted/40 border-0">
      {loading ? (
        <div className="space-y-4">
          <div className="h-10 w-16 bg-gray-200 rounded" />
          <div className="space-y-3">
            <div className="h-4 w-24 bg-gray-200 rounded" />
            <div className="h-4 w-28 bg-gray-200 rounded" />
            <div className="h-4 w-20 bg-gray-200 rounded" />
          </div>
        </div>
      ) : (
        <>
          <div className="text-5xl font-bold text-center">{total}</div>
          <div className="mt-4 text-sm">
            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-red-500"></span>
                <span>Bad</span>
              </div>
              <span className="font-medium">{counts.bad}</span>
            </div>
            <div className="border-t border-border/50" />
            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-purple-500"></span>
                <span>Neutral</span>
              </div>
              <span className="font-medium">{counts.neutral}</span>
            </div>
            <div className="border-t border-border/50" />
            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-green-500"></span>
                <span>Good</span>
              </div>
              <span className="font-medium">{counts.good}</span>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

export default ActiveConversationsSummary;