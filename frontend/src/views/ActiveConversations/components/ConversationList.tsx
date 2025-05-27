import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { Link } from "react-router-dom";
import { Skeleton } from "@/components/skeleton";
import { InfoIcon } from "lucide-react";

interface ItemWithSentiment {
  id: string;
  type?: string;
  sentiment: string;
  transcript: string;
}

interface ConversationListProps<T extends ItemWithSentiment> {
  title: string;
  viewAllLink: string;
  items?: T[];
  countDisplay?: number;
  isLoading: boolean;
  error: Error | null;
  onItemClick?: (item: T) => void;
  emptyMessage?: string;
  titleTooltip?: string;
}

export function ConversationList<T extends ItemWithSentiment>({
  title,
  viewAllLink,
  items,
  countDisplay,
  isLoading,
  error,
  onItemClick,
  emptyMessage = "No items found",
  titleTooltip,
}: ConversationListProps<T>) {
  if (error) {
    return (
      <Card className="p-6 mb-6">
        <div className="text-destructive animate-fade-down">
          Error loading data
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 mb-6 animate-fade-up">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          {title}
          <Badge className="text-xs bg-green-600 animate-fade-down">Live</Badge>
          {titleTooltip && (
            <div className="relative group">
              <InfoIcon className="w-4 h-4 text-gray-400 cursor-help" />
              <div className="absolute z-10 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg">
                {titleTooltip}
                <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-800"></div>
              </div>
            </div>
          )}
        </h2>
        <Link
          to={viewAllLink}
          className="text-sm text-primary hover:underline animate-fade-down"
        >
          View all
        </Link>
      </div>

      <div className="flex gap-6 items-center justify-between">
        <div className="flex-shrink-0">
          {isLoading ? (
            <Skeleton className="h-12 w-16" />
          ) : (
            <div className="text-5xl font-bold ml-5 mr-5">{countDisplay}</div>
          )}
        </div>

        <div className="flex-grow bg-muted/40 rounded-lg overflow-hidden">
          {isLoading ? (
            Array(3)
              .fill(0)
              .map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-none" />
              ))
          ) : items.length === 0 ? (
            <div className="text-muted-foreground py-4">{emptyMessage}</div>
          ) : (
            items.slice(0, 3).map((item, index) => (
              <div
                key={item.id}
                className="flex justify-between items-center bg-muted/40 p-4 cursor-pointer hover:bg-muted/70 transition-colors border-b last:border-b-0"
                onClick={() => onItemClick && onItemClick(item)}
              >
                <div className="flex-shrink-0 font-medium w-20">
                  Call #{index + 1}
                </div>
                <div className="flex-grow text-sm text-muted-foreground line-clamp-1">
                  {item.transcript}
                </div>
                <Badge
                  className={`capitalize ${
                    item.sentiment === "positive"
                      ? "bg-green-100 text-green-700"
                      : item.sentiment === "negative"
                      ? "bg-red-100 text-red-700"
                      : "bg-orange-100 text-orange-600"
                  }`}
                >
                  {item.sentiment}
                </Badge>
              </div>
            ))
          )}
        </div>
      </div>
    </Card>
  );
}
