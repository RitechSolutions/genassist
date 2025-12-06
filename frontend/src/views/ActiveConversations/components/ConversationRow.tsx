import { Badge } from "@/components/badge";
import { AlertTriangle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
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
  const sentimentStyle = eff === "positive"
    ? "bg-green-600 text-white"
    : eff === "negative"
    ? "bg-red-600 text-white"
    : "bg-purple-600 text-white";
  const showHostility = hostility > 60;
  const shortId = (item.id || "").slice(-4);

  return (
    <div
      role="button"
      tabIndex={0}
      className="p-4 flex items-start justify-between gap-4 cursor-pointer border-b-2 border-gray-200 last:border-b-0 hover:bg-muted/60"
      onClick={() => onClick?.(item)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(item);
        }
      }}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <div className="font-medium truncate">{item.topic && item.topic !== "Unknown" ? item.topic : "Conversation"} #{shortId}</div>
          <Badge className={cn("capitalize", sentimentStyle)}>{eff === "positive" ? "Good" : eff === "negative" ? "Bad" : "Neutral"}</Badge>
          {reason && <Badge variant="outline" className="border-gray-300 text-gray-700 bg-gray-50">{reason}</Badge>}
          {showHostility && (
            <AlertTriangle className="w-4 h-4 text-red-500 motion-safe:animate-pulse" />
          )}
        </div>
        <div className="text-sm text-muted-foreground truncate">
          {/* preview text should be injected by parent */}
          {item.transcript as unknown as string}
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap">
        <Clock className="w-4 h-4" />
        <span>{formatDuration(Number(item.duration || 0))}</span>
      </div>
    </div>
  );
}

export default ConversationRow;