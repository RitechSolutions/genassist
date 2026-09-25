import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";

function toEpochMs(ct: string | number | undefined | null): number {
  if (ct == null) return 0;
  if (typeof ct === "number") return ct;
  const t = new Date(ct).getTime();
  return isNaN(t) ? 0 : t;
}

function areMessagesEquivalent(
  previous: TranscriptEntry[],
  next: TranscriptEntry[]
): boolean {
  if (previous === next) return true;
  if (previous.length !== next.length) return false;

  for (let index = 0; index < previous.length; index += 1) {
    const prevMsg = previous[index];
    const nextMsg = next[index];

    if (
      prevMsg.type !== nextMsg.type ||
      prevMsg.speaker !== nextMsg.speaker ||
      prevMsg.text !== nextMsg.text ||
      toEpochMs(prevMsg.create_time) !== toEpochMs(nextMsg.create_time)
    ) {
      return false;
    }
  }

  return true;
}
import { Transcript, TranscriptEntry } from "@/interfaces/transcript.interface";
import { useState } from "react";
import { Database } from "lucide-react";
import { Button } from "@/components/button";
import { usePermissions } from "@/context/PermissionContext";
import { AddToDatasetDialog } from "@/views/TestSuites/components/AddToDatasetDialog";
import { canAddConversationToDataset } from "@/views/TestSuites/helpers/conversationDatasets";

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
  const permissions = usePermissions();
  const canAddToDataset = canAddConversationToDataset(permissions, transcript?.id);
  const [isAddToDatasetOpen, setIsAddToDatasetOpen] = useState(false);

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          <ActiveConversationTitle controller={controller} />
        </DialogTitle>
      </DialogHeader>

      {/* Pinned to the corner beside the close X rather than placed in the
          header, so the wrapping badge row is untouched and the h2 the dialog
          is named by stays free of button text. top-[10px] centres it on the X. */}
      {canAddToDataset && (
        <Button
          variant="outline"
          size="sm"
          className="absolute right-12 top-[10px] h-7 gap-1.5 px-2.5 text-xs font-normal"
          title="Add this conversation to an evaluation dataset"
          onClick={() => setIsAddToDatasetOpen(true)}
        >
          <Database className="h-3.5 w-3.5" />
          Add to dataset
        </Button>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:h-[550px] md:overflow-hidden">
        <ActiveConversationStatsPanel controller={controller} />
        <ActiveConversationThreadPanel
          controller={controller}
          className="md:col-span-2"
        />
      </div>

      <AddToDatasetDialog
        open={isAddToDatasetOpen}
        onOpenChange={setIsAddToDatasetOpen}
        conversationId={transcript?.id ?? null}
        conversationLabel={`Chat #${transcript.id.slice(-4)}`}
      />
    </>
  );
}
