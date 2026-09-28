import { useState } from 'react';
import { Database } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/dialog';
import { AgentResponseLogDialog } from '@/components/AgentResponseLogDialog';
import { Button } from '@/components/button';
import { Transcript } from '@/interfaces/transcript.interface';
import { usePermissions } from '@/context/PermissionContext';
import { AddToDatasetDialog } from '@/views/TestSuites/components/AddToDatasetDialog';
import { canAddConversationToDataset } from '@/views/TestSuites/helpers/conversationDatasets';

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
  const permissions = usePermissions();
  const [isAddToDatasetOpen, setIsAddToDatasetOpen] = useState(false);

  if (!controller.transcript) return null;

  const canAddToDataset = canAddConversationToDataset(permissions, controller.transcript.id);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl 2xl:max-w-[1120px] min-[1920px]:max-w-[1340px]">
        <DialogHeader>
          <DialogTitle>
            <TranscriptDetailTitle controller={controller} />
          </DialogTitle>
        </DialogHeader>

        {/* Pinned to the corner beside the close X rather than placed in the
            header, so nothing else shifts and the h2 the dialog is named by
            stays free of button text. top-[10px] centres it on the X. */}
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

        <div className="grid grid-cols-1 md:grid-cols-[350px_1fr] gap-6 items-start">
          <TranscriptStatsPanel controller={controller} />
          <TranscriptConversationPanel controller={controller} />
        </div>

        <AgentResponseLogDialog
          isOpen={controller.debugLogOpen}
          onOpenChange={controller.closeDebugLog}
          messageId={controller.debugMessageId}
        />

        <AddToDatasetDialog
          open={isAddToDatasetOpen}
          onOpenChange={setIsAddToDatasetOpen}
          conversationId={controller.transcript.id ?? null}
          conversationLabel={`${controller.isCall ? 'Call' : 'Chat'} #${(controller.transcript.metadata?.title ?? '----').slice(-4)}`}
        />
      </DialogContent>
    </Dialog>
  );
}
