import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/dialog';
import { AgentResponseLogDialog } from '@/components/AgentResponseLogDialog';
import { Transcript } from '@/interfaces/transcript.interface';

import { useTranscriptDetail } from '../hooks/useTranscriptDetail';
import { TranscriptConversationPanel } from './detail/TranscriptConversationPanel';
import { TranscriptDetailTitle } from './detail/TranscriptDetailTitle';
import { TranscriptStatsPanel } from './detail/TranscriptStatsPanel';

type TranscriptDialogProps = {
  transcript: Transcript | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** When the list is filtered to one agent, pass its name so the header can show it without extra metadata on the row. */
  agentName?: string;
};

/**
 * Finalized conversation detail as a dialog. The body is the same pair of panels the
 * Conversations workspace renders as columns — see `useTranscriptDetail`.
 */
export function TranscriptDialog({ transcript, isOpen, onOpenChange, agentName }: TranscriptDialogProps) {
  const controller = useTranscriptDetail({ transcript, isActive: isOpen, agentName });

  if (!controller.transcript) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl 2xl:max-w-[1120px] min-[1920px]:max-w-[1340px]">
        <DialogHeader>
          <DialogTitle>
            <TranscriptDetailTitle controller={controller} />
          </DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-[350px_1fr] gap-6 items-start">
          <TranscriptStatsPanel controller={controller} />
          <TranscriptConversationPanel controller={controller} />
        </div>

        <AgentResponseLogDialog
          isOpen={controller.debugLogOpen}
          onOpenChange={controller.closeDebugLog}
          messageId={controller.debugMessageId}
        />
      </DialogContent>
    </Dialog>
  );
}
