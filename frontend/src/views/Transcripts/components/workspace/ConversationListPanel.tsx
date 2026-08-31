import {
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  PlayCircle,
  Radio,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import { Button } from "@/components/button";
import { PageListSkeleton } from "@/components/skeletons";
import { cn } from "@/helpers/utils";
import { Transcript } from "@/interfaces/transcript.interface";

import { getEffectiveSentiment, isLiveTranscript } from "../../helpers/formatting";
import { SentimentBadge } from "../SentimentBadge";

const isCallTranscript = (transcript: Transcript) =>
  Boolean(transcript?.recording_id) || Boolean(transcript?.metadata?.isCall);

/** Time for a list row: clock time for today, short date before that. */
function formatRowTimestamp(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "";

  const now = new Date();
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  return isToday
    ? date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function lastMessagePreview(transcript: Transcript): string {
  const messages = transcript.messages ?? [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const text = messages[index]?.text?.trim();
    if (text) return text;
  }
  return "";
}

type ConversationListPanelProps = {
  transcripts: Transcript[];
  loading: boolean;
  error: unknown;
  selectedId: string | null;
  onSelect: (transcript: Transcript) => void;
  /** Omit the pager props for an unpaged list (e.g. the live dashboard). */
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  hasNarrowingFilters?: boolean;
  /** Shown under the empty state when no filters are narrowing the list. */
  emptyDescription?: string;
  className?: string;
};

/**
 * The conversation column of the split view: a compact, selectable row per conversation with
 * its own pager, so the detail columns keep their scroll position while the user browses.
 */
export function ConversationListPanel({
  transcripts,
  loading,
  error,
  selectedId,
  onSelect,
  total = 0,
  page = 1,
  pageSize = 0,
  onPageChange,
  hasNarrowingFilters = false,
  emptyDescription = "Try a wider date range or different filters.",
  className,
}: ConversationListPanelProps) {
  const paged = Boolean(onPageChange) && pageSize > 0;
  const totalPages = Math.max(1, Math.ceil(Math.max(0, total) / Math.max(1, pageSize)));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const rangeStart = transcripts.length === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const rangeEnd = (safePage - 1) * pageSize + transcripts.length;

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <PageListSkeleton variant="conversation" rows={6} bordered={false} />
        ) : error ? (
          <p className="p-6 text-center text-sm text-red-500">
            Error loading conversations. Please try again.
          </p>
        ) : transcripts.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
            <div className="rounded-full bg-muted p-3">
              <MessageSquare className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">
              {hasNarrowingFilters ? "No conversations match your filters" : "No conversations yet"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hasNarrowingFilters ? "Try adjusting your search or filters." : emptyDescription}
            </p>
          </div>
        ) : (
          transcripts.map((transcript) => {
            const isSelected = transcript.id === selectedId;
            const live = isLiveTranscript(transcript);
            const sentiment = getEffectiveSentiment(transcript);
            const preview = lastMessagePreview(transcript);

            return (
              <button
                key={transcript.id}
                type="button"
                onClick={() => onSelect(transcript)}
                aria-current={isSelected}
                className={cn(
                  "flex w-full items-start gap-2.5 border-b border-border px-3 py-3 text-left transition-colors",
                  isSelected ? "bg-primary/5" : "hover:bg-muted/70"
                )}
              >
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/5">
                  {isCallTranscript(transcript) ? (
                    <PlayCircle className="h-4 w-4 text-primary" />
                  ) : (
                    <MessageSquare className="h-4 w-4 text-primary" />
                  )}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-semibold">
                      {isCallTranscript(transcript) ? "Call" : "Chat"} #
                      {(transcript?.metadata?.title ?? "----").slice(-4)}
                    </span>
                    {live && (
                      // Same badge as the list view — a <span> because the row itself is a <button>.
                      <span className="flex shrink-0 animate-pulse items-center gap-1 rounded-full border border-green-200 bg-green-50 px-2.5 py-0.5 text-xs font-semibold text-green-700 dark:border-green-500/30 dark:bg-green-500/15 dark:text-green-400">
                        <Radio className="w-3 h-3" />
                        <span>Live</span>
                      </span>
                    )}
                    <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
                      {formatRowTimestamp(transcript.timestamp)}
                    </span>
                  </span>
                  {transcript?.metadata?.topic ? (
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {transcript.metadata.topic}
                    </span>
                  ) : null}
                  {preview ? (
                    <span className="mt-1 block truncate text-xs text-muted-foreground/80">{preview}</span>
                  ) : null}
                  <span className="mt-1.5 flex flex-wrap items-center gap-2">
                    <SentimentBadge sentiment={sentiment} />
                    {(transcript?.thumbs_up_count ?? 0) > 0 && (
                      <span className="flex items-center gap-0.5 text-[11px] text-muted-foreground">
                        <ThumbsUp className="h-3 w-3 text-emerald-500" />
                        {transcript.thumbs_up_count}
                      </span>
                    )}
                    {(transcript?.thumbs_down_count ?? 0) > 0 && (
                      <span className="flex items-center gap-0.5 text-[11px] text-muted-foreground">
                        <ThumbsDown className="h-3 w-3 text-rose-400" />
                        {transcript.thumbs_down_count}
                      </span>
                    )}
                  </span>
                </span>
              </button>
            );
          })
        )}
      </div>

      {paged && total > 0 && (
        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border px-3 py-2">
          <span className="truncate text-[11px] text-muted-foreground">
            {rangeStart}-{rangeEnd} of {total}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={safePage <= 1}
              onClick={() => onPageChange?.(safePage - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="tabular-nums text-[11px] text-muted-foreground">
              {safePage} / {totalPages}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={safePage >= totalPages}
              onClick={() => onPageChange?.(safePage + 1)}
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
