import { useQuery } from "@tanstack/react-query";
import { ExternalLink, MessageCircle, RefreshCw, ShieldAlert } from "lucide-react";

import { apiRequest } from "@/config/api";
import { Button } from "@/components/button";
import { BackendTranscript, Transcript } from "@/interfaces/transcript.interface";
import { transformTranscript } from "@/views/Transcripts/helpers/transformers";
import { TranscriptThread } from "@/views/Transcripts/components/TranscriptThread";
import { formatDateTime } from "@/helpers/utils";

const conversationTranscriptKey = (conversationId: string) =>
  ["conversation", conversationId, "transcript"] as const;

/**
 * Same request the `/transcripts?conversation=<id>` deep link makes, so the embedded
 * thread shows exactly what the full Transcripts view would.
 */
async function fetchConversationTranscript(
  conversationId: string,
): Promise<Transcript> {
  // apiRequest resolves to null on 403 instead of throwing, so a scoped-out
  // conversation lands here rather than in the catch.
  const backend = await apiRequest<BackendTranscript>(
    "get",
    `conversations/${encodeURIComponent(conversationId)}?include_feedback=true`,
  );
  if (!backend) {
    throw new Error(
      "This conversation may not exist or you may not have access to it.",
    );
  }

  // transformTranscript swallows its own errors and returns an "error" stub.
  const transformed = transformTranscript(backend);
  if (!transformed || transformed.id === "error") {
    throw new Error("This conversation could not be read.");
  }

  return transformed;
}

function ThreadSkeleton() {
  // Alternating bubble widths so the placeholder reads as a conversation.
  const rows = [
    { self: false, width: "w-2/3" },
    { self: true, width: "w-1/2" },
    { self: false, width: "w-3/5" },
    { self: true, width: "w-2/3" },
    { self: false, width: "w-1/2" },
  ];

  return (
    <div className="space-y-4 p-4" aria-hidden>
      {rows.map((row, index) => (
        <div
          key={index}
          className={`flex flex-col gap-1.5 ${row.self ? "items-end" : "items-start"}`}
        >
          <div className="h-2.5 w-14 animate-pulse rounded bg-muted" />
          <div
            className={`h-12 animate-pulse rounded-lg bg-muted ${row.width}`}
          />
        </div>
      ))}
    </div>
  );
}

type ConversationPanelProps = {
  conversationId: string;
  /** The reported message — ringed and scrolled into view once the thread loads. */
  highlightMessageId?: string | null;
  topic?: string | null;
  conversationDate?: string | null;
  /** Opens the full Transcripts view (stats, costs, Ask GenAI) in a new tab. */
  onOpenFullTranscript: () => void;
};

/**
 * The conversation behind a reported comment, rendered inside the Reported Feedback dialog
 * so reviewers keep their place in the list instead of navigating to Transcripts.
 *
 * The thread is deliberately read-only (`variant="compact"`): the dialog's detail pane already
 * owns the comment and its status, and offering a second place to edit the same comment inside
 * one dialog is ambiguous. Full editing stays one click away via "Open full transcript".
 */
export function ConversationPanel({
  conversationId,
  highlightMessageId,
  topic,
  conversationDate,
  onOpenFullTranscript,
}: ConversationPanelProps) {
  const {
    data: transcript,
    isPending,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: conversationTranscriptKey(conversationId),
    queryFn: () => fetchConversationTranscript(conversationId),
    enabled: Boolean(conversationId),
    staleTime: 30_000,
    retry: false,
  });

  const isCall =
    Boolean(transcript?.recording_id) || Boolean(transcript?.metadata?.isCall);

  return (
    <div className="flex min-h-0 flex-col bg-muted/20">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b bg-background/60 px-5 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <MessageCircle className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-foreground">
              {topic || "Untitled conversation"}
            </div>
            {conversationDate && (
              <div className="truncate text-xs text-muted-foreground">
                {formatDateTime(conversationDate)}
              </div>
            )}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="shrink-0 gap-1.5 rounded-full text-xs"
          onClick={onOpenFullTranscript}
          title="Open the full transcript — stats, costs and Ask GenAI — in a new tab"
        >
          Full transcript
          <ExternalLink className="h-3.5 w-3.5" />
        </Button>
      </div>

      {isPending ? (
        <ThreadSkeleton />
      ) : isError ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-12 text-center">
          <div className="rounded-full bg-destructive/10 p-3">
            <ShieldAlert className="h-7 w-7 text-destructive" />
          </div>
          <div>
            <h4 className="text-sm font-medium">Couldn't load the conversation</h4>
            <p className="mx-auto mt-1 max-w-xs text-xs text-muted-foreground">
              {error instanceof Error
                ? error.message
                : "Something went wrong loading this conversation."}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5 rounded-full"
            disabled={isFetching}
            onClick={() => void refetch()}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`}
            />
            Try again
          </Button>
        </div>
      ) : (
        <TranscriptThread
          transcript={transcript}
          isCall={isCall}
          variant="compact"
          highlightMessageId={highlightMessageId}
          className="min-h-0 flex-1 px-4 py-3"
        />
      )}
    </div>
  );
}
