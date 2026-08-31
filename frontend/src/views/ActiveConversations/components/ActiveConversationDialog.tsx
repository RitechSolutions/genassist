import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";

import { useActiveConversationDetail } from "../hooks/useActiveConversationDetail";
import { ActiveConversationStatsPanel } from "./detail/ActiveConversationStatsPanel";
import { ActiveConversationThreadPanel } from "./detail/ActiveConversationThreadPanel";
import { ActiveConversationTitle } from "./detail/ActiveConversationTitle";

interface Props {
  transcript: Transcript | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onTakeOver?: (transcriptId: string) => Promise<boolean>;
  refetchConversations?: () => void;
  isWebSocketConnected?: boolean;
  messages?: TranscriptEntry[];
  onSendMessage?: (message: TranscriptEntry) => void;
  isFinalized?: boolean;
  hasSupervisorTakeover?: boolean;
  /** Awaited once the conversation is finalized on the server, after the dialog has closed. */
  onFinalized?: (transcriptId: string) => void | Promise<void>;
}

/**
 * Live conversation detail as a dialog. The body is the same pair of panels the
 * Conversations workspace renders as columns — see `useActiveConversationDetail`.
 */
export function ActiveConversationDialog({
  transcript,
  isOpen,
  onOpenChange,
  onTakeOver,
  refetchConversations,
  messages = [],
  onFinalized,
}: Props) {
  if (!transcript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <ActiveConversationDialogBody
          key={`transcript-dialog-${transcript.id}`}
          transcript={transcript}
          isOpen={isOpen}
          onOpenChange={onOpenChange}
          onTakeOver={onTakeOver}
          refetchConversations={refetchConversations}
          messages={messages}
          onFinalized={onFinalized}
        />
      </DialogContent>
    </Dialog>
  );
}

function ActiveConversationDialogBody({
  transcript,
  isOpen,
  onOpenChange,
  onTakeOver,
  refetchConversations,
  messages,
  onFinalized,
}: Props): JSX.Element {
  const controller = useActiveConversationDetail({
    transcript: transcript as Transcript,
    isActive: isOpen,
    onTakeOver,
    refetchConversations,
    messages,
    onFinalizeStart: () => onOpenChange(false),
    onFinalized,
  });

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          <ActiveConversationTitle controller={controller} />
        </DialogTitle>
      </DialogHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:h-[550px] md:overflow-hidden">
        <ActiveConversationStatsPanel controller={controller} />
        <ActiveConversationThreadPanel
          controller={controller}
          className="md:col-span-2"
        />
      </div>
    </>
  );
}
