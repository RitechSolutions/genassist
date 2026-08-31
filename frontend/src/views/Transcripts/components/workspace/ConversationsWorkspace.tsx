import { Loader2, MessageSquare } from "lucide-react";
import { useCallback, useState } from "react";

import { Card } from "@/components/card";
import { cn } from "@/helpers/utils";
import { Transcript } from "@/interfaces/transcript.interface";

import { ConversationDetailPane } from "./ConversationDetailPane";
import { ConversationListPanel } from "./ConversationListPanel";

type ConversationsWorkspaceProps = {
  transcripts: Transcript[];
  loading: boolean;
  error: unknown;
  /** Full record for the selected row — refreshed by the page, so it carries messages. */
  selectedTranscript: Transcript | null;
  selectedId: string | null;
  isLiveSelected: boolean;
  onSelect: (transcript: Transcript) => void;
  onClearSelection: () => void;
  agentName?: string;
  /** Omit the pager props for an unpaged list (e.g. the live dashboard). */
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  hasNarrowingFilters?: boolean;
  emptyDescription?: string;
  refetchConversations: () => void;
  onTakeOver: (transcriptId: string) => Promise<boolean>;
  /** Awaited after a live conversation is finalized, so the owner can swap in the finalized view. */
  onConversationFinalized?: (transcriptId: string) => void | Promise<void>;
  className?: string;
};

/**
 * Split view for the Conversations page: conversation list, the conversation itself and its
 * stats as separate columns. Below `lg` the list and the conversation swap places instead of
 * sitting side by side.
 */
export function ConversationsWorkspace({
  transcripts,
  loading,
  error,
  selectedTranscript,
  selectedId,
  isLiveSelected,
  onSelect,
  onClearSelection,
  agentName,
  total,
  page,
  pageSize,
  onPageChange,
  hasNarrowingFilters,
  emptyDescription,
  refetchConversations,
  onTakeOver,
  onConversationFinalized,
  className,
}: ConversationsWorkspaceProps) {
  const [showStats, setShowStats] = useState(true);
  // A blocking action inside the detail (finalizing) covers the whole workspace, not just the
  // conversation column: the list must not keep offering the conversation as live meanwhile.
  const [busy, setBusy] = useState<{ active: boolean; label?: string }>({ active: false });

  const handleBusyChange = useCallback((active: boolean, label?: string) => {
    setBusy((prev) =>
      prev.active === active && prev.label === label ? prev : { active, label }
    );
  }, []);

  return (
    <div className={cn("relative flex min-h-0 gap-3", className)} aria-busy={busy.active}>
      <Card
        className={cn(
          "min-h-0 w-full flex-col overflow-hidden bg-card shadow-sm dark:bg-zinc-900 lg:w-[340px] lg:shrink-0",
          selectedTranscript ? "hidden lg:flex" : "flex"
        )}
      >
        <ConversationListPanel
          transcripts={transcripts}
          loading={loading}
          error={error}
          selectedId={selectedId}
          onSelect={onSelect}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={onPageChange}
          hasNarrowingFilters={hasNarrowingFilters}
          emptyDescription={emptyDescription}
          className="flex-1"
        />
      </Card>

      {selectedTranscript ? (
        <ConversationDetailPane
          transcript={selectedTranscript}
          isLive={isLiveSelected}
          agentName={agentName}
          onBack={onClearSelection}
          showStats={showStats}
          onToggleStats={() => setShowStats((prev) => !prev)}
          refetchConversations={refetchConversations}
          onTakeOver={onTakeOver}
          onConversationFinalized={onConversationFinalized}
          onBusyChange={handleBusyChange}
        />
      ) : (
        <Card className="hidden min-w-0 flex-1 flex-col items-center justify-center gap-3 bg-card text-center shadow-sm dark:bg-zinc-900 lg:flex">
          <div className="rounded-full bg-muted p-4">
            <MessageSquare className="h-10 w-10 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">Select a conversation</p>
          <p className="max-w-xs text-sm text-muted-foreground">
            Pick a conversation on the left to read the transcript and review its stats.
          </p>
        </Card>
      )}

      {busy.active && (
        <div
          role="status"
          aria-live="polite"
          className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-lg bg-background/80 backdrop-blur-sm"
        >
          <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden />
          {busy.label ? <p className="text-sm font-medium">{busy.label}</p> : null}
        </div>
      )}
    </div>
  );
}
