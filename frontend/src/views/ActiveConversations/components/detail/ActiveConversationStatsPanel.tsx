import { AlertTriangle, Frown, MessageCircle, Timer, User } from "lucide-react";
import React from "react";

import { cn } from "@/helpers/utils";

import { formatDuration } from "../../helpers/format";
import type { ActiveConversationDetailController } from "../../hooks/useActiveConversationDetail";

type ActiveConversationStatsPanelProps = {
  controller: ActiveConversationDetailController;
  className?: string;
};

/**
 * Running stats for a live conversation. Extracted from `ActiveConversationDialog` so the
 * Conversations workspace can render it as its own column.
 *
 * Deliberately has no feedback form: a conversation is only rated once it is finalized, so
 * that lives on the finalized surface (`TranscriptStatsPanel`).
 */
export function ActiveConversationStatsPanel({
  controller,
  className,
}: ActiveConversationStatsPanelProps) {
  const {
    conversationStats,
    durationInSeconds,
    hostilityScore,
    topicText,
    isCurrentUserSupervisor,
    isTakenOverByOther,
    supervisorDisplayName,
  } = controller;

  return (
    <div className={cn("flex h-full flex-col", className)}>
      <div className="flex-1 space-y-4 overflow-y-auto">
        <InfoBox
          icon={<Timer />}
          label="Duration"
          value={formatDuration(durationInSeconds)}
        />
        <InfoBox
          icon={<User />}
          label="Agent/Customer Ratio"
          value={`${conversationStats.agent_ratio || 0}% / ${
            conversationStats.customer_ratio || 0
          }%`}
        />
        <InfoBox
          icon={<MessageCircle />}
          label="Word Count"
          value={`${conversationStats.word_count || 0}`}
        />
        <InfoBox
          icon={<Frown />}
          label="Hostility"
          value={`${hostilityScore}%`}
        />

        <TopicBox
          text={
            isCurrentUserSupervisor
              ? "You have taken over this conversation"
              : isTakenOverByOther
                ? `${supervisorDisplayName} has taken over this conversation`
                : topicText
          }
        />
      </div>
    </div>
  );
}

function InfoBox({
  icon,
  label,
  value,
}: {
  icon: JSX.Element;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center p-3 bg-muted rounded-lg">
      {icon}
      <span className="text-sm font-medium">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function TopicBox({ text }: { text: string }) {
  return (
    <div className="flex bg-amber-50 rounded-xl p-4 dark:bg-amber-500/15">
      <AlertTriangle className="w-5 h-5 text-amber-600 mt-1 dark:text-amber-400" />
      <div className="flex flex-col justify-start items-start ml-3">
        <span className="text-sm font-semibold leading-tight">Topic</span>
        <span className="text-sm">{text}</span>
      </div>
    </div>
  );
}
