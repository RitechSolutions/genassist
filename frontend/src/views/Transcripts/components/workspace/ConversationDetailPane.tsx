import { ArrowLeft, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { AgentResponseLogDialog } from "@/components/AgentResponseLogDialog";
import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/RadixTooltip";
import { Transcript } from "@/interfaces/transcript.interface";
import { useActiveConversationDetail } from "@/views/ActiveConversations/hooks/useActiveConversationDetail";
import { ActiveConversationStatsPanel } from "@/views/ActiveConversations/components/detail/ActiveConversationStatsPanel";
import { ActiveConversationThreadPanel } from "@/views/ActiveConversations/components/detail/ActiveConversationThreadPanel";
import { ActiveConversationTitle } from "@/views/ActiveConversations/components/detail/ActiveConversationTitle";

import { useTranscriptDetail } from "../../hooks/useTranscriptDetail";
import { TranscriptConversationPanel } from "../detail/TranscriptConversationPanel";
import { TranscriptDetailTitle } from "../detail/TranscriptDetailTitle";
import { TranscriptStatsPanel } from "../detail/TranscriptStatsPanel";

type ConversationDetailPaneProps = {
  transcript: Transcript;
  /** Live conversations get the takeover/supervisor surface, finalized ones the analysis one. */
  isLive: boolean;
  agentName?: string;
  /** Clears the selection — only reachable below `lg`, where the columns stack. */
  onBack: () => void;
  showStats: boolean;
  onToggleStats: () => void;
  refetchConversations: () => void;
  onTakeOver: (transcriptId: string) => Promise<boolean>;
  /**
   * Awaited once a live conversation is finalized on the server, so the pane can keep its
   * "finalizing" overlay up until the owner has swapped in the finalized surface.
   */
  onConversationFinalized?: (transcriptId: string) => void | Promise<void>;
  /**
   * Reports a blocking action (finalize) so the workspace can cover *all* its columns — the
   * conversation list would otherwise keep offering the conversation as live while it is being
   * finalized. Must be referentially stable.
   */
  onBusyChange?: (busy: boolean, label?: string) => void;
};

/**
 * The conversation + stats columns of the split view. Renders two sibling cards so the
 * workspace lays them out as separate columns.
 */
export function ConversationDetailPane({
  transcript,
  isLive,
  agentName,
  onBack,
  showStats,
  onToggleStats,
  refetchConversations,
  onTakeOver,
  onConversationFinalized,
  onBusyChange,
}: ConversationDetailPaneProps) {
  const shared = { onBack, showStats, onToggleStats };

  return isLive ? (
    <LiveConversationDetail
      key={`live-${transcript.id}`}
      transcript={transcript}
      refetchConversations={refetchConversations}
      onTakeOver={onTakeOver}
      onConversationFinalized={onConversationFinalized}
      onBusyChange={onBusyChange}
      {...shared}
    />
  ) : (
    <FinalizedConversationDetail
      key={`finalized-${transcript.id}`}
      transcript={transcript}
      agentName={agentName}
      {...shared}
    />
  );
}

function LiveConversationDetail({
  transcript,
  refetchConversations,
  onTakeOver,
  onConversationFinalized,
  onBusyChange,
  onBack,
  showStats,
  onToggleStats,
}: Pick<
  ConversationDetailPaneProps,
  | "transcript"
  | "refetchConversations"
  | "onTakeOver"
  | "onConversationFinalized"
  | "onBusyChange"
  | "onBack"
  | "showStats"
  | "onToggleStats"
>) {
  const controller = useActiveConversationDetail({
    transcript,
    isActive: true,
    onTakeOver,
    refetchConversations,
    onFinalized: onConversationFinalized,
  });

  const { isFinalizing } = controller;
  useEffect(() => {
    onBusyChange?.(isFinalizing, isFinalizing ? "Finalizing conversation..." : undefined);
    // Also clears on unmount, which is exactly when the finalized surface takes over.
    return () => onBusyChange?.(false);
  }, [isFinalizing, onBusyChange]);

  return (
    <>
      <DetailCard
        title={
          <ActiveConversationTitle
            controller={controller}
            leading={<BackButton onClick={onBack} />}
            trailing={<StatsToggle showStats={showStats} onToggle={onToggleStats} />}
          />
        }
      >
        <ActiveConversationThreadPanel controller={controller} />
      </DetailCard>

      <StatsCard show={showStats}>
        <ActiveConversationStatsPanel controller={controller} />
      </StatsCard>
    </>
  );
}

function FinalizedConversationDetail({
  transcript,
  agentName,
  onBack,
  showStats,
  onToggleStats,
}: Pick<
  ConversationDetailPaneProps,
  "transcript" | "agentName" | "onBack" | "showStats" | "onToggleStats"
>) {
  const controller = useTranscriptDetail({ transcript, isActive: true, agentName });

  if (!controller.transcript) return null;

  return (
    <>
      <DetailCard
        title={
          <TranscriptDetailTitle
            controller={controller}
            leading={<BackButton onClick={onBack} />}
            trailing={<StatsToggle showStats={showStats} onToggle={onToggleStats} />}
          />
        }
      >
        <TranscriptConversationPanel controller={controller} fill />
        <AgentResponseLogDialog
          isOpen={controller.debugLogOpen}
          onOpenChange={controller.closeDebugLog}
          messageId={controller.debugMessageId}
        />
      </DetailCard>

      <StatsCard show={showStats}>
        <TranscriptStatsPanel controller={controller} />
      </StatsCard>
    </>
  );
}

function DetailCard({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <Card className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-card dark:bg-zinc-900">
      <div className="flex shrink-0 items-start gap-2 border-b border-border px-4 py-3 text-lg font-semibold leading-none tracking-tight">
        {title}
      </div>
      <div className="flex min-h-0 flex-1 flex-col p-4">{children}</div>
    </Card>
  );
}

function StatsCard({ show, children }: { show: boolean; children: ReactNode }) {
  if (!show) return null;
  return (
    <Card className="hidden w-[340px] shrink-0 flex-col overflow-hidden bg-card dark:bg-zinc-900 xl:flex">
      <div className="shrink-0 border-b border-border px-4 py-3 text-sm font-semibold">
        Conversation stats
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
    </Card>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="-ml-1 h-7 w-7 shrink-0 lg:hidden"
      onClick={onClick}
      aria-label="Back to conversation list"
    >
      <ArrowLeft className="h-4 w-4" />
    </Button>
  );
}

function StatsToggle({ showStats, onToggle }: { showStats: boolean; onToggle: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="hidden h-7 w-7 shrink-0 xl:inline-flex"
          onClick={onToggle}
          aria-pressed={showStats}
          aria-label={showStats ? "Hide conversation stats" : "Show conversation stats"}
        >
          {showStats ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{showStats ? "Hide stats" : "Show stats"}</TooltipContent>
    </Tooltip>
  );
}
