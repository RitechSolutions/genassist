import { Badge } from "@/components/badge";
import { TriangleAlert, Clock } from "lucide-react";
import { cn } from "@/helpers/utils";
import { formatDuration } from "@/helpers/duration";
import type { NormalizedConversation } from "../helpers/activeConversations.types";

interface RowProps {
  item: NormalizedConversation;
  reason?: string;
  onClick?: (item: NormalizedConversation) => void;
}

export function ConversationRow({ item, reason, onClick }: RowProps) {
  const hostility = Number(item.in_progress_hostility_score || 0);
  const eff = item.effectiveSentiment;
  const sentimentVariant = eff === "negative" ? "destructive" : "default";
  const sentimentLabel = eff === "positive" ? "Good" : eff === "negative" ? "Bad" : "Neutral";
  const showHostility = hostility > 60;
  const shortId = (item.id || "").slice(-4);
  const title = item.topic && item.topic !== "Unknown" ? item.topic : "Booking Inquiry";

  return (
    <div
      role="button"
      tabIndex={0}
      className="bg-primary-foreground px-4 py-4 cursor-pointer border-b border-border last:border-b-0 hover:bg-muted/40 transition-colors"
      onClick={() => onClick?.(item)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(item);
        }
      }}
    >
      <div className="flex flex-col gap-2 w-full">
        {/* Top Row */}
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-3 min-w-0">
            <p className="text-sm font-medium text-foreground shrink-0">
              {title} #{shortId}
            </p>
            <Badge 
              variant={sentimentVariant}
              className="px-2.5 py-0.5 shrink-0"
            >
              {sentimentLabel}
            </Badge>
            {reason && (
              <Badge 
                variant="outline"
                className="px-2.5 py-0.5 shrink-0"
              >
                {reason}
              </Badge>
            )}
            {showHostility && (
              <TriangleAlert className="w-5 h-5 text-destructive shrink-0" />
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Clock className="w-3 h-3 text-muted-foreground" />
            <p className="text-xs text-muted-foreground leading-none">
              {formatDuration(Number(item.duration || 0))}
            </p>
          </div>
        </div>

        {/* Bottom Row - Preview */}
        <p className="text-sm text-muted-foreground leading-5">
          {item.transcript as unknown as string}
        </p>
      </div>
    </div>
  );
}

export default ConversationRow;