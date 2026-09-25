import { MessageSquare } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/badge";
import { cn } from "@/helpers/utils";

import type { ActiveConversationDetailController } from "../../hooks/useActiveConversationDetail";

type ActiveConversationTitleProps = {
  controller: ActiveConversationDetailController;
  /** Rendered before the conversation icon — used by the workspace for its back button. */
  leading?: ReactNode;
  /** Rendered at the end of the badge row, e.g. the workspace's "toggle stats" control. */
  trailing?: ReactNode;
  className?: string;
};

/**
 * The live conversation title row (id, sentiment, Live / Supervisor badges) without any
 * dialog chrome, so it can sit inside a `DialogTitle` or straight in a page header.
 */
export function ActiveConversationTitle({
  controller,
  leading,
  trailing,
  className,
}: ActiveConversationTitleProps) {
  const {
    transcript,
    sentiment,
    isConnected,
    isCurrentUserSupervisor,
    isTakenOverByOther,
  } = controller;

  return (
    <span className={cn("flex w-full flex-col gap-1.5 items-start", className)}>
      <span className="flex w-full flex-wrap items-center gap-2">
        {leading}
        <MessageSquare className="w-5 h-5 shrink-0" />
        <span>Chat #{transcript.id.slice(-4)}</span>
        <Badge
          variant="default"
          className={
            sentiment === "positive"
              ? "bg-green-600 text-white"
              : sentiment === "negative"
              ? "bg-destructive text-destructive-foreground"
              : "bg-purple-600 text-white"
          }
        >
          {sentiment.charAt(0).toUpperCase() + sentiment.slice(1)}
        </Badge>
        {isConnected && (
          <Badge
            variant="outline"
            className="bg-green-50 text-green-700 border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30"
          >
            Live
          </Badge>
        )}
        {isCurrentUserSupervisor && (
          <Badge
            variant="outline"
            className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30"
          >
            Supervisor Mode
          </Badge>
        )}
        {isTakenOverByOther && (
          <Badge
            variant="outline"
            className="bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-500/15 dark:text-amber-400 dark:border-amber-500/30"
          >
            Taken over
          </Badge>
        )}
        {trailing ? <span className="ml-auto flex items-center">{trailing}</span> : null}
      </span>
      {transcript.agent_name?.trim() ? (
        <span className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground">
          {transcript.agent_name.trim()}
        </span>
      ) : null}
    </span>
  );
}
