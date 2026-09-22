import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Transcript } from "@/interfaces/transcript.interface";
import { ConversationsWorkspace } from "@/views/Transcripts/components/workspace/ConversationsWorkspace";

interface Props {
  /** Live conversations only — the dashboard's own list, already enriched. */
  conversations: Transcript[];
  selectedTranscript: Transcript | null;
  isLoading?: boolean;
  error?: Error | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (transcript: Transcript) => void;
  onClearSelection: () => void;
  onTakeOver: (transcriptId: string) => Promise<boolean>;
  refetchConversations: () => void;
  /** Awaited once a conversation is finalized — the dialog only lists running ones. */
  onConversationFinalized?: (transcriptId: string) => void | Promise<void>;
}

/**
 * The dashboard's live conversation surface: the same three columns as the Conversations
 * split view (list, conversation, stats), hosted in a dialog and restricted to conversations
 * that are still in progress.
 */
export function LiveConversationsDialog({
  conversations,
  selectedTranscript,
  isLoading = false,
  error = null,
  isOpen,
  onOpenChange,
  onSelect,
  onClearSelection,
  onTakeOver,
  refetchConversations,
  onConversationFinalized,
}: Props) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[88vh] w-[96vw] max-w-[1500px] flex-col overflow-x-hidden overflow-y-hidden p-4 sm:p-6">
        <DialogHeader className="mb-0 shrink-0">
          <DialogTitle>Live conversations</DialogTitle>
        </DialogHeader>

        <ConversationsWorkspace
          className="mt-4 flex-1"
          transcripts={conversations}
          loading={isLoading}
          error={error}
          selectedTranscript={selectedTranscript}
          selectedId={selectedTranscript?.id ?? null}
          isLiveSelected
          onSelect={onSelect}
          onClearSelection={onClearSelection}
          emptyDescription="No conversations are running right now."
          refetchConversations={refetchConversations}
          onTakeOver={onTakeOver}
          onConversationFinalized={onConversationFinalized}
        />
      </DialogContent>
    </Dialog>
  );
}
