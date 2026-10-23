import { useState } from 'react';
import { Database, X } from 'lucide-react';
import { Dialog, DialogClose, DialogContent, DialogHeader, DialogTitle } from '@/components/dialog';
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
      {/* [&>button]:hidden drops the built-in corner X; the header row carries its own close. */}
      <DialogContent className="max-w-5xl 2xl:max-w-[1120px] min-[1920px]:max-w-[1340px] [&>button]:hidden">
        <DialogHeader>
          <DialogTitle>
            <TranscriptDetailTitle
              controller={controller}
              actions={
                canAddToDataset && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    title="Add to dataset"
                    aria-label="Add to dataset"
                    onClick={() => setIsAddToDatasetOpen(true)}
                  >
                    <Database className="h-4 w-4" />
                  </Button>
                )
              }
              trailing={
                <DialogClose asChild>
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0" title="Close" aria-label="Close">
                    <X className="h-4 w-4" />
                  </Button>
                </DialogClose>
              }
            />
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
